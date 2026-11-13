"""Modelos SQLAlchemy 2 de SART (§5.1).

Por ahora: Usuario y la aceptación de la finalidad (RF-16, RNF-S-1, RNF-S-2). Las demás entidades de §5.1 se
agregan con sus requisitos. Cada cambio aquí va con su migración en ``backend/migraciones``.

Regla que no se negocia: 0 datos de pacientes (RNF-S-5). Usuario guarda solo los datos de la cuenta (§5.3).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, MetaData, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sart.dominio.roles import Rol

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


class Usuario(Base):
    """Cuenta de una jefatura, un subdirector o un administrador (§5.1). Único dato personal del sistema."""

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    correo: Mapped[str] = mapped_column(String(254), unique=True)  # §5.1: correo único
    rol: Mapped[Rol] = mapped_column(
        # VARCHAR con CHECK en vez de un tipo ENUM de PostgreSQL: más simple de migrar y funciona en SQLite
        Enum(
            Rol,
            name="rol",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda roles: [r.value for r in roles],
        )
    )
    hash_contrasena: Mapped[str] = mapped_column(String(255))  # Argon2id (RNF-S-1)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    aceptaciones: Mapped[list[AceptacionFinalidad]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )


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
