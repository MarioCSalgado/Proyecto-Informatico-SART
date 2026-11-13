"""MFA TOTP para administradores (RNF-S-1).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuario", sa.Column("mfa_secreto", sa.String(length=64), nullable=True))
    op.add_column("usuario", sa.Column("mfa_activado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("usuario", sa.Column("mfa_ultimo_paso", sa.BigInteger(), nullable=True))
    op.add_column(
        "usuario", sa.Column("mfa_intentos_fallidos", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("usuario", sa.Column("mfa_bloqueado_hasta", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("usuario", "mfa_bloqueado_hasta")
    op.drop_column("usuario", "mfa_intentos_fallidos")
    op.drop_column("usuario", "mfa_ultimo_paso")
    op.drop_column("usuario", "mfa_activado_en")
    op.drop_column("usuario", "mfa_secreto")
