"""RF-9, RB-3 y TC-17: configuración y auditoría a través del router de T7."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from queue import Queue
from time import monotonic, sleep

import pytest
from alembic import command
from alembic.config import Config
from conftest import SECRETO_DE_PRUEBA
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import (
    Auditoria,
    CentroSalud,
    ConsultaSemanal,
    Estacion,
    ParametroAjustado,
    Pronostico,
    UmbralCentro,
    Usuario,
    Zona,
)
from sart.db.supuestos import ajustar_parametro
from sart.db.umbrales import fijar_umbral_manual, guardar_umbrales_calculados, umbral_vigente
from sart.dominio.alerta_demanda import pronostico_con_margen
from sart.dominio.pronostico_semanal import PronosticoCentro, ResultadoPronostico
from sart.dominio.roles import Rol
from sart.dominio.valores import FuenteEstacion, TipoCentro
from sart.parametros import cargar_parametros
from sart.tareas import semanal

UMBRAL = "/administracion/umbrales/100001"
PARAMETROS = "/administracion/parametros"
HISTORIAL = "/administracion/historial"
CLAVE_K = "regla_alerta.k_margen"


def _autenticar(cliente, motor, rol):
    with Session(motor) as sesion:
        usuario = Usuario(nombre="Cuenta de prueba", correo=f"{rol}@demo.sart", rol=rol, hash_contrasena="x")
        sesion.add(usuario)
        sesion.commit()
        token = emitir_token(
            usuario_id=usuario.id, rol=rol, secreto=SECRETO_DE_PRUEBA, duracion=timedelta(minutes=5)
        )
    cliente.cookies.set(NOMBRE_COOKIE, token)
    return cliente


@pytest.fixture
def admin(cliente, motor_memoria):
    return _autenticar(cliente, motor_memoria, Rol.ADMINISTRADOR)


@pytest.fixture
def centro(motor_memoria):
    return _crear_centro(motor_memoria)


def _crear_centro(motor):
    with Session(motor) as sesion:
        zona = Zona(nombre="Concepción")
        estacion = Estacion(
            nombre="Estación de prueba",
            comuna="Concepción",
            zona=zona,
            fuente=FuenteEstacion.SINCA,
            es_respaldo=True,
        )
        centro = CentroSalud(
            codigo_deis=100001,
            nombre="SAR de prueba",
            tipo=TipoCentro.SAR,
            comuna="Concepción",
            zona=zona,
            estacion=estacion,
        )
        sesion.add(centro)
        sesion.commit()
        return centro.id


@pytest.mark.parametrize("rol", [None, Rol.JEFATURA, Rol.SUBDIRECTOR])
def test_rf9_tc09_configuracion_solo_para_administradores(cliente, motor_memoria, rol):
    if rol is not None:
        _autenticar(cliente, motor_memoria, rol)
    esperado = 401 if rol is None else 403
    assert cliente.get("/administracion/umbrales").status_code == esperado
    assert cliente.get(PARAMETROS).status_code == esperado
    assert cliente.get(HISTORIAL).status_code == esperado
    assert (
        cliente.put(
            UMBRAL, json={"umbral_atencion": 650, "umbral_alerta": 713, "motivo": "Prueba"}
        ).status_code
        == esperado
    )
    assert (
        cliente.put(f"{PARAMETROS}/{CLAVE_K}", json={"valor": 0, "motivo": "Prueba"}).status_code == esperado
    )


def test_rf9_rb3_umbrales_vigentes_y_auditoria(admin, motor_memoria, centro):
    [fila] = admin.get("/administracion/umbrales").json()
    assert fila["centro"] == {"codigo_deis": 100001, "nombre": "SAR de prueba"}
    assert fila["umbral"] is None
    with Session(motor_memoria) as sesion:
        guardar_umbrales_calculados(sesion, {centro: (600, 700)}, anios_usados="2022–2024")
        registrar_auditoria(sesion, autor=None, accion="emision_alerta", entidad="alerta")
        sesion.commit()

    [fila] = admin.get("/administracion/umbrales").json()
    assert fila["umbral"]["origen"] == "calculado"
    respuesta = admin.put(
        UMBRAL,
        json={
            "umbral_atencion": 650,
            "umbral_alerta": 713,
            "motivo": "  Revisión de demanda  ",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["umbral"]["origen"] == "manual"
    assert admin.get("/administracion/umbrales").json() == [respuesta.json()]

    with Session(motor_memoria) as sesion:
        assert guardar_umbrales_calculados(sesion, {centro: (601, 701)}, anios_usados="2023–2025") == {
            "guardados": 0,
            "manuales_respetados": 1,
        }
        assert sesion.scalar(select(func.count()).select_from(UmbralCentro)) == 2

    cambio, recalculo = admin.get(HISTORIAL).json()
    assert cambio["accion"] == "cambio_umbral"
    assert cambio["centro"]["codigo_deis"] == 100001
    assert cambio["autor_id"] is not None and cambio["autor_rol"] == "administrador"
    assert cambio["valor_anterior"]["umbral_alerta"] == 700
    assert cambio["valor_nuevo"]["umbral_alerta"] == 713
    assert cambio["motivo"] == "Revisión de demanda"
    assert recalculo["accion"] == "recalculo_umbral"
    assert recalculo["autor_rol"] == "sistema"


def test_rf9_umbrales_invalidos_y_centro_inexistente_no_guardan(admin, motor_memoria, centro):
    datos = {"umbral_atencion": 650, "umbral_alerta": 713, "motivo": "Prueba"}
    assert admin.put("/administracion/umbrales/999999", json=datos).status_code == 404
    for cambios in (
        {"motivo": " "},
        {"umbral_atencion": 800},
        {"umbral_atencion": -1},
        {"umbral_alerta": "inf"},
    ):
        assert admin.put(UMBRAL, json={**datos, **cambios}).status_code == 422
    assert (
        admin.put(
            UMBRAL,
            content='{"umbral_atencion":650,"umbral_alerta":1e309,"motivo":"Prueba"}',
            headers={"Content-Type": "application/json"},
        ).status_code
        == 422
    )
    with Session(motor_memoria) as sesion:
        assert sesion.scalar(select(func.count()).select_from(UmbralCentro)) == 0
        assert sesion.scalar(select(func.count()).select_from(Auditoria)) == 0


def test_rf9_rb3_parametros_editables_y_validaciones(admin, motor_memoria):
    respuesta = admin.get(PARAMETROS)
    assert respuesta.status_code == 200
    valores = {fila["clave"]: fila["valor"] for fila in respuesta.json()}
    assert set(valores) == set(cargar_parametros()["administracion"]["parametros_editables"])
    assert valores[CLAVE_K] == 0.4
    assert valores["dotacion.horas_funcionamiento_semana.SUR"] is None
    for clave, valor, motivo in (
        ("horarios.ingesta", 1, "Prueba"),
        (CLAVE_K, 0, " "),
        (CLAVE_K, True, "Prueba"),
        (CLAVE_K, -0.1, "Prueba"),
        ("umbrales.cuantil_alerta", 0.7, "Prueba"),
        ("umbrales.cuantil_atencion", 0, "Prueba"),
        ("umbrales.cuantil_alerta", 1, "Prueba"),
        ("umbrales.anios_umbral", 2.5, "Prueba"),
        ("dotacion.minutos_por_atencion", 0, "Prueba"),
        ("notificaciones.reenvio_horas", 48, "Prueba"),
    ):
        assert admin.put(f"{PARAMETROS}/{clave}", json={"valor": valor, "motivo": motivo}).status_code == 422
    assert (
        admin.put(
            f"{PARAMETROS}/{CLAVE_K}",
            content='{"valor":1e309,"motivo":"Prueba"}',
            headers={"Content-Type": "application/json"},
        ).status_code
        == 422
    )
    with Session(motor_memoria) as sesion:
        assert sesion.scalar(select(func.count()).select_from(ParametroAjustado)) == 0
        assert sesion.scalar(select(func.count()).select_from(Auditoria)) == 0

    assert (
        admin.put(
            f"{PARAMETROS}/umbrales.cuantil_alerta", json={"valor": 0.95, "motivo": "Prueba"}
        ).status_code
        == 200
    )
    assert (
        admin.put(
            f"{PARAMETROS}/umbrales.cuantil_atencion", json={"valor": 0.94, "motivo": "Prueba"}
        ).status_code
        == 200
    )
    assert (
        admin.put(
            f"{PARAMETROS}/umbrales.cuantil_alerta", json={"valor": 0.93, "motivo": "Prueba"}
        ).status_code
        == 422
    )


def test_tc17_cambiar_k_por_api_cambia_la_clasificacion_de_la_corrida(
    admin, motor_memoria, centro, monkeypatch
):
    # Fija las cifras del GLM para TC-17 y ejecuta la corrida, clasificación y persistencia reales.
    estimados = ResultadoPronostico([PronosticoCentro(centro, 700, 640, 760)])
    monkeypatch.setattr(semanal, "panel_desde_la_base", lambda *args, **kwargs: None)
    monkeypatch.setattr(semanal, "pronosticar_semana", lambda *args, **kwargs: estimados)
    assert (
        admin.put(
            UMBRAL,
            json={
                "umbral_atencion": 650,
                "umbral_alerta": 713,
                "motivo": "Umbral del caso TC-17",
            },
        ).status_code
        == 200
    )
    with Session(motor_memoria) as sesion:
        sesion.add(
            ConsultaSemanal(
                centro_id=centro,
                anio=2025,
                semana=27,
                causa="ira_alta",
                grupo_edad="1_4",
                cantidad=700,
            )
        )
        sesion.commit()
        semanal.correr_semanal(sesion, fecha=date(2025, 7, 7))

    respuesta = admin.put(f"{PARAMETROS}/{CLAVE_K}", json={"valor": 0, "motivo": "Prueba TC-17 sin margen"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"clave": CLAVE_K, "valor": 0}
    assert next(fila["valor"] for fila in admin.get(PARAMETROS).json() if fila["clave"] == CLAVE_K) == 0
    with Session(motor_memoria) as sesion:
        semanal.correr_semanal(sesion, fecha=date(2025, 7, 7))
        anterior, vigente = sesion.scalars(select(Pronostico).order_by(Pronostico.id)).all()
        assert (anterior.nivel, anterior.k_margen, anterior.vigente) == ("alerta", 0.4, False)
        assert round(anterior.valor_con_margen) == 715
        assert (vigente.nivel, vigente.k_margen, vigente.vigente) == ("atencion", 0, True)

    cambio, _ = admin.get(HISTORIAL).json()
    assert cambio["accion"] == "cambio_parametro" and cambio["entidad_id"] == CLAVE_K
    assert (cambio["valor_anterior"], cambio["valor_nuevo"]) == (0.4, 0)
    assert cambio["motivo"] == "Prueba TC-17 sin margen"


def test_rf9_tc17_rechaza_k_que_desborda_sin_guardar(admin, motor_memoria):
    respuesta = admin.put(
        f"{PARAMETROS}/{CLAVE_K}", json={"valor": 1e308, "motivo": "Valor fuera del rango numérico"}
    )
    assert respuesta.status_code == 422
    [k] = [fila for fila in admin.get(PARAMETROS).json() if fila["clave"] == CLAVE_K]
    assert k["valor"] == 0.4
    with Session(motor_memoria) as sesion:
        assert sesion.scalar(select(func.count()).select_from(ParametroAjustado)) == 0
        assert sesion.scalar(select(func.count()).select_from(Auditoria)) == 0


@pytest.mark.parametrize(
    ("pronostico", "superior", "k"),
    [(700, 760, 1e308), (1e308, 1.5e308, 3)],
    ids=["producto", "suma"],
)
def test_tc17_el_motor_rechaza_un_margen_no_finito(pronostico, superior, k):
    with pytest.raises(ValueError, match="finito"):
        pronostico_con_margen(pronostico, superior, k=k, nivel_intervalo=0.9)


@pytest.fixture
def motor_postgres_t7(crear_base_temporal):
    url = crear_base_temporal()
    destino = make_url(url)
    nombre = destino.database or ""
    assert destino.get_backend_name() == "postgresql" and nombre.startswith("sart_prueba_")
    motor = create_engine(url)
    try:
        with motor.connect() as conexion:
            assert conexion.scalar(text("SELECT current_database()")) == nombre
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["url"] = url
        command.upgrade(config, "head")
        yield motor
    finally:
        motor.dispose()


def _crear_admin(sesion):
    autor = Usuario(
        nombre="Admin de prueba", correo="admin@demo.sart", rol=Rol.ADMINISTRADOR, hash_contrasena="x"
    )
    sesion.add(autor)
    sesion.commit()
    return autor


@pytest.mark.integracion
def test_rf9_ajustes_y_auditoria_en_postgresql(motor_postgres_t7):
    """Ejercita el bloqueo y la persistencia de ajustes en el esquema migrado."""
    with Session(motor_postgres_t7) as sesion:
        autor = _crear_admin(sesion)
        ajustar_parametro(sesion, CLAVE_K, 0.5, autor=autor, motivo="Primer cambio")
        ajustar_parametro(sesion, CLAVE_K, 0, autor=autor, motivo="Segundo cambio")
        ajustes = sesion.scalars(select(ParametroAjustado).order_by(ParametroAjustado.id)).all()
        assert [(ajuste.valor, ajuste.vigente) for ajuste in ajustes] == [(0.5, False), (0, True)]
        cambios = sesion.scalars(select(Auditoria).order_by(Auditoria.id)).all()
        assert [(c.valor_anterior, c.valor_nuevo) for c in cambios] == [(0.4, 0.5), (0.5, 0)]


@pytest.mark.integracion
@pytest.mark.parametrize("segundo_manual", [True, False], ids=["manual", "recalculo"])
def test_rf9_rb3_ediciones_concurrentes_del_umbral(motor_postgres_t7, segundo_manual):
    motor = motor_postgres_t7
    centro_id = _crear_centro(motor)
    pid_segunda = Queue()

    def segunda_escritura(autor_id):
        with Session(motor) as sesion:
            sesion.execute(text("SET LOCAL lock_timeout = '10s'"))
            pid_segunda.put(sesion.scalar(text("SELECT pg_backend_pid()")))
            if segundo_manual:
                fijar_umbral_manual(
                    sesion, centro_id, 620, 720, autor=sesion.get(Usuario, autor_id), motivo="Segundo cambio"
                )
            else:
                return guardar_umbrales_calculados(sesion, {centro_id: (620, 720)}, anios_usados="2023–2025")

    with ThreadPoolExecutor(max_workers=1) as ejecutor, Session(motor) as primera:
        autor = _crear_admin(primera)
        autor_id = autor.id
        guardar_umbrales_calculados(primera, {centro_id: (600, 700)}, anios_usados="2022–2024")
        pid_primera = primera.scalar(text("SELECT pg_backend_pid()"))

        def esperar_segunda(sesion):
            nonlocal segunda
            sesion.flush()
            segunda = ejecutor.submit(segunda_escritura, autor_id)
            pid = pid_segunda.get(timeout=5)
            limite = monotonic() + 5
            with motor.connect() as observador:
                while monotonic() < limite:
                    if observador.scalar(
                        text("SELECT :primera = ANY(pg_blocking_pids(:segunda))"),
                        {"primera": pid_primera, "segunda": pid},
                    ):
                        return
                    sleep(0.01)
            pytest.fail("La segunda escritura no esperó al primer guardado.")

        segunda = None
        event.listen(primera, "before_commit", esperar_segunda, once=True)
        fijar_umbral_manual(primera, centro_id, 610, 710, autor=autor, motivo="Primer cambio")
        assert segunda is not None
        resumen = segunda.result(timeout=10)

    with Session(motor) as sesion:
        cambios = sesion.scalars(
            select(Auditoria).where(Auditoria.accion == "cambio_umbral").order_by(Auditoria.id)
        ).all()
        pares = [(c.valor_anterior["umbral_alerta"], c.valor_nuevo["umbral_alerta"]) for c in cambios]
        if segundo_manual:
            assert pares == [(700, 710), (710, 720)]
            assert umbral_vigente(sesion, centro_id).umbral_alerta == 720
        else:
            assert resumen == {"guardados": 0, "manuales_respetados": 1}
            assert pares == [(700, 710)]
            assert umbral_vigente(sesion, centro_id).umbral_alerta == 710
