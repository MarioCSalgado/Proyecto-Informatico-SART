"""Usuarios y aceptación de la finalidad (RF-16, RNF-S-1, RNF-S-2).

Revision ID: 0001
Revises:
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("correo", sa.String(length=254), nullable=False),
        sa.Column(
            "rol",
            sa.Enum(
                "jefatura",
                "subdirector",
                "administrador",
                name="rol",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("hash_contrasena", sa.String(length=255), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuario")),
        sa.UniqueConstraint("correo", name=op.f("uq_usuario_correo")),
    )
    op.create_table(
        "aceptacion_finalidad",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("version_texto", sa.String(length=20), nullable=False),
        sa.Column("aceptada_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_aceptacion_finalidad_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aceptacion_finalidad")),
        sa.UniqueConstraint(
            "usuario_id", "version_texto", name=op.f("uq_aceptacion_finalidad_usuario_id")
        ),
    )
    op.create_index(
        op.f("ix_aceptacion_finalidad_usuario_id"), "aceptacion_finalidad", ["usuario_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_aceptacion_finalidad_usuario_id"), table_name="aceptacion_finalidad")
    op.drop_table("aceptacion_finalidad")
    op.drop_table("usuario")
