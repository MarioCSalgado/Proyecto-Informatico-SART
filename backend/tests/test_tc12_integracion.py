
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Estacion, Medicion, PronosticoAmbiental
from sart.dominio.valores import (
    UNIDAD_POR_TIPO,
    FuenteEstacion,
    OrigenMedicion,
    TipoMedicion,
)
from sart.tareas.precision_pronostico import evaluar_tc12_desde_bd


def test_tc12_conecta_pronosticos_con_observaciones_reales(base_prueba):
    zona = ZoneInfo("America/Santiago")

    with Session(base_prueba) as sesion:
        kingston = sesion.scalars(
            select(Estacion).where(
                Estacion.nombre == "Kingston College",
                Estacion.fuente == FuenteEstacion.SINCA,
            )
        ).one()

        open_meteo = sesion.scalars(
            select(Estacion).where(
                Estacion.fuente == FuenteEstacion.OPEN_METEO,
                Estacion.nombre == "Open-Meteo Concepción",  # el punto principal (RF-4 agrega uno por comuna)
            )
        ).one()

        mediciones = sesion.scalars(
            select(Medicion).where(
                Medicion.estacion_id == kingston.id,
                Medicion.tipo == TipoMedicion.MP25,
                Medicion.origen == OrigenMedicion.OBSERVADO,
            )
        ).all()

        # Agrupa las observaciones por día local.
        valores_por_dia = defaultdict(list)

        for medicion in mediciones:
            fecha = medicion.fecha_hora
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=UTC)

            dia = fecha.astimezone(zona).date()
            valores_por_dia[dia].append(medicion.valor)

        # Selecciona un día real cuyo promedio observado supere 50.
        dia_objetivo = next(
            dia
            for dia, valores in sorted(valores_por_dia.items())
            if sum(valores) / len(valores) > 50
        )

        emision_local = datetime.combine(
            dia_objetivo - timedelta(days=1),
            time(7),
            tzinfo=zona,
        )

        unidad = UNIDAD_POR_TIPO[TipoMedicion.MP25]

        # Inserta 24 horas de pronóstico sintético sobre el umbral.
        for hora in range(24):
            objetivo_local = datetime.combine(
                dia_objetivo,
                time(hora),
                tzinfo=zona,
            )

            sesion.add(
                PronosticoAmbiental(
                    estacion_id=open_meteo.id,
                    fecha_hora=objetivo_local.astimezone(UTC),
                    emitido_en=emision_local.astimezone(UTC),
                    tipo=TipoMedicion.MP25,
                    valor=60.0,
                    unidad=unidad,
                )
            )

        sesion.commit()

        resultado = evaluar_tc12_desde_bd(
            sesion,
            zona_horaria="America/Santiago",
            desde=dia_objetivo,
            hasta=dia_objetivo,
        )

        assert resultado.verdaderos_positivos == 1
        assert resultado.falsos_negativos == 0
        assert resultado.dias_observados_sobre_umbral == 1
        assert resultado.sensibilidad == 1.0
        assert resultado.cumple is True

def test_tc12_identifica_falta_de_pronosticos_historicos(base_prueba):
    with Session(base_prueba) as sesion:
        resultado = evaluar_tc12_desde_bd(
            sesion,
            zona_horaria="America/Santiago",
        )

    print("\nResultado TC-12 con los datos disponibles:")
    print(f"Días observados: {resultado.dias_evaluados}")
    print(f"Días observados sobre 50: {resultado.dias_observados_sobre_umbral}")
    print(f"Días sin pronóstico válido: {resultado.dias_sin_pronostico}")
    print(f"Verdaderos positivos: {resultado.verdaderos_positivos}")
    print(f"Falsos negativos: {resultado.falsos_negativos}")
    print(f"Sensibilidad: {resultado.sensibilidad}")
    print(f"¿Cumple ≥ 0,50?: {resultado.cumple}")

    assert resultado.dias_observados_sobre_umbral > 0
    assert resultado.dias_sin_pronostico > 0
    assert resultado.sensibilidad == 0.0
    assert resultado.cumple is False
