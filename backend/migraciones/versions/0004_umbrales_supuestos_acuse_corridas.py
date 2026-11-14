"""Umbrales por centro, supuestos ajustados, acuse y escalamiento, y log de corridas.

RB-3, RF-9 (opción a), RF-15, RB-2 y RNF-M-3. Los CHECK de notificación y el relleno de token_acuse se
escribieron a mano: Alembic no detecta CHECK nuevos en tablas que ya existen.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "corrida",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tarea", sa.String(length=40), nullable=False),
        sa.Column("fuente", sa.String(length=40), nullable=True),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "estado",
            sa.Enum(
                "en_curso",
                "exitosa",
                "fallida",
                name="estado_corrida",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("filas", sa.Integer(), nullable=True),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "estado = 'en_curso' OR fin IS NOT NULL", name=op.f("ck_corrida_terminada_con_fin")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corrida")),
    )
    op.create_index("ix_corrida_fuente_inicio", "corrida", ["fuente", "inicio"], unique=False)
    op.create_table(
        "parametro_ajustado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clave", sa.String(length=100), nullable=False),
        sa.Column("valor", sa.JSON(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=True),
        sa.Column("vigente", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["autor_id"],
            ["usuario.id"],
            name=op.f("fk_parametro_ajustado_autor_id_usuario"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parametro_ajustado")),
    )
    op.create_index(
        "uq_parametro_ajustado_vigente",
        "parametro_ajustado",
        ["clave"],
        unique=True,
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    op.create_table(
        "umbral_centro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("centro_id", sa.Integer(), nullable=False),
        sa.Column("umbral_atencion", sa.Float(), nullable=False),
        sa.Column("umbral_alerta", sa.Float(), nullable=False),
        sa.Column(
            "origen",
            sa.Enum(
                "calculado",
                "manual",
                name="origen_umbral",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("anios_usados", sa.String(length=40), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("autor_id", sa.Integer(), nullable=True),
        sa.Column("vigente", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "origen <> 'manual' OR motivo IS NOT NULL", name=op.f("ck_umbral_centro_manual_con_motivo")
        ),
        sa.CheckConstraint(
            "umbral_atencion >= 0 AND umbral_atencion <= umbral_alerta",
            name=op.f("ck_umbral_centro_orden_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["autor_id"], ["usuario.id"], name=op.f("fk_umbral_centro_autor_id_usuario"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["centro_id"],
            ["centro_salud.id"],
            name=op.f("fk_umbral_centro_centro_id_centro_salud"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_umbral_centro")),
    )
    op.create_index(
        "uq_umbral_centro_vigente",
        "umbral_centro",
        ["centro_id"],
        unique=True,
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    # token_acuse: primero nullable, se rellena en las filas que existan y después NOT NULL
    op.add_column("notificacion", sa.Column("token_acuse", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE notificacion"
        " SET token_acuse = md5(random()::text || id::text) || md5(clock_timestamp()::text)"
        " WHERE token_acuse IS NULL"
    )
    op.alter_column("notificacion", "token_acuse", nullable=False)
    op.add_column("notificacion", sa.Column("fecha_reenvio", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notificacion", sa.Column("fecha_escalamiento", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(op.f("uq_notificacion_token_acuse"), "notificacion", ["token_acuse"])
    op.create_check_constraint(
        op.f("ck_notificacion_reenviada_con_fecha"),
        "notificacion",
        "estado <> 'reenviada' OR fecha_reenvio IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_notificacion_escalada_con_fecha"),
        "notificacion",
        "estado <> 'escalada' OR fecha_escalamiento IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_notificacion_escalada_con_fecha"), "notificacion", type_="check")
    op.drop_constraint(op.f("ck_notificacion_reenviada_con_fecha"), "notificacion", type_="check")
    op.drop_constraint(op.f("uq_notificacion_token_acuse"), "notificacion", type_="unique")
    op.drop_column("notificacion", "fecha_escalamiento")
    op.drop_column("notificacion", "fecha_reenvio")
    op.drop_column("notificacion", "token_acuse")
    op.drop_index(
        "uq_umbral_centro_vigente",
        table_name="umbral_centro",
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    op.drop_table("umbral_centro")
    op.drop_index(
        "uq_parametro_ajustado_vigente",
        table_name="parametro_ajustado",
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    op.drop_table("parametro_ajustado")
    op.drop_index("ix_corrida_fuente_inicio", table_name="corrida")
    op.drop_table("corrida")
