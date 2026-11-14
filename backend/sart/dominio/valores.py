"""Conjuntos de valores válidos de las entidades de §5.1 (los usa la base para sus restricciones)."""

from __future__ import annotations

from enum import StrEnum


class TipoCentro(StrEnum):
    """§5.1 Centro_Salud: SAPU, SAR, SUR u hospital (las horas de funcionamiento de RF-6 dependen de esto)."""

    SAPU = "SAPU"
    SAR = "SAR"
    SUR = "SUR"
    HOSPITAL = "hospital"


class FuenteEstacion(StrEnum):
    """De dónde vienen las mediciones de una estación. Open-Meteo entrega un punto, no una estación física:
    se registra como estación de fuente Open-Meteo (pendientes #27)."""

    SINCA = "SINCA"
    OPEN_METEO = "Open-Meteo"


class TipoMedicion(StrEnum):
    MP25 = "mp25"
    MP10 = "mp10"
    TEMPERATURA_MEDIA = "temperatura_media"
    TEMPERATURA_MINIMA = "temperatura_minima"
    HUMEDAD = "humedad"


# §5.1 Medición: «la unidad debe ser compatible con el tipo de medición».
UNIDAD_POR_TIPO: dict[TipoMedicion, str] = {
    TipoMedicion.MP25: "µg/m³",
    TipoMedicion.MP10: "µg/m³",
    TipoMedicion.TEMPERATURA_MEDIA: "°C",
    TipoMedicion.TEMPERATURA_MINIMA: "°C",
    TipoMedicion.HUMEDAD: "%",
}


class OrigenMedicion(StrEnum):
    """Valor medido o pronosticado (el pronóstico de MP2,5 de Open-Meteo alimenta RF-4)."""

    OBSERVADO = "observado"
    PRONOSTICO = "pronostico"


class CalidadDato(StrEnum):
    """Estado del dato en SINCA: los validados tienen prioridad sobre los preliminares."""

    VALIDADO = "validado"
    PRELIMINAR = "preliminar"
    NO_VALIDADO = "no_validado"


class TipoAlerta(StrEnum):
    """§5.1: la alerta de demanda es de un centro (RF-3); la ambiental, de una zona (RF-4)."""

    DEMANDA = "demanda"
    AMBIENTAL = "ambiental"


# Niveles que generan una alerta. «Normal» no genera alerta en ninguno de los dos tipos.
NIVELES_DEMANDA = ("atencion", "alerta")  # RF-3, RB-3
NIVELES_AMBIENTALES = ("sobre_la_norma", "alerta", "preemergencia", "emergencia")  # RF-4, RB-1, TC-05


class EstadoNotificacion(StrEnum):
    """§5.1 Notificación: enviada, fallida, confirmada, reenviada o escalada (RF-5, RF-15, RB-2)."""

    ENVIADA = "enviada"
    FALLIDA = "fallida"
    CONFIRMADA = "confirmada"
    REENVIADA = "reenviada"
    ESCALADA = "escalada"


# Columnas de grupo de edad del archivo de urgencias del DEIS → clave guardada en consulta_semanal.grupo_edad
GRUPOS_EDAD_DEIS: dict[str, str] = {
    "Menores_1": "menores_1",
    "De_1_a_4": "de_1_a_4",
    "De_5_a_14": "de_5_a_14",
    "De_15_a_64": "de_15_a_64",
    "De_65_y_mas": "de_65_y_mas",
}


class OrigenUmbral(StrEnum):
    """RB-3 calcula los umbrales; RF-9 permite que el administrador los corrija con un motivo."""

    CALCULADO = "calculado"
    MANUAL = "manual"


class EstadoCorrida(StrEnum):
    """Estado de cada corrida de una tarea programada o de una carga (RNF-M-3)."""

    EN_CURSO = "en_curso"
    EXITOSA = "exitosa"
    FALLIDA = "fallida"
