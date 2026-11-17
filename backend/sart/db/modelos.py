"""Modelos SQLAlchemy 2 de SART: las entidades de §5.1, más auditoría (RNF-S-4) y aceptación de la finalidad
(RF-16). Cada cambio aquí va con su migración en ``backend/migraciones``.

Regla que no se negocia: 0 datos de pacientes (RNF-S-5). Los conteos del DEIS son agregados por centro,
semana, causa y grupo de edad; Usuario guarda solo los datos de la cuenta (§5.3).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sart.dominio.acuse import nuevo_token_acuse
from sart.dominio.roles import Rol
from sart.dominio.valores import (
    NIVELES_AMBIENTALES,
    NIVELES_DEMANDA,
    NIVELES_PRONOSTICO,
    UNIDAD_POR_TIPO,
    CalidadDato,
    EstadoCorrida,
    EstadoNotificacion,
    FuenteEstacion,
    OrigenMedicion,
    OrigenUmbral,
    TipoAlerta,
    TipoCentro,
    TipoMedicion,
)

# Nombres estables para índices y restricciones, así Alembic genera migraciones reproducibles.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


def _enum(clase: type[StrEnum], nombre: str, largo: int) -> Enum:
    """VARCHAR con CHECK en vez de un tipo ENUM de PostgreSQL: más simple de migrar y funciona en SQLite."""
    return Enum(
        clase,
        name=nombre,
        native_enum=False,
        create_constraint=True,
        length=largo,
        values_callable=lambda valores: [v.value for v in valores],
    )


def _en(valores) -> str:
    return ", ".join(f"'{v}'" for v in valores)


# ---------------------------------------------------------------------------
# Cuentas (RF-16, RNF-S-1, RNF-S-2)
# ---------------------------------------------------------------------------
class Usuario(Base):
    """Cuenta de una jefatura, un subdirector o un administrador (§5.1). Único dato personal del sistema."""

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    correo: Mapped[str] = mapped_column(String(254), unique=True)  # §5.1: correo único
    rol: Mapped[Rol] = mapped_column(_enum(Rol, "rol", 20))
    hash_contrasena: Mapped[str] = mapped_column(String(255))  # Argon2id (RNF-S-1)
    # MFA TOTP, solo administradores (RNF-S-1). El secreto se guarda tal cual y lo protege el cifrado en
    # reposo de la base (RNF-S-3); ver docs/pendientes_informe.md #19.
    mfa_secreto: Mapped[str | None] = mapped_column(String(64))
    mfa_activado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_ultimo_paso: Mapped[int | None] = mapped_column(BigInteger)  # impide reusar un código
    mfa_intentos_fallidos: Mapped[int] = mapped_column(default=0, server_default="0")
    mfa_bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    aceptaciones: Mapped[list[AceptacionFinalidad]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )
    centros: Mapped[list[CentroSalud]] = relationship(secondary="usuario_centro", back_populates="usuarios")


class AceptacionFinalidad(Base):
    """Constancia de que el funcionario aceptó la finalidad de §5.3: fecha, hora y versión del texto (RF-16).

    Se borra con la cuenta (RF-16 E2); lo que se conserva de una baja es el registro de auditoría (RNF-S-4).
    """

    __tablename__ = "aceptacion_finalidad"
    __table_args__ = (UniqueConstraint("usuario_id", "version_texto"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    version_texto: Mapped[str] = mapped_column(String(20))
    aceptada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    usuario: Mapped[Usuario] = relationship(back_populates="aceptaciones")


class UsuarioCentro(Base):
    """Centros asignados a cada cuenta (§5.1 Usuario, RF-9). Una jefatura solo ve sus centros (RNF-S-2)."""

    __tablename__ = "usuario_centro"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True)
    centro_id: Mapped[int] = mapped_column(
        ForeignKey("centro_salud.id", ondelete="CASCADE"), primary_key=True
    )


# ---------------------------------------------------------------------------
# Catálogo: zonas, estaciones y centros (CI-3, RB-5)
# ---------------------------------------------------------------------------
class Zona(Base):
    """Área del Gran Concepción: una por comuna (pendientes #27). Agrupa centros y estaciones (RF-4)."""

    __tablename__ = "zona"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)


