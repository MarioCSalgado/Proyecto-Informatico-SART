"""Distingue alertas ambientales por pronóstico y por medición SINCA."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alerta",
        sa.Column("fuente_ambiental", sa.String(length=12), nullable=True),
    )
    op.add_column(
        "alerta",
        sa.Column("dia_observado", sa.Date(), nullable=True),
    )

    # Las alertas ambientales existentes fueron generadas desde pronósticos.
    op.execute(
        sa.text(
            "UPDATE alerta SET fuente_ambiental = 'pronostico' "
            "WHERE tipo = 'ambiental'"
        )
    )

    with op.batch_alter_table("alerta") as batch:
        batch.drop_constraint(op.f("ck_alerta_segun_tipo"), type_="check")
        batch.create_check_constraint(
            "segun_tipo",
            """
            (
                tipo = 'demanda'
                AND centro_id IS NOT NULL
                AND pronostico_id IS NOT NULL
                AND zona_id IS NULL
                AND fuente_ambiental IS NULL
                AND dia_pronosticado IS NULL
                AND dia_observado IS NULL
                AND nivel IN ('atencion', 'alerta')
            )
            OR
            (
                tipo = 'ambiental'
                AND zona_id IS NOT NULL
                AND centro_id IS NULL
                AND pronostico_id IS NULL
                AND valor_mp25 IS NOT NULL
                AND valor_mp25 >= 0
                AND nivel IN ('sobre_la_norma', 'alerta', 'preemergencia', 'emergencia')
                AND (
                    (
                        fuente_ambiental = 'pronostico'
                        AND dia_pronosticado IS NOT NULL
                        AND dia_observado IS NULL
                    )
                    OR
                    (
                        fuente_ambiental = 'sinca'
                        AND dia_observado IS NOT NULL
                        AND dia_pronosticado IS NULL
                    )
                )
            )
            """,
        )


def downgrade() -> None:
    with op.batch_alter_table("alerta") as batch:
        batch.drop_constraint(op.f("ck_alerta_segun_tipo"), type_="check")
        batch.create_check_constraint(
            "segun_tipo",
            """
            (
                tipo = 'demanda'
                AND centro_id IS NOT NULL
                AND pronostico_id IS NOT NULL
                AND zona_id IS NULL
                AND nivel IN ('atencion', 'alerta')
            )
            OR
            (
                tipo = 'ambiental'
                AND zona_id IS NOT NULL
                AND centro_id IS NULL
                AND dia_pronosticado IS NOT NULL
                AND valor_mp25 IS NOT NULL
                AND valor_mp25 >= 0
                AND nivel IN ('sobre_la_norma', 'alerta', 'preemergencia', 'emergencia')
            )
            """,
        )
        batch.drop_column("dia_observado")
        batch.drop_column("fuente_ambiental")