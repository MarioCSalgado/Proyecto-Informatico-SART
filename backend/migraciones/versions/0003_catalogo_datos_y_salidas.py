"""Catálogo, datos de entrada, salidas y auditoría: el resto de §5.1.

CI-3, RB-5, RF-1 a RF-5, RF-9, RF-15 y RNF-S-4.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "semana_carga",
        sa.Column("anio", sa.SmallInteger(), nullable=False),
        sa.Column("semana", sa.SmallInteger(), nullable=False),
        sa.Column("centros_reportados", sa.Integer(), nullable=False),
        sa.Column("completa", sa.Boolean(), nullable=True),
        sa.Column("cargada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("semana BETWEEN 1 AND 53", name=op.f("ck_semana_carga_semana_valida")),
        sa.PrimaryKeyConstraint("anio", "semana", name=op.f("pk_semana_carga")),
    )
    op.create_table(
        "zona",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zona")),
        sa.UniqueConstraint("nombre", name=op.f("uq_zona_nombre")),
    )
    op.create_table(
        "auditoria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=True),
        sa.Column("autor_rol", sa.String(length=20), nullable=True),
        sa.Column("accion", sa.String(length=60), nullable=False),
        sa.Column("entidad", sa.String(length=60), nullable=False),
        sa.Column("entidad_id", sa.String(length=60), nullable=True),
        sa.Column("valor_anterior", sa.JSON(), nullable=True),
        sa.Column("valor_nuevo", sa.JSON(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["autor_id"], ["usuario.id"], name=op.f("fk_auditoria_autor_id_usuario"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria")),
    )
    op.create_index(op.f("ix_auditoria_fecha"), "auditoria", ["fecha"], unique=False)
    op.create_table(
        "estacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("comuna", sa.String(length=100), nullable=False),
        sa.Column("direccion", sa.String(length=200), nullable=True),
        sa.Column("zona_id", sa.Integer(), nullable=False),
        sa.Column(
            "fuente",
            sa.Enum(
                "SINCA",
                "Open-Meteo",
                name="fuente_estacion",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("codigo_sinca", sa.String(length=20), nullable=True),
        sa.Column("latitud", sa.Float(), nullable=True),
        sa.Column("longitud", sa.Float(), nullable=True),
        sa.Column("es_respaldo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["zona_id"], ["zona.id"], name=op.f("fk_estacion_zona_id_zona")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_estacion")),
        sa.UniqueConstraint("nombre", name=op.f("uq_estacion_nombre")),
    )
    op.create_index(op.f("ix_estacion_zona_id"), "estacion", ["zona_id"], unique=False)
    op.create_table(
        "centro_salud",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo_deis", sa.Integer(), nullable=False),
        sa.Column("codigo_antiguo", sa.Integer(), nullable=True),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "SAPU",
                "SAR",
                "SUR",
                "hospital",
                name="tipo_centro",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("comuna", sa.String(length=100), nullable=False),
        sa.Column("direccion", sa.String(length=200), nullable=True),
        sa.Column("latitud", sa.Float(), nullable=True),
        sa.Column("longitud", sa.Float(), nullable=True),
        sa.Column("zona_id", sa.Integer(), nullable=False),
        sa.Column("estacion_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["estacion_id"], ["estacion.id"], name=op.f("fk_centro_salud_estacion_id_estacion")
        ),
        sa.ForeignKeyConstraint(["zona_id"], ["zona.id"], name=op.f("fk_centro_salud_zona_id_zona")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_centro_salud")),
        sa.UniqueConstraint("codigo_antiguo", name=op.f("uq_centro_salud_codigo_antiguo")),
        sa.UniqueConstraint("codigo_deis", name=op.f("uq_centro_salud_codigo_deis")),
    )
    op.create_index(op.f("ix_centro_salud_estacion_id"), "centro_salud", ["estacion_id"], unique=False)
    op.create_index(op.f("ix_centro_salud_zona_id"), "centro_salud", ["zona_id"], unique=False)
    op.create_table(
        "medicion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estacion_id", sa.Integer(), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "mp25",
                "mp10",
                "temperatura_media",
                "temperatura_minima",
                "humedad",
                name="tipo_medicion",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("unidad", sa.String(length=10), nullable=False),
        sa.Column(
            "origen",
            sa.Enum(
                "observado",
                "pronostico",
                name="origen_medicion",
                native_enum=False,
                create_constraint=True,
                length=12,
            ),
            nullable=False,
        ),
        sa.Column(
            "calidad",
            sa.Enum(
                "validado",
                "preliminar",
                "no_validado",
                name="calidad_dato",
                native_enum=False,
                create_constraint=True,
                length=12,
            ),
            nullable=True,
        ),
        sa.CheckConstraint(
            "(tipo = 'mp25' AND unidad = 'µg/m³') OR (tipo = 'mp10' AND unidad = 'µg/m³')"
            " OR (tipo = 'temperatura_media' AND unidad = '°C')"
            " OR (tipo = 'temperatura_minima' AND unidad = '°C')"
            " OR (tipo = 'humedad' AND unidad = '%')",  # un solo %: Alembic lo duplica al autogenerar
            name=op.f("ck_medicion_unidad_compatible"),
        ),
        sa.CheckConstraint(
            "tipo <> 'humedad' OR valor BETWEEN 0 AND 100", name=op.f("ck_medicion_humedad_valida")
        ),
        sa.CheckConstraint(
            "tipo NOT IN ('mp25', 'mp10') OR valor >= 0", name=op.f("ck_medicion_concentracion_no_negativa")
        ),
        sa.ForeignKeyConstraint(
            ["estacion_id"],
            ["estacion.id"],
            name=op.f("fk_medicion_estacion_id_estacion"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medicion")),
        sa.UniqueConstraint(
            "estacion_id", "tipo", "origen", "fecha_hora", name=op.f("uq_medicion_estacion_id")
        ),
    )
    op.create_table(
        "consulta_semanal",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("centro_id", sa.Integer(), nullable=False),
        sa.Column("anio", sa.SmallInteger(), nullable=False),
        sa.Column("semana", sa.SmallInteger(), nullable=False),
        sa.Column("causa", sa.String(length=30), nullable=False),
        sa.Column("grupo_edad", sa.String(length=20), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.CheckConstraint("cantidad >= 0", name=op.f("ck_consulta_semanal_cantidad_no_negativa")),
        sa.CheckConstraint("semana BETWEEN 1 AND 53", name=op.f("ck_consulta_semanal_semana_valida")),
        sa.ForeignKeyConstraint(
            ["centro_id"],
            ["centro_salud.id"],
            name=op.f("fk_consulta_semanal_centro_id_centro_salud"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consulta_semanal")),
        sa.UniqueConstraint(
            "centro_id", "anio", "semana", "causa", "grupo_edad", name=op.f("uq_consulta_semanal_centro_id")
        ),
    )
    op.create_table(
        "pronostico",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("centro_id", sa.Integer(), nullable=False),
        sa.Column("anio", sa.SmallInteger(), nullable=False),
        sa.Column("semana", sa.SmallInteger(), nullable=False),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("limite_inferior", sa.Float(), nullable=False),
        sa.Column("limite_superior", sa.Float(), nullable=False),
        sa.Column("version_modelo", sa.String(length=40), nullable=False),
        sa.Column("fecha_corte", sa.Date(), nullable=False),
        sa.Column("vigente", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "limite_inferior <= valor AND valor <= limite_superior",
            name=op.f("ck_pronostico_dentro_del_intervalo"),
        ),
        sa.CheckConstraint("semana BETWEEN 1 AND 53", name=op.f("ck_pronostico_semana_valida")),
        sa.CheckConstraint("valor > 0", name=op.f("ck_pronostico_valor_positivo")),
        sa.ForeignKeyConstraint(
            ["centro_id"],
            ["centro_salud.id"],
            name=op.f("fk_pronostico_centro_id_centro_salud"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pronostico")),
    )
    op.create_index(
        "uq_pronostico_vigente",
        "pronostico",
        ["centro_id", "anio", "semana"],
        unique=True,
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    op.create_table(
        "usuario_centro",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("centro_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["centro_id"],
            ["centro_salud.id"],
            name=op.f("fk_usuario_centro_centro_id_centro_salud"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_usuario_centro_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "centro_id", name=op.f("pk_usuario_centro")),
    )
    op.create_table(
        "alerta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "demanda",
                "ambiental",
                name="tipo_alerta",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("nivel", sa.String(length=20), nullable=False),
        sa.Column("fecha_emision", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("centro_id", sa.Integer(), nullable=True),
        sa.Column("pronostico_id", sa.Integer(), nullable=True),
        sa.Column("zona_id", sa.Integer(), nullable=True),
        sa.Column("dia_pronosticado", sa.Date(), nullable=True),
        sa.Column("valor_mp25", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "(tipo = 'demanda' AND centro_id IS NOT NULL AND pronostico_id IS NOT NULL AND zona_id IS NULL"
            " AND nivel IN ('atencion', 'alerta'))"
            " OR (tipo = 'ambiental' AND zona_id IS NOT NULL AND centro_id IS NULL"
            " AND dia_pronosticado IS NOT NULL"
            " AND valor_mp25 IS NOT NULL AND valor_mp25 >= 0"
            " AND nivel IN ('sobre_la_norma', 'alerta', 'preemergencia', 'emergencia'))",
            name=op.f("ck_alerta_segun_tipo"),
        ),
        sa.ForeignKeyConstraint(
            ["centro_id"],
            ["centro_salud.id"],
            name=op.f("fk_alerta_centro_id_centro_salud"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pronostico_id"], ["pronostico.id"], name=op.f("fk_alerta_pronostico_id_pronostico")
        ),
        sa.ForeignKeyConstraint(["zona_id"], ["zona.id"], name=op.f("fk_alerta_zona_id_zona")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerta")),
    )
    op.create_index(op.f("ix_alerta_centro_id"), "alerta", ["centro_id"], unique=False)
    op.create_index(op.f("ix_alerta_zona_id"), "alerta", ["zona_id"], unique=False)
    op.create_table(
        "notificacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alerta_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column(
            "estado",
            sa.Enum(
                "enviada",
                "fallida",
                "confirmada",
                "reenviada",
                "escalada",
                name="estado_notificacion",
                native_enum=False,
                create_constraint=True,
                length=12,
            ),
            nullable=False,
        ),
        sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_confirmacion", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado <> 'confirmada' OR fecha_confirmacion IS NOT NULL",
            name=op.f("ck_notificacion_confirmada_con_fecha"),
        ),
        sa.ForeignKeyConstraint(
            ["alerta_id"], ["alerta.id"], name=op.f("fk_notificacion_alerta_id_alerta"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_notificacion_usuario_id_usuario"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notificacion")),
        sa.UniqueConstraint("alerta_id", "usuario_id", name=op.f("uq_notificacion_alerta_id")),
    )
    op.create_index(op.f("ix_notificacion_usuario_id"), "notificacion", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notificacion_usuario_id"), table_name="notificacion")
    op.drop_table("notificacion")
    op.drop_index(op.f("ix_alerta_zona_id"), table_name="alerta")
    op.drop_index(op.f("ix_alerta_centro_id"), table_name="alerta")
    op.drop_table("alerta")
    op.drop_table("usuario_centro")
    op.drop_index(
        "uq_pronostico_vigente",
        table_name="pronostico",
        postgresql_where=sa.text("vigente"),
        sqlite_where=sa.text("vigente"),
    )
    op.drop_table("pronostico")
    op.drop_table("consulta_semanal")
    op.drop_table("medicion")
    op.drop_index(op.f("ix_centro_salud_zona_id"), table_name="centro_salud")
    op.drop_index(op.f("ix_centro_salud_estacion_id"), table_name="centro_salud")
    op.drop_table("centro_salud")
    op.drop_index(op.f("ix_estacion_zona_id"), table_name="estacion")
    op.drop_table("estacion")
    op.drop_index(op.f("ix_auditoria_fecha"), table_name="auditoria")
    op.drop_table("auditoria")
    op.drop_table("zona")
    op.drop_table("semana_carga")
