"""
Generación y verificación de pruebas de Merkle (Merkle Proofs).

Una prueba de Merkle permite demostrar que una hoja pertenece a un árbol
sin necesidad de revelar el árbol completo. Su complejidad es O(log n).

La prueba consiste en una lista de ProofStep, donde cada paso contiene:
- El hash del nodo hermano en ese nivel.
- La posición del hermano ("left" o "right").

Para verificar, se recalcula el hash desde la hoja hasta la raíz
aplicando cada paso de la prueba, y se compara con el root esperado.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List

from app.core.hashing import combine_hashes
from app.core.merkle_tree import MerkleTree


@dataclass(frozen=True)
class ProofStep:
    """
    Un paso en una prueba de Merkle.

    Atributos:
        hash: Hash hexadecimal del nodo hermano.
        position: Posición del hermano relativa al nodo actual.
                  "left" = el hermano está a la izquierda.
                  "right" = el hermano está a la derecha.
    """

    hash: str
    position: str  # "left" o "right"

    def __post_init__(self):
        if self.position not in ("left", "right"):
            raise ValueError(
                f"Posición inválida: '{self.position}'. "
                f"Debe ser 'left' o 'right'"
            )

    def to_dict(self) -> dict:
        """Convierte el ProofStep a diccionario (útil para serialización API)."""
        return asdict(self)


def generate_proof(tree: MerkleTree, leaf_index: int) -> List[ProofStep]:
    """
    Genera una prueba de Merkle para una hoja específica.

    Recorre el árbol desde la hoja hasta la raíz, recolectando
    el hash del hermano en cada nivel.

    Args:
        tree: Árbol de Merkle del cual generar la prueba.
        leaf_index: Índice de la hoja (0-based).

    Returns:
        Lista de ProofStep desde la hoja hasta la raíz.

    Raises:
        ValueError: Si el árbol está vacío.
        IndexError: Si el índice está fuera de rango.
    """
    if tree.root is None:
        raise ValueError("No se puede generar prueba de un árbol vacío")

    if leaf_index < 0 or leaf_index >= tree.leaf_count:
        raise IndexError(
            f"Índice {leaf_index} fuera de rango. "
            f"El árbol tiene {tree.leaf_count} hojas (0 a {tree.leaf_count - 1})"
        )

    # Árbol con una sola hoja: la prueba es vacía (la hoja es la raíz)
    if tree.leaf_count == 1:
        return []

    proof: List[ProofStep] = []
    levels = tree.levels
    current_index = leaf_index

    # Recorrer desde las hojas (nivel 0) hasta el penúltimo nivel
    for level in range(len(levels) - 1):
        current_level = levels[level]

        # Si el nivel tiene número impar, se duplicó el último nodo al construir
        level_nodes = list(current_level)
        if len(level_nodes) % 2 != 0:
            level_nodes.append(level_nodes[-1])

        # Determinar si el nodo actual es izquierdo o derecho
        if current_index % 2 == 0:
            # Nodo actual es izquierdo → hermano está a la derecha
            sibling_index = current_index + 1
            sibling_hash = level_nodes[sibling_index]
            proof.append(ProofStep(hash=sibling_hash, position="right"))
        else:
            # Nodo actual es derecho → hermano está a la izquierda
            sibling_index = current_index - 1
            sibling_hash = level_nodes[sibling_index]
            proof.append(ProofStep(hash=sibling_hash, position="left"))

        # Subir al nivel del padre
        current_index = current_index // 2

    return proof


def verify_proof(
    leaf_hash: str,
    proof: List[ProofStep],
    expected_root: str,
) -> bool:
    """
    Verifica una prueba de Merkle.

    Recalcula el hash desde la hoja hasta la raíz aplicando cada paso
    de la prueba, y compara el resultado con el root esperado.

    Esta función es ESTÁTICA: no necesita el árbol, solo los datos
    de la prueba. Esto permite verificación independiente por terceros.

    Args:
        leaf_hash: Hash de la hoja a verificar.
        proof: Lista de ProofStep que forman la prueba.
        expected_root: Merkle Root esperado.

    Returns:
        True si la prueba es válida, False en caso contrario.
    """
    if not leaf_hash or not expected_root:
        return False

    # Si la prueba está vacía, la hoja debe ser la raíz
    if not proof:
        return leaf_hash == expected_root

    current_hash = leaf_hash

    for step in proof:
        if step.position == "left":
            # El hermano está a la izquierda → combine(hermano, actual)
            current_hash = combine_hashes(step.hash, current_hash)
        else:
            # El hermano está a la derecha → combine(actual, hermano)
            current_hash = combine_hashes(current_hash, step.hash)

    return current_hash == expected_root