class Estacion(Base):
    """Estación de monitoreo. Las de SINCA miden MP2,5; el punto de Open-Meteo entrega clima y pronóstico."""

    __tablename__ = "estacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    comuna: Mapped[str] = mapped_column(String(100))
    direccion: Mapped[str | None] = mapped_column(String(200))  # pendientes #28
    zona_id: Mapped[int] = mapped_column(ForeignKey("zona.id"), index=True)
    fuente: Mapped[FuenteEstacion] = mapped_column(_enum(FuenteEstacion, "fuente_estacion", 20))
    codigo_sinca: Mapped[str | None] = mapped_column(String(20))
    latitud: Mapped[float | None] = mapped_column(Float)
    longitud: Mapped[float | None] = mapped_column(Float)
    es_respaldo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))  # RB-5

    zona: Mapped[Zona] = relationship()


class CentroSalud(Base):
    """Centro de urgencia del registro de establecimientos (§5.1), con su zona y su estación (CI-3)."""

    __tablename__ = "centro_salud"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_deis: Mapped[int] = mapped_column(unique=True)  # EstablecimientoCodigo
    codigo_antiguo: Mapped[int | None] = mapped_column(unique=True)  # el que usa el archivo de urgencias
    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoCentro] = mapped_column(_enum(TipoCentro, "tipo_centro", 10))
    comuna: Mapped[str] = mapped_column(String(100))
    direccion: Mapped[str | None] = mapped_column(String(200))  # pendientes #28
    latitud: Mapped[float | None] = mapped_column(Float)
    longitud: Mapped[float | None] = mapped_column(Float)
    zona_id: Mapped[int] = mapped_column(ForeignKey("zona.id"), index=True)
    estacion_id: Mapped[int] = mapped_column(ForeignKey("estacion.id"), index=True)

    zona: Mapped[Zona] = relationship()
    estacion: Mapped[Estacion] = relationship()
    usuarios: Mapped[list[Usuario]] = relationship(secondary="usuario_centro", back_populates="centros")


# ---------------------------------------------------------------------------
# Datos de entrada: consultas del DEIS y mediciones (RF-1)
# ---------------------------------------------------------------------------
class ConsultaSemanal(Base):
    """Conteo agregado de consultas de urgencia por centro, semana, causa y grupo de edad (§5.1, RF-1)."""

    __tablename__ = "consulta_semanal"
    __table_args__ = (
        UniqueConstraint("centro_id", "anio", "semana", "causa", "grupo_edad"),
        CheckConstraint("semana BETWEEN 1 AND 53", name="semana_valida"),
        CheckConstraint("cantidad >= 0", name="cantidad_no_negativa"),
    )

    # BIGINT por el volumen (cerca de un millón de filas); en SQLite, INTEGER para que autoincremente
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    centro_id: Mapped[int] = mapped_column(ForeignKey("centro_salud.id", ondelete="CASCADE"))
    anio: Mapped[int] = mapped_column(SmallInteger)
    semana: Mapped[int] = mapped_column(SmallInteger)  # semana epidemiológica del MINSAL
    causa: Mapped[str] = mapped_column(String(30))  # clave de ingesta.causas en parametros.yaml
    grupo_edad: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[int]


