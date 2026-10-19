"""
Motor de hashing criptográfico.

Este módulo provee las funciones fundamentales de hashing para el sistema
de auditoría. Implementa:
- Hashing SHA-256 de datos crudos
- Serialización canónica determinista de estructuras de datos
- Hashing de log entries
- Combinación de hashes hermanos para la construcción del Merkle Tree

IMPORTANTE: La serialización canónica definida aquí es la piedra angular
del sistema. Una vez definida, NO debe modificarse, ya que cualquier cambio
invalidaría todos los hashes existentes.
"""

import hashlib
import json
from typing import Any


def hash_data(data: bytes) -> str:
    """
    Calcula el hash SHA-256 de datos crudos.

    Args:
        data: Bytes a hashear.

    Returns:
        Hash hexadecimal en lowercase (64 caracteres).

    Raises:
        TypeError: Si data no es de tipo bytes.
    """
    if not isinstance(data, bytes):
        raise TypeError(f"Se esperaba bytes, se recibió {type(data).__name__}")

    return hashlib.sha256(data).hexdigest()


def _sort_recursive(obj: Any) -> Any:
    """
    Ordena recursivamente las claves de diccionarios anidados.
    Convierte listas y otros tipos de forma consistente.

    Args:
        obj: Estructura de datos a ordenar.

    Returns:
        Estructura con diccionarios ordenados por clave.
    """
    if isinstance(obj, dict):
        return {k: _sort_recursive(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [_sort_recursive(item) for item in obj]
    else:
        return obj


def canonicalize(data: dict) -> bytes:
    """
    Serialización canónica determinista de un diccionario.

    Garantías:
    - Las claves se ordenan alfabéticamente de forma recursiva.
    - El encoding es siempre UTF-8.
    - Los separadores JSON no contienen espacios (',' y ':').
    - ensure_ascii=False para preservar caracteres Unicode.
    - sort_keys=True como doble seguridad (además del ordenamiento recursivo).

    Estas reglas NO deben cambiar una vez en producción.

    Args:
        data: Diccionario a serializar.

    Returns:
        Representación canónica en bytes UTF-8.

    Raises:
        TypeError: Si data no es un diccionario.
        ValueError: Si data está vacío.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Se esperaba dict, se recibió {type(data).__name__}")
    if not data:
        raise ValueError("El diccionario no puede estar vacío")

    sorted_data = _sort_recursive(data)

    canonical_json = json.dumps(
        sorted_data,
        separators=(",", ":"),
        ensure_ascii=False,
        sort_keys=True,
    )

    return canonical_json.encode("utf-8")


def hash_log_entry(log_data: dict) -> str:
    """
    Calcula el hash SHA-256 de un log entry usando serialización canónica.

    Este es el hash que se almacena como content_hash del log y que se
    usa como hoja en el Árbol de Merkle.

    Args:
        log_data: Diccionario con los datos del log entry.

    Returns:
        Hash hexadecimal SHA-256 del log serializado canónicamente.
    """
    canonical_bytes = canonicalize(log_data)
    return hash_data(canonical_bytes)


def combine_hashes(left: str, right: str) -> str:
    """
    Combina dos hashes hermanos para producir el hash del nodo padre.

    Esta es la operación fundamental del Árbol de Merkle.
    Concatena los dos hashes (left + right) y calcula el SHA-256
    del resultado.

    Args:
        left: Hash hexadecimal del hijo izquierdo.
        right: Hash hexadecimal del hijo derecho.

    Returns:
        Hash hexadecimal del nodo padre.

    Raises:
        ValueError: Si alguno de los hashes está vacío o no es hexadecimal válido.
    """
    if not left or not right:
        raise ValueError("Los hashes no pueden estar vacíos")

    # Validar que sean hex strings válidos
    try:
        int(left, 16)
        int(right, 16)
    except ValueError:
        raise ValueError("Los hashes deben ser cadenas hexadecimales válidas")

    combined = (left + right).encode("utf-8")
    return hash_data(combined)
