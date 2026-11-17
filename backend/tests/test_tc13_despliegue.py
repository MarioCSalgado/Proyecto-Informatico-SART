"""TC-13 · Despliegue con Docker y planificador (RNF-P-1, RNF-P-2, T11).

Lo automático de TC-13: Docker Compose levanta base, API, planificador y web dentro de 2 vCPU y 4 GB, y el
planificador corre cada tarea a la hora de ``horarios`` (RNF-M-4). La construcción desde cero y el rollback
cronometrados (≤ 15 min y ≤ 10 min) se miden a mano: ver ``docs/estado_tc.md``.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import yaml

from sart import planificador
from sart.configuracion import RAIZ_REPOSITORIO
from sart.dominio.planificador import ErrorHorarios, tareas_debidas, tareas_programadas
from sart.parametros import cargar_parametros

SANTIAGO = ZoneInfo("America/Santiago")
COMPOSE = RAIZ_REPOSITORIO / "docker-compose.yml"


def _memoria_gb(texto: str) -> float:
    texto = str(texto).lower()
    unidades = {"g": 1.0, "m": 1 / 1024}
    return float(texto[:-1]) * unidades[texto[-1]]


# ---------------------------------------------------------------------------
# Docker Compose (RNF-P-1, RNF-P-2)
# ---------------------------------------------------------------------------
def test_tc13_compose_levanta_todos_los_servicios():
    servicios = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    assert {"db", "api", "planificador", "web"} <= set(servicios)
    assert servicios["planificador"]["command"] == ["python", "-m", "sart.planificador"]
    assert servicios["api"]["build"]["dockerfile"] == "backend/Dockerfile"
    for nombre in ("api", "planificador"):
        assert "@db:5432" in servicios[nombre]["environment"]["DATABASE_URL"]


def test_tc13_rnf_p2_todo_cabe_en_2_vcpu_y_4_gb():
    servicios = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    siempre = {n: s for n, s in servicios.items() if not s.get("profiles")}
    limites = {n: s["deploy"]["resources"]["limits"] for n, s in siempre.items()}

    assert sum(float(lim["cpus"]) for lim in limites.values()) <= 2.0
    assert sum(_memoria_gb(lim["memory"]) for lim in limites.values()) <= 4.0


def test_tc13_las_imagenes_no_llevan_secretos_ni_datos():
    ignorados = (RAIZ_REPOSITORIO / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for patron in (".env", "datos", "respaldos", "referencia"):
        assert patron in ignorados


def test_tc13_nginx_deja_cargar_los_mapas_de_openstreetmap():
    """RF-12: OpenStreetMap bloquea los mapas («Access blocked») si el navegador no envía de qué sitio vienen;
    con Referrer-Policy same-origin no lo envía. strict-origin-when-cross-origin envía solo el origen."""
    nginx = (RAIZ_REPOSITORIO / "web" / "nginx.conf").read_text(encoding="utf-8")
    assert "Referrer-Policy strict-origin-when-cross-origin" in nginx
    assert "Referrer-Policy same-origin" not in nginx
    assert "no-referrer" not in nginx


# ---------------------------------------------------------------------------
# Planificador (horarios de config/parametros.yaml)
# ---------------------------------------------------------------------------
@pytest.fixture
def horarios():
    return cargar_parametros()["horarios"]


def _locales(desde: datetime, hasta: datetime, horarios) -> list[tuple[str, str]]:
    debidas = tareas_debidas(desde, hasta, horarios, "America/Santiago")
    return [(m.astimezone(SANTIAGO).strftime("%H:%M"), t.nombre) for m, t in debidas]


def test_tc13_el_lunes_corren_todas_en_orden(horarios):
    lunes = datetime(2026, 11, 16, 0, 0, tzinfo=SANTIAGO)
    tareas = [t for t in _locales(lunes, lunes + timedelta(days=1), horarios) if t[1] != "seguimiento"]

    assert tareas == [
        ("04:30", "respaldo"),
        ("05:00", "ingesta"),
        ("06:00", "pronostico"),
        ("07:00", "alerta_ambiental"),
        ("07:30", "boletin"),
    ]


def test_tc13_el_martes_no_hay_pronostico_ni_boletin(horarios):
    martes = datetime(2026, 11, 17, 0, 0, tzinfo=SANTIAGO)
    nombres = {n for _, n in _locales(martes, martes + timedelta(days=1), horarios)}
    assert nombres == {"respaldo", "ingesta", "alerta_ambiental", "seguimiento"}


def test_tc13_el_seguimiento_de_rb2_corre_cada_hora(horarios):
    lunes = datetime(2026, 11, 16, 0, 0, tzinfo=SANTIAGO)
    seguimientos = [h for h, n in _locales(lunes, lunes + timedelta(days=1), horarios) if n == "seguimiento"]
    assert len(seguimientos) == 24
    assert seguimientos[:2] == ["01:00", "02:00"]


def test_tc13_cada_minuto_corre_solo_lo_de_ese_minuto(horarios):
    lunes_0600 = datetime(2026, 11, 16, 6, 0, tzinfo=SANTIAGO)
    assert _locales(lunes_0600 - timedelta(minutes=1), lunes_0600, horarios) == [
        ("06:00", "pronostico"),
        ("06:00", "seguimiento"),
    ]
    assert _locales(lunes_0600, lunes_0600 + timedelta(minutes=1), horarios) == []


def test_tc13_horarios_invalidos_se_rechazan(horarios):
    with pytest.raises(ErrorHorarios):
        tareas_programadas({**horarios, "boletin": "09:00"})  # después de boletin_limite
    with pytest.raises(ErrorHorarios):
        tareas_programadas({**horarios, "dia_semanal": "feriado"})
    with pytest.raises(ErrorHorarios):
        tareas_programadas({**horarios, "ingesta": "5 am"})


def test_tc13_si_una_tarea_falla_las_siguientes_corren_igual(horarios, capsys):
    corridas = []

    def ejecutor(tarea):
        corridas.append(tarea.nombre)
        return 1 if tarea.nombre == "ingesta" else 0

    lunes = datetime(2026, 11, 16, 4, 0, tzinfo=SANTIAGO).astimezone(UTC)
    resultado = planificador.una_vuelta(lunes, lunes + timedelta(hours=4), ejecutor)

    assert [n for n, _ in resultado if n != "seguimiento"] == [
        "respaldo",
        "ingesta",
        "pronostico",
        "alerta_ambiental",
        "boletin",
    ]
    assert ("ingesta", 1) in resultado
    assert "ingesta: falló con código 1" in capsys.readouterr().out


def test_tc13_mostrar_lista_las_proximas_24_horas():
    texto = planificador.mostrar(datetime(2026, 11, 16, 3, 0, tzinfo=UTC))
    assert "pronostico: python -m sart.tareas semanal" in texto
    assert "ingesta: python -m sart.tareas.descarga" in texto
