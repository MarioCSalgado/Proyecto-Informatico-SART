"""Corrida semanal: con qué se clasificó cada pronóstico y la dotación sugerida guardada.

RF-2, RF-3 y RF-6 (pendientes #39): el pronóstico guarda su nivel, el umbral vigente y el k usados; la
dotación se guarda con sus supuestos para que un ajuste posterior (RF-9) no cambie lo ya recomendado. Los
CHECK del pronóstico se escribieron a mano: Alembic no detecta CHECK nuevos en tablas que ya existen.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pronostico", sa.Column("nivel", sa.String(length=20), nullable=True))
    op.add_column("pronostico", sa.Column("umbral_id", sa.Integer(), nullable=True))
    op.add_column("pronostico", sa.Column("k_margen", sa.Float(), nullable=True))
    op.add_column("pronostico", sa.Column("valor_con_margen", sa.Float(), nullable=True))
    op.create_foreign_key(
        op.f("fk_pronostico_umbral_id_umbral_centro"), "pronostico", "umbral_centro", ["umbral_id"], ["id"]
    )
    op.create_check_constraint(
        op.f("ck_pronostico_nivel_valido"),
        "pronostico",
        "nivel IS NULL OR nivel IN ('normal', 'atencion', 'alerta')",
    )
    op.create_check_constraint(
        op.f("ck_pronostico_clasificado_con_umbral"),
        "pronostico",
        "nivel IS NULL OR (umbral_id IS NOT NULL AND k_margen IS NOT NULL AND valor_con_margen IS NOT NULL)",
    )
    op.create_table(
        "dotacion_sugerida",
        sa.Column("pronostico_id", sa.Integer(), nullable=False),
        sa.Column("profesionales", sa.Integer(), nullable=False),
        sa.Column("llegadas_hora_punta", sa.Float(), nullable=False),
        sa.Column("espera_media_min", sa.Float(), nullable=False),
        sa.Column("espera_con_uno_menos_min", sa.Float(), nullable=True),
        sa.Column("supuestos", sa.JSON(), nullable=False),
        sa.CheckConstraint("profesionales >= 1", name=op.f("ck_dotacion_sugerida_al_menos_uno")),
        sa.CheckConstraint(
            "llegadas_hora_punta >= 0 AND espera_media_min >= 0",
            name=op.f("ck_dotacion_sugerida_no_negativas"),
        ),
        sa.ForeignKeyConstraint(
            ["pronostico_id"],
            ["pronostico.id"],
            name=op.f("fk_dotacion_sugerida_pronostico_id_pronostico"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("pronostico_id", name=op.f("pk_dotacion_sugerida")),
    )


def downgrade() -> None:
    op.drop_table("dotacion_sugerida")
    op.drop_constraint(op.f("ck_pronostico_clasificado_con_umbral"), "pronostico", type_="check")
    op.drop_constraint(op.f("ck_pronostico_nivel_valido"), "pronostico", type_="check")
    op.drop_constraint(op.f("fk_pronostico_umbral_id_umbral_centro"), "pronostico", type_="foreignkey")
    op.drop_column("pronostico", "valor_con_margen")
    op.drop_column("pronostico", "k_margen")
    op.drop_column("pronostico", "umbral_id")
    op.drop_column("pronostico", "nivel")
