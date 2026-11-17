
"""Histórico de emisiones de pronósticos ambientales."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pronostico_ambiental",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estacion_id", sa.Integer(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column("emitido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("unidad", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(
            ["estacion_id"], ["estacion.id"],
            name="fk_pronostico_ambiental_estacion_id_estacion",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "estacion_id",
            "tipo",
            "fecha_hora",
            "emitido_en",
        ),
        sa.CheckConstraint(
            "tipo IN ('mp25', 'mp10', 'temperatura_media', "
            "'temperatura_minima', 'humedad')",
            name="ck_pronostico_ambiental_tipo_medicion",
        ),
    )


def downgrade() -> None:
    op.drop_table("pronostico_ambiental")
