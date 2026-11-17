
"""Corrida diaria de alertas ambientales de MP2,5 (RF-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from math import isfinite
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import Alerta, Estacion, Medicion, Zona
from sart.db.supuestos import parametros_vigentes
from sart.dominio.ambiental import (
    PronosticoHorarioMp25,
    calcular_promedios_diarios_mp25,
)
from sart.dominio.mp25 import clasificar_mp25
from sart.dominio.valores import (
    FuenteEstacion,
    OrigenMedicion,
    TipoAlerta,
    TipoMedicion,
)
from sart.tareas.corridas import registrar_corrida
from sart.tareas.precision_pronostico import evaluar_tc12_desde_bd


TAREA = "alerta_ambiental_diaria"
DIAS_VIGENCIA_SINCA = 7


class ErrorCorridaAmbiental(ValueError):
    """La corrida ambiental no se puede realizar."""


@dataclass
class ResumenAmbiental:
    primer_dia: date
    dias: int
    promedios_calculados: int = 0
    alertas: int = 0
    datos_insuficientes: list[str] = field(default_factory=list)
    fuente: str = "pronostico"
    sensibilidad_tc12: float | None = None

    def texto(self) -> str:
        lineas = [
            f"Corrida ambiental desde {self.primer_dia}: "
            f"{self.promedios_calculados} promedios calculados y "
            f"{self.alertas} alertas ambientales emitidas.",
            f"Fuente utilizada: {self.fuente}.",
        ]

        if self.sensibilidad_tc12 is not None:
            lineas.append(
                f"Sensibilidad TC-12: {self.sensibilidad_tc12:.3f}."
            )

        if self.datos_insuficientes:
            lineas.append(
                "Datos insuficientes para: "
                + ", ".join(self.datos_insuficientes)
                + "."
            )

        return "\n".join(lineas)


def _hoy(parametros: dict) -> date:
    return datetime.now(ZoneInfo(parametros["zona_horaria"])).date()


def correr_ambiental(
    sesion: Session,
    *,
    fecha: date | None = None,
    parametros: dict | None = None,
) -> ResumenAmbiental:
    """Ejecuta RF-4 y registra el resultado de la corrida."""
    with registrar_corrida(sesion, TAREA) as corrida:
        resumen = _correr(sesion, fecha, parametros)
        corrida.filas = resumen.promedios_calculados
        corrida.mensaje = resumen.texto()

    return resumen


def _sensibilidad_tc12(
    sesion: Session,
    zona_horaria: str,
) -> tuple[bool, float | None]:
    """Determina si los pronósticos tienen la sensibilidad mínima."""
    try:
        resultado = evaluar_tc12_desde_bd(
            sesion,
            zona_horaria=zona_horaria,
        )
    except (ValueError, KeyError):
        # Ante una evaluación imposible no se habilita la anticipación.
        return False, None

    return bool(resultado.cumple), resultado.sensibilidad


def _normalizar_fecha_hora(valor: datetime) -> datetime:
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


def _guardar_alerta(
    sesion: Session,
    *,
    zona: Zona,
    dia: date,
    valor: float,
    nivel,
    fuente: str,
    emision: datetime,
) -> bool:
    """Guarda una alerta ambiental sin duplicar la misma fuente y fecha."""
    if fuente == "pronostico":
        existente = sesion.scalar(
            select(Alerta).where(
                Alerta.tipo == TipoAlerta.AMBIENTAL,
                Alerta.zona_id == zona.id,
                Alerta.fuente_ambiental == "pronostico",
                Alerta.dia_pronosticado == dia,
            )
        )
    else:
        existente = sesion.scalar(
            select(Alerta).where(
                Alerta.tipo == TipoAlerta.AMBIENTAL,
                Alerta.zona_id == zona.id,
                Alerta.fuente_ambiental == "sinca",
                Alerta.dia_observado == dia,
            )
        )

    if existente is not None:
        return False

    if fuente == "pronostico":
        mensaje = (
            f"Alerta ambiental para {zona.nombre} el {dia}: "
            f"promedio pronosticado de MP2,5 de {valor:.1f} µg/m³. "
            f"Nivel: {nivel.nombre}. "
            "Este aviso se basa en un pronóstico y no constituye "
            "una declaración oficial sobre la calidad del aire."
        )
    else:
        mensaje = (
            f"Alerta ambiental para {zona.nombre} el {dia}: "
            f"medición observada de MP2,5 de {valor:.1f} µg/m³. "
            f"Nivel: {nivel.nombre}. "
            "Este aviso se basa en datos observados de SINCA y no "
            "constituye una declaración oficial sobre la calidad del aire."
        )

    alerta = Alerta(
        tipo=TipoAlerta.AMBIENTAL,
        nivel=nivel.clave,
        fuente_ambiental=fuente,
        fecha_emision=emision,
        zona_id=zona.id,
        dia_pronosticado=dia if fuente == "pronostico" else None,
        dia_observado=dia if fuente == "sinca" else None,
        valor_mp25=valor,
        mensaje=mensaje,
    )
    sesion.add(alerta)
    sesion.flush()

    nuevo = {
        "tipo": "ambiental",
        "zona": zona.nombre,
        "fuente_ambiental": fuente,
        "nivel": nivel.clave,
        "valor_mp25": round(valor, 1),
    }
    nuevo["dia_pronosticado" if fuente == "pronostico" else "dia_observado"] = (
        dia.isoformat()
    )

    registrar_auditoria(
        sesion,
        autor=None,
        accion="emision_alerta",
        entidad="alerta",
        entidad_id=alerta.id,
        nuevo=nuevo,
        motivo="RF-4: corrida ambiental diaria",
    )

    return True


def _estaciones_sinca(sesion: Session) -> dict[str, Estacion]:
    estaciones = sesion.scalars(
        select(Estacion).where(
            Estacion.fuente == FuenteEstacion.SINCA
        )
    ).all()
    return {estacion.nombre: estacion for estacion in estaciones}


def _mediciones_sinca_recientes(
    sesion: Session,
    *,
    estaciones: dict[str, Estacion],
    hoy: date,
    zona_horaria: str,
) -> dict[int, tuple[date, float]]:
    """Obtiene la última medición observada y vigente por estación."""
    tz = ZoneInfo(zona_horaria)
    desde_local = datetime.combine(
        hoy - timedelta(days=DIAS_VIGENCIA_SINCA - 1),
        time.min,
        tzinfo=tz,
    )
    hasta_local = (
        datetime.combine(
            hoy + timedelta(days=1),
            time.min,
            tzinfo=tz,
        )
        - timedelta(microseconds=1)
    )

    desde_utc = desde_local.astimezone(UTC)
    hasta_utc = hasta_local.astimezone(UTC)

    ids = [estacion.id for estacion in estaciones.values()]
    if not ids:
        return {}

    registros = sesion.execute(
        select(Medicion, Estacion)
        .join(Estacion, Estacion.id == Medicion.estacion_id)
        .where(
            Medicion.estacion_id.in_(ids),
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.OBSERVADO,
            Medicion.fecha_hora >= desde_utc,
            Medicion.fecha_hora <= hasta_utc,
        )
        .order_by(Medicion.fecha_hora.desc())
    ).all()

    ultimas: dict[int, tuple[date, float]] = {}

    for medicion, estacion in registros:
        if estacion.id in ultimas:
            continue

        valor = float(medicion.valor)
        if not isfinite(valor) or valor < 0:
            continue

        fecha_local = _normalizar_fecha_hora(
            medicion.fecha_hora
        ).astimezone(tz).date()

        if fecha_local > hoy:
            continue

        ultimas[estacion.id] = (fecha_local, valor)

    return ultimas


def _correr_sinca(
    sesion: Session,
    *,
    parametros: dict,
    fecha: date,
    sensibilidad: float | None,
) -> ResumenAmbiental:
    """Emite alertas basadas en observaciones SINCA recientes."""
    zona_horaria = parametros["zona_horaria"]
    comunas = parametros["escenario"]["comunas"]
    umbrales = parametros["mp25_niveles"]
    catalogo = parametros["catalogo"]

    estaciones = _estaciones_sinca(sesion)
    respaldo_nombre = parametros["escenario"]["estacion_respaldo"]
    respaldo = estaciones.get(respaldo_nombre)

    if respaldo is None:
        raise ErrorCorridaAmbiental(
            f"No existe la estación SINCA de respaldo {respaldo_nombre!r}."
        )

    asignaciones = catalogo["estacion_por_comuna"]
    ultimas = _mediciones_sinca_recientes(
        sesion,
        estaciones=estaciones,
        hoy=fecha,
        zona_horaria=zona_horaria,
    )

    zonas_db = {
        zona.nombre: zona
        for zona in sesion.scalars(select(Zona))
    }

    resumen = ResumenAmbiental(
        primer_dia=fecha,
        dias=1,
        fuente="sinca",
        sensibilidad_tc12=sensibilidad,
    )
    emision = datetime.now(UTC)

    for comuna in comunas:
        zona = zonas_db.get(comuna)
        if zona is None:
            raise ErrorCorridaAmbiental(
                f"No existe la zona {comuna!r} en la base de datos."
            )

        nombre_asignado = asignaciones.get(comuna)
        asignada = estaciones.get(nombre_asignado) if nombre_asignado else None

        medicion = ultimas.get(asignada.id) if asignada else None
        estacion_utilizada = asignada

        # RB-5: si la estación asignada no tiene datos recientes,
        # se consulta Kingston College como respaldo.
        if medicion is None:
            medicion = ultimas.get(respaldo.id)
            estacion_utilizada = respaldo

        if medicion is None:
            resumen.datos_insuficientes.append(comuna)
            continue

        dia_observado, valor = medicion
        nivel = clasificar_mp25(valor, umbrales)
        resumen.promedios_calculados += 1

        # El nivel normal no genera una alerta.
        if nivel.clave == "normal":
            continue

        if _guardar_alerta(
            sesion,
            zona=zona,
            dia=dia_observado,
            valor=valor,
            nivel=nivel,
            fuente="sinca",
            emision=emision,
        ):
            resumen.alertas += 1

    sesion.commit()
    return resumen


def _correr_pronostico(
    sesion: Session,
    *,
    parametros: dict,
    fecha: date,
    sensibilidad: float | None,
) -> ResumenAmbiental:
    """Calcula los cinco días pronosticados y emite alertas anticipadas."""
    zona_horaria = parametros["zona_horaria"]
    zonas = parametros["escenario"]["comunas"]
    umbrales = parametros["mp25_niveles"]
    cantidad_dias = 5

    tz = ZoneInfo(zona_horaria)
    inicio_local = datetime.combine(fecha, time.min, tzinfo=tz)
    fin_local = datetime.combine(
        fecha + timedelta(days=cantidad_dias),
        time.min,
        tzinfo=tz,
    )

    registros = sesion.execute(
        select(Medicion, Estacion)
        .join(Estacion, Estacion.id == Medicion.estacion_id)
        .where(
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.PRONOSTICO,
            Estacion.fuente == FuenteEstacion.OPEN_METEO,
            Medicion.fecha_hora >= inicio_local.astimezone(UTC),
            Medicion.fecha_hora < fin_local.astimezone(UTC),
        )
    ).all()

    pronosticos = [
        PronosticoHorarioMp25(
            zona=estacion.zona.nombre,
            fecha_hora=_normalizar_fecha_hora(medicion.fecha_hora),
            valor=float(medicion.valor),
        )
        for medicion, estacion in registros
    ]

    resultados = calcular_promedios_diarios_mp25(
        pronosticos=pronosticos,
        zonas=zonas,
        primer_dia=fecha,
        umbrales=umbrales,
        zona_horaria=zona_horaria,
        cantidad_dias=cantidad_dias,
    )

    zonas_db = {
        zona.nombre: zona
        for zona in sesion.scalars(select(Zona))
    }

    resumen = ResumenAmbiental(
        primer_dia=fecha,
        dias=cantidad_dias,
        fuente="pronostico",
        sensibilidad_tc12=sensibilidad,
    )
    emision = datetime.now(UTC)

    for resultado in resultados:
        if resultado.estado == "datos_insuficientes":
            resumen.datos_insuficientes.append(
                f"{resultado.zona} ({resultado.dia})"
            )
            continue

        resumen.promedios_calculados += 1

        if resultado.nivel.clave == "normal":
            continue

        zona = zonas_db.get(resultado.zona)
        if zona is None:
            raise ErrorCorridaAmbiental(
                f"No existe la zona {resultado.zona!r} en la base de datos."
            )

        if _guardar_alerta(
            sesion,
            zona=zona,
            dia=resultado.dia,
            valor=resultado.promedio,
            nivel=resultado.nivel,
            fuente="pronostico",
            emision=emision,
        ):
            resumen.alertas += 1

    sesion.commit()
    return resumen


def _correr(
    sesion: Session,
    fecha: date | None,
    parametros: dict | None,
) -> ResumenAmbiental:
    parametros = parametros or parametros_vigentes(sesion)

    zona_horaria = parametros["zona_horaria"]
    hoy = _hoy(parametros)
    cumple_tc12, sensibilidad = _sensibilidad_tc12(
        sesion,
        zona_horaria,
    )

    if cumple_tc12:
        primer_dia = fecha or (hoy + timedelta(days=1))
        return _correr_pronostico(
            sesion,
            parametros=parametros,
            fecha=primer_dia,
            sensibilidad=sensibilidad,
        )

    # Si TC-12 no cumple, RF-4 utiliza observaciones SINCA.
    # Una fecha explícita se conserva para permitir pruebas reproducibles.
    fecha_observada = fecha or hoy
    return _correr_sinca(
        sesion,
        parametros=parametros,
        fecha=fecha_observada,
        sensibilidad=sensibilidad,
    )
