"""Contraseñas con hash Argon2id (RNF-S-1)."""

from sart.dominio.contrasenas import hashear, necesita_rehash, verificar


def test_el_hash_es_argon2id_y_no_contiene_la_contrasena():
    resultado = hashear("una clave larga de prueba")

    assert resultado.startswith("$argon2id$")
    assert "una clave larga de prueba" not in resultado


def test_dos_hashes_de_la_misma_clave_son_distintos():
    """Cada hash lleva su propia sal."""
    assert hashear("misma clave de prueba") != hashear("misma clave de prueba")


def test_verifica_la_clave_correcta_y_rechaza_la_incorrecta():
    guardado = hashear("clave correcta 123")

    assert verificar(guardado, "clave correcta 123") is True
    assert verificar(guardado, "clave incorrecta 123") is False


def test_un_hash_invalido_no_lanza_error_y_no_verifica():
    assert verificar("esto no es un hash", "cualquier cosa") is False


def test_un_hash_recien_hecho_no_necesita_rehash():
    assert necesita_rehash(hashear("otra clave de prueba")) is False
