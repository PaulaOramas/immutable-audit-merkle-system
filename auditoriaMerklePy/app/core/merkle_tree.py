"""
Implementación del Árbol de Merkle construido desde cero.

Un Árbol de Merkle es una estructura de datos en forma de árbol binario donde:
- Las hojas contienen los hashes de los datos originales (logs).
- Cada nodo interno contiene el hash de la concatenación de sus dos hijos.
- La raíz (Merkle Root) es un hash que resume toda la estructura.

Propiedades clave:
- Cualquier cambio en una hoja altera todos los nodos hasta la raíz.
- Se puede probar la pertenencia de una hoja con O(log n) hashes.
- Nodos impares: si un nivel tiene número impar de nodos, se duplica el último.
"""

from __future__ import annotations

from typing import List, Optional

from app.core.hashing import combine_hashes


class MerkleTree:
    """
    Árbol de Merkle construido desde cero.

    Atributos:
        leaves: Lista de hashes de las hojas (datos originales hasheados).
        levels: Todos los niveles del árbol, donde levels[0] son las hojas
                y levels[-1] es la raíz.
    """

    def __init__(self, leaves: Optional[List[str]] = None):
        """
        Construye un Árbol de Merkle a partir de una lista de hashes de hojas.

        Args:
            leaves: Lista de hashes hexadecimales. Si es None o vacía,
                    se crea un árbol vacío que puede crecer con add_leaf().

        Raises:
            TypeError: Si leaves no es una lista.
            ValueError: Si alguna hoja no es un string hexadecimal válido.
        """
        if leaves is not None and not isinstance(leaves, list):
            raise TypeError(f"Se esperaba list, se recibió {type(leaves).__name__}")

        self._leaves: List[str] = []
        self._levels: List[List[str]] = []

        if leaves:
            self._validate_hashes(leaves)
            self._leaves = list(leaves)  # Copia defensiva
            self._build_tree()

    @staticmethod
    def _validate_hashes(hashes: List[str]) -> None:
        """
        Valida que todos los elementos sean strings hexadecimales válidos.

        Args:
            hashes: Lista de strings a validar.

        Raises:
            ValueError: Si algún hash es inválido.
        """
        for i, h in enumerate(hashes):
            if not isinstance(h, str) or not h:
                raise ValueError(f"Hoja en posición {i} no es un string válido")
            try:
                int(h, 16)
            except ValueError:
                raise ValueError(
                    f"Hoja en posición {i} no es hexadecimal válido: '{h}'"
                )

    def _build_tree(self) -> None:
        """
        Construye el árbol de abajo (hojas) hacia arriba (raíz).

        Cada nivel se construye combinando pares de nodos del nivel inferior.
        Si un nivel tiene número impar de nodos, se duplica el último nodo
        para completar el par.
        """
        if not self._leaves:
            self._levels = []
            return

        # Nivel 0: las hojas
        current_level = list(self._leaves)
        self._levels = [current_level]

        # Construir niveles superiores hasta llegar a la raíz
        while len(current_level) > 1:
            next_level = []

            # Si el número de nodos es impar, duplicar el último
            if len(current_level) % 2 != 0:
                current_level.append(current_level[-1])

            # Combinar pares
            for i in range(0, len(current_level), 2):
                parent_hash = combine_hashes(current_level[i], current_level[i + 1])
                next_level.append(parent_hash)

            self._levels.append(next_level)
            current_level = next_level

    @property
    def root(self) -> Optional[str]:
        """
        Retorna el Merkle Root (hash raíz del árbol).

        Returns:
            Hash hexadecimal de la raíz, o None si el árbol está vacío.
        """
        if not self._levels:
            return None
        return self._levels[-1][0]

    @property
    def leaves(self) -> List[str]:
        """Retorna una copia de las hojas del árbol."""
        return list(self._leaves)

    @property
    def levels(self) -> List[List[str]]:
        """
        Retorna todos los niveles del árbol.

        levels[0] = hojas
        levels[-1] = [raíz]
        """
        return [list(level) for level in self._levels]

    @property
    def leaf_count(self) -> int:
        """Retorna el número de hojas en el árbol."""
        return len(self._leaves)

    @property
    def height(self) -> int:
        """
        Retorna la altura del árbol (número de niveles).
        Un árbol con una sola hoja tiene altura 1.
        """
        return len(self._levels)

    def add_leaf(self, leaf_hash: str) -> None:
        """
        Agrega una nueva hoja al árbol y lo reconstruye.

        Este método es para el batch activo (en construcción).
        Una vez que el batch se cierra, el árbol no debe modificarse.

        Args:
            leaf_hash: Hash hexadecimal de la nueva hoja.

        Raises:
            ValueError: Si el hash no es hexadecimal válido.
        """
        self._validate_hashes([leaf_hash])
        self._leaves.append(leaf_hash)
        self._build_tree()

    def get_leaf(self, index: int) -> str:
        """
        Retorna el hash de una hoja por su índice.

        Args:
            index: Índice de la hoja (0-based).

        Returns:
            Hash hexadecimal de la hoja.

        Raises:
            IndexError: Si el índice está fuera de rango.
        """
        if index < 0 or index >= len(self._leaves):
            raise IndexError(
                f"Índice {index} fuera de rango. "
                f"El árbol tiene {len(self._leaves)} hojas (0 a {len(self._leaves) - 1})"
            )
        return self._leaves[index]

    def __repr__(self) -> str:
        return (
            f"MerkleTree(leaves={self.leaf_count}, "
            f"height={self.height}, "
            f"root={self.root[:16] + '...' if self.root else 'None'})"
        )

    def __eq__(self, other: object) -> bool:
        """Dos árboles son iguales si tienen el mismo root."""
        if not isinstance(other, MerkleTree):
            return NotImplemented
        return self.root == other.root

    def __len__(self) -> int:
        """El tamaño del árbol es su número de hojas."""
        return self.leaf_count
