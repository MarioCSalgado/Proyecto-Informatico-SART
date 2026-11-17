"""TC-18 (envío) · El boletín del lunes llega por correo solo con cifras agregadas (RF-8, RNF-S-5).

Completa ``test_tc18_boletin_llm.py`` (la redacción y la revisión de cifras) con la tarea que lo manda:
cada jefatura recibe el de sus centros y el Subdirector el de la red (los mismos centros que ve en RF-7), una
vez por semana. El LLM se reemplaza por una función de prueba (proveedor sin elegir, pendientes #12) y el
servidor de correo por un buzón de prueba.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import (
    Auditoria,
    CentroSalud,
    DotacionSugerida,
    Estacion,
    Pronostico,
    UmbralCentro,
    Usuario,
    Zona,
)
from sart.dominio.roles import Rol
from sart.dominio.semanas import semana_epidemiologica
from sart.dominio.valores import FuenteEstacion, OrigenUmbral, TipoCentro
from sart.tareas.boletin import enviar_boletin

HOY = date(2026, 11, 16)  # lunes
ANIO, SEMANA = semana_epidemiologica(HOY)
URL = "https://sart.prueba"


class Buzon:
    def __init__(self) -> None:
        self.enviados: list[tuple[str, str, str]] = []

    def __call__(self, destinatario: str, asunto: str, cuerpo: str) -> None:
        self.enviados.append((destinatario, asunto, cuerpo))

    def para(self, correo: str) -> list[tuple[str, str, str]]:
        return [e for e in self.enviados if e[0] == correo]


@pytest.fixture
def red(motor_memoria):
    """Dos centros con pronóstico de la semana en curso y uno con pronóstico viejo (RF-3 E2)."""
    with Session(motor_memoria) as sesion:
        zona = Zona(nombre="Concepción")
        sesion.add(zona)
        sesion.flush()
        estacion = Estacion(
            nombre="Kingston College",
            comuna="Concepción",
            zona_id=zona.id,
            fuente=FuenteEstacion.SINCA,
            es_respaldo=True,
        )
        sesion.add(estacion)
        sesion.flush()

        def centro(codigo: int, nombre: str) -> CentroSalud:
            return CentroSalud(
                codigo_deis=codigo,
                nombre=nombre,
                tipo=TipoCentro.SAPU,
                comuna="Concepción",
                zona_id=zona.id,
                estacion_id=estacion.id,
            )

        lagunillas, penco, viejo = (
            centro(1, "SAPU Lagunillas"),
            centro(2, "SAPU Penco"),
            centro(3, "SAPU Viejo"),
        )
        sesion.add_all(
            [
                lagunillas,
                penco,
                viejo,
                Usuario(
                    nombre="Ana Pérez",
                    correo="ana@sart.prueba",
                    rol=Rol.JEFATURA,
                    hash_contrasena="x",
                    centros=[lagunillas],
                ),
                Usuario(
                    nombre="Luis Soto",
                    correo="luis@sart.prueba",
                    rol=Rol.JEFATURA,
                    hash_contrasena="x",
                    centros=[penco],
                ),
                Usuario(
                    nombre="Sara Díaz", correo="sara@sart.prueba", rol=Rol.SUBDIRECTOR, hash_contrasena="x"
                ),
                Usuario(
                    nombre="Admin", correo="admin@sart.prueba", rol=Rol.ADMINISTRADOR, hash_contrasena="x"
                ),
            ]
        )
        sesion.flush()

        def pronostico(
            c: CentroSalud, valor: float, sup: float, nivel: str, semana_atras: int = 0
        ) -> Pronostico:
            anio, semana = semana_epidemiologica(HOY - timedelta(weeks=semana_atras))
            umbral = UmbralCentro(
                centro_id=c.id, umbral_atencion=500, umbral_alerta=700, origen=OrigenUmbral.CALCULADO
            )
            sesion.add(umbral)
            sesion.flush()
            p = Pronostico(
                centro_id=c.id,
                anio=anio,
                semana=semana,
                valor=valor,
                limite_inferior=valor * 0.9,
                limite_superior=sup,
                version_modelo="prueba",
                fecha_corte=HOY - timedelta(days=2),
                vigente=True,
                nivel=nivel,
                umbral_id=umbral.id,
                k_margen=0.4,
                valor_con_margen=valor + 0.4 * (sup - valor) / 1.645,
            )
            sesion.add(p)
            sesion.flush()
            return p

        p1 = pronostico(lagunillas, 760, 812, "alerta")
        sesion.add(
            DotacionSugerida(
                pronostico_id=p1.id,
                profesionales=4,
                llegadas_hora_punta=9.9,
                espera_media_min=5.0,
                supuestos={},
            )
        )
        pronostico(penco, 310, 350, "normal")
        pronostico(viejo, 999, 1100, "alerta", semana_atras=3)
        sesion.commit()
    return motor_memoria


def _correr(motor, buzon: Buzon, redactor=None) -> dict[str, int]:
    with Session(motor) as sesion:
        resultado = enviar_boletin(sesion, hoy=HOY, redactor=redactor, url_base=URL, transportador=buzon)
        sesion.commit()
    return resultado


def test_tc18_cada_jefatura_recibe_solo_sus_centros_y_el_subdirector_la_red(red):
    buzon = Buzon()
    resultado = _correr(red, buzon)

    assert resultado["enviados"] == 3
    assert buzon.para("admin@sart.prueba") == []
    [(_, asunto, ana)] = buzon.para("ana@sart.prueba")
    assert f"SE {SEMANA} de {ANIO}" in asunto
    assert "SAPU Lagunillas" in ana and "760" in ana and "4 profesionales" in ana
    assert "SAPU Penco" not in ana
    [(_, _, sara)] = buzon.para("sara@sart.prueba")
    assert "De 2 centros: 1 en ALERTA" in sara
    assert "SAPU Viejo" not in sara and "999" not in sara  # pronóstico desactualizado: no entra
    assert "CC BY-NC" in sara


def test_tc18_no_se_manda_dos_veces_la_misma_semana(red):
    buzon = Buzon()
    _correr(red, buzon)
    resultado = _correr(red, buzon)
    assert resultado["enviados"] == 0
    assert resultado["ya_enviados"] == 3
    assert len(buzon.enviados) == 3
    with Session(red) as sesion:
        claves = list(
            sesion.scalars(select(Auditoria.entidad_id).where(Auditoria.accion == "enviar_boletin"))
        )
    assert len(claves) == 3
    assert not any("@" in c or "Ana" in c for c in claves)  # la auditoría no guarda nombres ni correos


def test_tc18_el_llm_no_recibe_nombres_ni_correos_y_el_saludo_se_agrega_despues(red):
    recibidos: list[str] = []

    def llm(prompt: str) -> str:
        recibidos.append(prompt)
        return f"Boletín SE {SEMANA} de {ANIO}.\nSAPU Lagunillas está en ALERTA con 760 consultas."

    buzon = Buzon()
    resultado = _correr(red, buzon, redactor=llm)

    assert recibidos
    for prompt in recibidos:
        for dato in ("Ana", "Luis", "Sara", "@"):
            assert dato not in prompt
    [(_, _, ana)] = buzon.para("ana@sart.prueba")
    assert ana.startswith("Hola Ana Pérez:")
    assert "SAPU Lagunillas está en ALERTA con 760 consultas." in ana
    assert resultado["con_llm"] >= 1


def test_tc18_si_el_llm_cambia_un_nivel_sale_la_plantilla(red):
    buzon = Buzon()
    _correr(red, buzon, redactor=lambda _: "SAPU Lagunillas está en nivel normal.")
    [(_, _, ana)] = buzon.para("ana@sart.prueba")
    assert "está en nivel normal" not in ana
    assert "SAPU Lagunillas: nivel ALERTA" in ana


def test_tc18_la_misma_lista_de_centros_llama_una_vez_al_llm(red):
    with Session(red) as sesion:
        lagunillas = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == 1))
        sesion.add(
            Usuario(
                nombre="Otra jefa",
                correo="otra@sart.prueba",
                rol=Rol.JEFATURA,
                hash_contrasena="x",
                centros=[lagunillas],
            )
        )
        sesion.commit()
    llamadas: list[str] = []
    _correr(red, Buzon(), redactor=lambda p: llamadas.append(p) or "SAPU Lagunillas en ALERTA.")
    assert len(llamadas) == 3  # Lagunillas (dos jefaturas, una llamada), Penco y la red
