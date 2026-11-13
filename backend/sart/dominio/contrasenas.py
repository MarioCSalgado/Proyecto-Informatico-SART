"""Contraseñas con hash Argon2id (RNF-S-1).

Se usan los parámetros por defecto de ``argon2-cffi`` (perfil de bajo uso de memoria de RFC 9106), que
siguen la recomendación de OWASP. La contraseña nunca se guarda ni se registra; solo su hash.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # Argon2id por defecto


def hashear(contrasena: str) -> str:
    """Hash Argon2id con sal aleatoria, listo para guardar en ``usuario.hash_contrasena``."""
    return _hasher.hash(contrasena)


def verificar(hash_guardado: str, contrasena: str) -> bool:
    """True si la contraseña corresponde al hash. Un hash dañado o ajeno da False, no una excepción."""
    try:
        return _hasher.verify(hash_guardado, contrasena)
    except (VerificationError, InvalidHashError):
        return False


def necesita_rehash(hash_guardado: str) -> bool:
    """True si el hash se hizo con parámetros más débiles que los actuales (se rehace al iniciar sesión)."""
    return _hasher.check_needs_rehash(hash_guardado)