class SemanaCarga(Base):
    """Estado de cada semana publicada: cobertura y si está completa (RB-4). La lógica que decide «completa»
    es de la parte 5 (TC-01); mientras tanto queda en NULL (sin evaluar)."""

    __tablename__ = "semana_carga"
    __table_args__ = (CheckConstraint("semana BETWEEN 1 AND 53", name="semana_valida"),)

    anio: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    semana: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    centros_reportados: Mapped[int]
    completa: Mapped[bool | None] = mapped_column(Boolean)
    cargada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Medicion(Base):
    """Medición ambiental de una estación: MP2,5 de SINCA, o clima y pronóstico de MP2,5 de Open-Meteo."""

    __tablename__ = "medicion"
    __table_args__ = (
        UniqueConstraint("estacion_id", "tipo", "origen", "fecha_hora"),
        CheckConstraint(
            " OR ".join(
                f"(tipo = '{tipo.value}' AND unidad = '{unidad}')" for tipo, unidad in UNIDAD_POR_TIPO.items()
            ),
            name="unidad_compatible",
        ),
        CheckConstraint("tipo NOT IN ('mp25', 'mp10') OR valor >= 0", name="concentracion_no_negativa"),
        CheckConstraint("tipo <> 'humedad' OR valor BETWEEN 0 AND 100", name="humedad_valida"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    estacion_id: Mapped[int] = mapped_column(ForeignKey("estacion.id", ondelete="CASCADE"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tipo: Mapped[TipoMedicion] = mapped_column(_enum(TipoMedicion, "tipo_medicion", 20))
    valor: Mapped[float] = mapped_column(Float)
    unidad: Mapped[str] = mapped_column(String(10))
    origen: Mapped[OrigenMedicion] = mapped_column(
        _enum(OrigenMedicion, "origen_medicion", 12), default=OrigenMedicion.OBSERVADO
    )
    calidad: Mapped[CalidadDato | None] = mapped_column(_enum(CalidadDato, "calidad_dato", 12))

class PronosticoAmbiental(Base):
    __tablename__ = "pronostico_ambiental"

    __table_args__ = (
        UniqueConstraint(
            "estacion_id",
            "tipo",
            "fecha_hora",
            "emitido_en",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    estacion_id: Mapped[int] = mapped_column(
        ForeignKey("estacion.id"),
        nullable = False,
    )

    # Fecha/hora a la que corresponde el valor pronosticado.
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Momento en que este pronóstico fue cargado/emitido.
    emitido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    tipo: Mapped[TipoMedicion] = mapped_column(
        _enum(TipoMedicion, "tipo_medicion", 20),
        nullable=False,
    )

    valor: Mapped[float] = mapped_column(Float, nullable=False)

    unidad: Mapped[str] = mapped_column(String(10), nullable=False)

    estacion: Mapped["Estacion"] = relationship()


# ---------------------------------------------------------------------------
# Salidas: pronósticos, alertas y notificaciones (RF-2 a RF-5, RF-15)
# ---------------------------------------------------------------------------
class Pronostico(Base):
    """Pronóstico semanal de consultas de un centro con su intervalo de 90 % (§5.1, RF-2, CI-1).

    Guarda también con qué se clasificó (RF-3): el nivel, el umbral vigente y el k de ese momento, para que
    un cambio posterior de k o del umbral (RF-9) no altere lo que se informó (pendientes #39). ``nivel`` es
    NULL si el centro no tenía umbral vigente (RF-3 E1).
    """

    __tablename__ = "pronostico"
    __table_args__ = (
        CheckConstraint("valor > 0", name="valor_positivo"),
        CheckConstraint("limite_inferior <= valor AND valor <= limite_superior", name="dentro_del_intervalo"),
        CheckConstraint("semana BETWEEN 1 AND 53", name="semana_valida"),
        CheckConstraint(f"nivel IS NULL OR nivel IN ({_en(NIVELES_PRONOSTICO)})", name="nivel_valido"),
        CheckConstraint(
            "nivel IS NULL OR (umbral_id IS NOT NULL AND k_margen IS NOT NULL"
            " AND valor_con_margen IS NOT NULL)",
            name="clasificado_con_umbral",
        ),
        # §5.1: un solo pronóstico vigente por centro y semana
        Index(
            "uq_pronostico_vigente",
            "centro_id",
            "anio",
            "semana",
            unique=True,
            postgresql_where=text("vigente"),
            sqlite_where=text("vigente"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    centro_id: Mapped[int] = mapped_column(ForeignKey("centro_salud.id", ondelete="CASCADE"))
    anio: Mapped[int] = mapped_column(SmallInteger)
    semana: Mapped[int] = mapped_column(SmallInteger)
    valor: Mapped[float] = mapped_column(Float)
    limite_inferior: Mapped[float] = mapped_column(Float)
    limite_superior: Mapped[float] = mapped_column(Float)
    version_modelo: Mapped[str] = mapped_column(String(40))
    fecha_corte: Mapped[date] = mapped_column(Date)  # última semana completa usada (RB-4)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # RF-3: con qué se clasificó
    nivel: Mapped[str | None] = mapped_column(String(20))
    umbral_id: Mapped[int | None] = mapped_column(ForeignKey("umbral_centro.id"))
    k_margen: Mapped[float | None] = mapped_column(Float)
    valor_con_margen: Mapped[float | None] = mapped_column(Float)

    dotacion: Mapped[DotacionSugerida | None] = relationship(
        back_populates="pronostico", cascade="all, delete-orphan", passive_deletes=True
    )


class DotacionSugerida(Base):
    """Profesionales sugeridos en hora punta para un pronóstico (RF-6, CI-2), con los supuestos usados.

    Se guarda y no se recalcula al leer: si el administrador cambia un supuesto (RF-9), lo que se recomendó
    en su momento sigue igual en el correo (RF-5), el historial (RF-10) y la auditoría (RNF-S-4)
    (pendientes #39). Un centro cuyo tipo no tiene horas de funcionamiento definidas queda sin fila.
    """

    __tablename__ = "dotacion_sugerida"
    __table_args__ = (
        CheckConstraint("profesionales >= 1", name="al_menos_uno"),
        CheckConstraint("llegadas_hora_punta >= 0 AND espera_media_min >= 0", name="no_negativas"),
    )

    pronostico_id: Mapped[int] = mapped_column(
        ForeignKey("pronostico.id", ondelete="CASCADE"), primary_key=True
    )
    profesionales: Mapped[int]
    llegadas_hora_punta: Mapped[float] = mapped_column(Float)
    espera_media_min: Mapped[float] = mapped_column(Float)
    # espera con un profesional menos (Gherkin de RF-6: «con 2 profesionales la espera sería de 55 minutos»);
    # NULL si con uno menos no alcanza a atender las llegadas o si ya es uno solo
    espera_con_uno_menos_min: Mapped[float | None] = mapped_column(Float)
    supuestos: Mapped[dict[str, Any]] = mapped_column(JSON)  # RF-6 paso 3 y E1 («por validar»)

    pronostico: Mapped[Pronostico] = relationship(back_populates="dotacion")


class Alerta(Base):
    """Alerta de demanda de un centro (RF-3) o ambiental de una zona (RF-4), en una sola tabla (§5.1).

    La de demanda nace de un pronóstico (su semana es la del pronóstico); la ambiental, del MP2,5 previsto
    para un día. «Normal» no genera alerta.
    """

    __tablename__ = "alerta"
    __table_args__ = (
        CheckConstraint(
            f"(tipo = 'demanda' AND centro_id IS NOT NULL "
            f"AND pronostico_id IS NOT NULL AND zona_id IS NULL "
            f"AND fuente_ambiental IS NULL AND dia_pronosticado IS NULL "
            f"AND dia_observado IS NULL AND nivel IN ({_en(NIVELES_DEMANDA)}))"
            f" OR "
            f"(tipo = 'ambiental' AND zona_id IS NOT NULL "
            f"AND centro_id IS NULL AND pronostico_id IS NULL "
            f"AND valor_mp25 IS NOT NULL AND valor_mp25 >= 0 "
            f"AND nivel IN ({_en(NIVELES_AMBIENTALES)}) "
            f"AND ((fuente_ambiental = 'pronostico' "
            f"AND dia_pronosticado IS NOT NULL AND dia_observado IS NULL) "
            f"OR (fuente_ambiental = 'sinca' "
            f"AND dia_observado IS NOT NULL AND dia_pronosticado IS NULL)))",
            name="segun_tipo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoAlerta] = mapped_column(_enum(TipoAlerta, "tipo_alerta", 10))
    nivel: Mapped[str] = mapped_column(String(20))
    fecha_emision: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mensaje: Mapped[str] = mapped_column(Text)
    centro_id: Mapped[int | None] = mapped_column(
        ForeignKey("centro_salud.id", ondelete="CASCADE"), index=True
    )
    pronostico_id: Mapped[int | None] = mapped_column(ForeignKey("pronostico.id"))
    zona_id: Mapped[int | None] = mapped_column(ForeignKey("zona.id"), index=True)
    dia_pronosticado: Mapped[date | None] = mapped_column(Date)
    valor_mp25: Mapped[float | None] = mapped_column(Float)
    fuente_ambiental: Mapped[str | None] = mapped_column(String(12))
    dia_observado: Mapped[date | None] = mapped_column(Date)


class Notificacion(Base):
    """Aviso de una alerta a un usuario y su acuse (§5.1, RF-5, RF-15, RB-2).

    Si la cuenta se da de baja, la notificación queda sin usuario (RF-16 E2) para no perder el historial.
    """

    __tablename__ = "notificacion"
    __table_args__ = (
        UniqueConstraint("alerta_id", "usuario_id"),  # sin avisos duplicados de una misma alerta
        CheckConstraint(
            "estado <> 'confirmada' OR fecha_confirmacion IS NOT NULL", name="confirmada_con_fecha"
        ),
        CheckConstraint("estado <> 'reenviada' OR fecha_reenvio IS NOT NULL", name="reenviada_con_fecha"),
        CheckConstraint("estado <> 'escalada' OR fecha_escalamiento IS NOT NULL", name="escalada_con_fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # RF-15: el correo enlaza a /acuse/<token_acuse>; no se usa el id, que es correlativo y fácil de adivinar
    token_acuse: Mapped[str] = mapped_column(String(64), unique=True, default=nuevo_token_acuse)
    alerta_id: Mapped[int] = mapped_column(ForeignKey("alerta.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"), index=True)
    estado: Mapped[EstadoNotificacion] = mapped_column(_enum(EstadoNotificacion, "estado_notificacion", 12))
    fecha_envio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_confirmacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # RB-2: reenvío a las 24 h sin acuse y escalamiento al Subdirector a las 48 h (plazos en parametros.yaml)
    fecha_reenvio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_escalamiento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Umbrales y supuestos que ajusta el administrador (RB-3, RF-9; opción a, pendientes #31)
# ---------------------------------------------------------------------------
class UmbralCentro(Base):
    """Umbrales de atención (p75) y alerta (p90) de un centro. Los calcula RB-3; el administrador puede
    corregirlos con un motivo (RF-9). Se guarda la historia: solo uno vigente por centro."""

    __tablename__ = "umbral_centro"
    __table_args__ = (
        CheckConstraint("umbral_atencion >= 0 AND umbral_atencion <= umbral_alerta", name="orden_valido"),
        CheckConstraint("origen <> 'manual' OR motivo IS NOT NULL", name="manual_con_motivo"),
        Index(
            "uq_umbral_centro_vigente",
            "centro_id",
            unique=True,
            postgresql_where=text("vigente"),
            sqlite_where=text("vigente"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    centro_id: Mapped[int] = mapped_column(ForeignKey("centro_salud.id", ondelete="CASCADE"))
    umbral_atencion: Mapped[float] = mapped_column(Float)  # consultas por semana (percentil 75)
    umbral_alerta: Mapped[float] = mapped_column(Float)  # consultas por semana (percentil 90)
    origen: Mapped[OrigenUmbral] = mapped_column(_enum(OrigenUmbral, "origen_umbral", 10))
    anios_usados: Mapped[str | None] = mapped_column(String(40))  # p. ej. «2023–2025» (RB-3)
    motivo: Mapped[str | None] = mapped_column(Text)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ParametroAjustado(Base):
    """Supuesto de ``config/parametros.yaml`` que el administrador cambió desde la web (RF-9, opción a).

    El YAML queda como valor de partida versionado en git; las corridas leen el YAML con los ajustes vigentes
    encima (``sart.db.supuestos.parametros_vigentes``). Solo uno vigente por clave; se guarda la historia.
    """

    __tablename__ = "parametro_ajustado"
    __table_args__ = (
        Index(
            "uq_parametro_ajustado_vigente",
            "clave",
            unique=True,
            postgresql_where=text("vigente"),
            sqlite_where=text("vigente"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(100))  # ruta en el YAML, p. ej. «regla_alerta.k_margen»
    valor: Mapped[Any] = mapped_column(JSON)
    motivo: Mapped[str] = mapped_column(Text)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Corridas de tareas y cargas (RNF-M-3)
# ---------------------------------------------------------------------------
class Corrida(Base):
    """Log de cada corrida: tarea, fuente, inicio, fin, estado y mensaje. Con esto se sabe si una fuente
    falló varias veces seguidas (``ingesta.avisar_tras_fallas_seguidas``)."""

    __tablename__ = "corrida"
    __table_args__ = (
        CheckConstraint("estado = 'en_curso' OR fin IS NOT NULL", name="terminada_con_fin"),
        Index("ix_corrida_fuente_inicio", "fuente", "inicio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tarea: Mapped[str] = mapped_column(String(40))
    fuente: Mapped[str | None] = mapped_column(String(40))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[EstadoCorrida] = mapped_column(_enum(EstadoCorrida, "estado_corrida", 10))
    filas: Mapped[int | None]
    mensaje: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Auditoría (RNF-S-4)
# ---------------------------------------------------------------------------
class Auditoria(Base):
    """Registro de cambios de umbral, alertas, envíos y confirmaciones (RNF-S-4), por 12 meses
    (``auditoria.retencion_meses``). Guarda el rol del autor y no su nombre, para que sobreviva a la baja."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    autor_rol: Mapped[str | None] = mapped_column(String(20))  # «sistema» para las tareas programadas
    accion: Mapped[str] = mapped_column(String(60))
    entidad: Mapped[str] = mapped_column(String(60))
    entidad_id: Mapped[str | None] = mapped_column(String(60))
    valor_anterior: Mapped[Any | None] = mapped_column(JSON)
    valor_nuevo: Mapped[Any | None] = mapped_column(JSON)
    motivo: Mapped[str | None] = mapped_column(Text)
