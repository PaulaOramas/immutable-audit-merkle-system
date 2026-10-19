"""
Tests unitarios del Árbol de Merkle.

Valida:
- Construcción correcta con diferentes cantidades de hojas
- Manejo de nodos impares (duplicación del último)
- Propiedades del root (determinismo, sensibilidad)
- Adición incremental de hojas
- Casos límite (vacío, una hoja)
- Property-based testing con Hypothesis
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.hashing import hash_data, combine_hashes
from app.core.merkle_tree import MerkleTree


# Estrategia de Hypothesis: generar listas de hashes válidos
hash_strategy = st.text(
    alphabet="0123456789abcdef", min_size=64, max_size=64
)
hash_list_strategy = st.lists(hash_strategy, min_size=1, max_size=32)


# ============================================================
# Tests de construcción básica
# ============================================================

class TestMerkleTreeConstruction:
    """Tests de construcción del árbol."""

    def test_single_leaf(self):
        """Árbol con 1 hoja: root == hash de la hoja."""
        leaf = hash_data(b"single_leaf")
        tree = MerkleTree([leaf])

        assert tree.root == leaf
        assert tree.leaf_count == 1
        assert tree.height == 1
        assert tree.levels == [[leaf]]

    def test_two_leaves(self):
        """Árbol con 2 hojas: root == combine(h1, h2)."""
        h1 = hash_data(b"leaf_1")
        h2 = hash_data(b"leaf_2")
        tree = MerkleTree([h1, h2])

        expected_root = combine_hashes(h1, h2)
        assert tree.root == expected_root
        assert tree.leaf_count == 2
        assert tree.height == 2
        assert tree.levels[0] == [h1, h2]
        assert tree.levels[1] == [expected_root]

    def test_four_leaves(self):
        """Árbol con 4 hojas: verificar root contra cálculo manual."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        # Cálculo manual:
        #       root
        #      /    \
        #    h01     h23
        #   /  \    /  \
        #  h0  h1  h2  h3
        h01 = combine_hashes(leaves[0], leaves[1])
        h23 = combine_hashes(leaves[2], leaves[3])
        expected_root = combine_hashes(h01, h23)

        assert tree.root == expected_root
        assert tree.leaf_count == 4
        assert tree.height == 3

    def test_eight_leaves(self):
        """Árbol con 8 hojas: verificar estructura completa."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(8)]
        tree = MerkleTree(leaves)

        # Nivel 0: 8 hojas
        # Nivel 1: 4 nodos
        # Nivel 2: 2 nodos
        # Nivel 3: 1 nodo (root)
        assert tree.leaf_count == 8
        assert tree.height == 4
        assert len(tree.levels[0]) == 8
        assert len(tree.levels[1]) == 4
        assert len(tree.levels[2]) == 2
        assert len(tree.levels[3]) == 1

    def test_empty_tree(self):
        """Árbol vacío (sin hojas)."""
        tree = MerkleTree()
        assert tree.root is None
        assert tree.leaf_count == 0
        assert tree.height == 0
        assert tree.levels == []

    def test_none_leaves(self):
        """Árbol con None como leaves → vacío."""
        tree = MerkleTree(None)
        assert tree.root is None
        assert tree.leaf_count == 0

    def test_empty_list(self):
        """Árbol con lista vacía → vacío."""
        tree = MerkleTree([])
        assert tree.root is None
        assert tree.leaf_count == 0


# ============================================================
# Tests de nodos impares
# ============================================================

class TestMerkleTreeOddLeaves:
    """Tests para el manejo de número impar de hojas."""

    def test_three_leaves(self):
        """Árbol con 3 hojas: la 3ra se duplica para completar el par."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(3)]
        tree = MerkleTree(leaves)

        # Con 3 hojas, el nivel 0 tiene [h0, h1, h2]
        # Se duplica h2 → [h0, h1, h2, h2]
        # Nivel 1: [combine(h0,h1), combine(h2,h2)]
        # Nivel 2: [root]
        h01 = combine_hashes(leaves[0], leaves[1])
        h22 = combine_hashes(leaves[2], leaves[2])
        expected_root = combine_hashes(h01, h22)

        assert tree.root == expected_root
        assert tree.leaf_count == 3

    def test_five_leaves(self):
        """Árbol con 5 hojas funciona correctamente."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(5)]
        tree = MerkleTree(leaves)

        assert tree.root is not None
        assert tree.leaf_count == 5
        assert len(tree.root) == 64

    def test_seven_leaves(self):
        """Árbol con 7 hojas funciona correctamente."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(7)]
        tree = MerkleTree(leaves)

        assert tree.root is not None
        assert tree.leaf_count == 7


# ============================================================
# Tests de propiedades del root
# ============================================================

class TestMerkleRoot:
    """Tests de las propiedades del Merkle Root."""

    def test_root_determinism(self):
        """Mismas hojas siempre producen el mismo root."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree1 = MerkleTree(leaves)
        tree2 = MerkleTree(leaves)
        assert tree1.root == tree2.root

    def test_root_sensitivity_to_data_change(self):
        """Cambiar una hoja cambia el root."""
        leaves_original = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        leaves_modified = list(leaves_original)
        leaves_modified[2] = hash_data(b"leaf_modified")

        tree_original = MerkleTree(leaves_original)
        tree_modified = MerkleTree(leaves_modified)

        assert tree_original.root != tree_modified.root

    def test_root_sensitivity_to_order(self):
        """Cambiar el orden de las hojas cambia el root."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        leaves_reversed = list(reversed(leaves))

        tree1 = MerkleTree(leaves)
        tree2 = MerkleTree(leaves_reversed)

        assert tree1.root != tree2.root

    def test_root_is_valid_sha256(self):
        """El root siempre es un hash SHA-256 válido."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(6)]
        tree = MerkleTree(leaves)

        assert len(tree.root) == 64
        assert all(c in "0123456789abcdef" for c in tree.root)


# ============================================================
# Tests de add_leaf (actualización dinámica)
# ============================================================

class TestMerkleTreeAddLeaf:
    """Tests para la adición incremental de hojas."""

    def test_add_leaf_to_empty_tree(self):
        """Agregar una hoja a un árbol vacío."""
        tree = MerkleTree()
        leaf = hash_data(b"first_leaf")
        tree.add_leaf(leaf)

        assert tree.root == leaf
        assert tree.leaf_count == 1

    def test_add_leaf_changes_root(self):
        """Agregar una hoja cambia el root."""
        tree = MerkleTree([hash_data(b"leaf_0")])
        root_before = tree.root

        tree.add_leaf(hash_data(b"leaf_1"))
        assert tree.root != root_before
        assert tree.leaf_count == 2

    def test_add_leaf_equivalent_to_batch_construction(self):
        """Agregar hojas una por una produce el mismo resultado que construirlas todas juntas."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(5)]

        # Construir de una sola vez
        tree_batch = MerkleTree(leaves)

        # Construir incrementalmente
        tree_incremental = MerkleTree()
        for leaf in leaves:
            tree_incremental.add_leaf(leaf)

        assert tree_batch.root == tree_incremental.root
        assert tree_batch.leaf_count == tree_incremental.leaf_count

    def test_add_leaf_validates_input(self):
        """add_leaf rechaza hashes inválidos."""
        tree = MerkleTree()
        with pytest.raises(ValueError):
            tree.add_leaf("not_a_valid_hex!")

    def test_add_multiple_leaves_sequentially(self):
        """Agregar múltiples hojas secuencialmente."""
        tree = MerkleTree()
        for i in range(10):
            tree.add_leaf(hash_data(f"leaf_{i}".encode()))

        assert tree.leaf_count == 10
        assert tree.root is not None


# ============================================================
# Tests de acceso a hojas
# ============================================================

class TestMerkleTreeLeafAccess:
    """Tests para acceso a hojas individuales."""

    def test_get_leaf_valid_index(self):
        """Acceder a una hoja por índice válido."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        for i, expected in enumerate(leaves):
            assert tree.get_leaf(i) == expected

    def test_get_leaf_out_of_range(self):
        """Acceder a un índice fuera de rango lanza IndexError."""
        tree = MerkleTree([hash_data(b"leaf")])
        with pytest.raises(IndexError, match="fuera de rango"):
            tree.get_leaf(5)

    def test_get_leaf_negative_index(self):
        """Acceder a un índice negativo lanza IndexError."""
        tree = MerkleTree([hash_data(b"leaf")])
        with pytest.raises(IndexError, match="fuera de rango"):
            tree.get_leaf(-1)

    def test_leaves_returns_copy(self):
        """La propiedad leaves retorna una copia, no una referencia."""
        leaves = [hash_data(b"leaf")]
        tree = MerkleTree(leaves)
        returned_leaves = tree.leaves
        returned_leaves.append("extra")
        assert tree.leaf_count == 1  # No se modificó el original


# ============================================================
# Tests de validación
# ============================================================

class TestMerkleTreeValidation:
    """Tests de validación de entrada."""

    def test_invalid_type_raises(self):
        """Pasar tipo incorrecto como leaves lanza TypeError."""
        with pytest.raises(TypeError, match="Se esperaba list"):
            MerkleTree("not_a_list")

    def test_invalid_hash_in_leaves(self):
        """Hojas con hash inválido lanzan ValueError."""
        with pytest.raises(ValueError, match="no es hexadecimal válido"):
            MerkleTree(["valid_hex_a1b2c3", "not_hex!!!"])

    def test_empty_string_in_leaves(self):
        """Hojas con string vacío lanzan ValueError."""
        with pytest.raises(ValueError, match="no es un string válido"):
            MerkleTree([""])


# ============================================================
# Tests de representación y comparación
# ============================================================

class TestMerkleTreeRepr:
    """Tests de __repr__, __eq__ y __len__."""

    def test_repr(self):
        """__repr__ produce una representación legible."""
        tree = MerkleTree([hash_data(b"leaf")])
        repr_str = repr(tree)
        assert "MerkleTree" in repr_str
        assert "leaves=1" in repr_str

    def test_repr_empty(self):
        """__repr__ de árbol vacío."""
        tree = MerkleTree()
        repr_str = repr(tree)
        assert "root=None" in repr_str

    def test_equality(self):
        """Dos árboles con las mismas hojas son iguales."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree1 = MerkleTree(leaves)
        tree2 = MerkleTree(leaves)
        assert tree1 == tree2

    def test_inequality(self):
        """Dos árboles con hojas diferentes no son iguales."""
        tree1 = MerkleTree([hash_data(b"a")])
        tree2 = MerkleTree([hash_data(b"b")])
        assert tree1 != tree2

    def test_len(self):
        """__len__ retorna el número de hojas."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(5)]
        tree = MerkleTree(leaves)
        assert len(tree) == 5


# ============================================================
# Property-based tests con Hypothesis
# ============================================================

class TestMerkleTreeProperties:
    """Property-based tests."""

    @given(hash_list_strategy)
    @settings(max_examples=30)
    def test_root_determinism_property(self, leaves):
        """Property: mismas hojas → mismo root, siempre."""
        tree1 = MerkleTree(leaves)
        tree2 = MerkleTree(leaves)
        assert tree1.root == tree2.root

    @given(hash_list_strategy)
    @settings(max_examples=30)
    def test_root_is_valid_hash_property(self, leaves):
        """Property: el root siempre es un hash hex de 64 chars."""
        tree = MerkleTree(leaves)
        assert len(tree.root) == 64
        assert all(c in "0123456789abcdef" for c in tree.root)

    @given(hash_list_strategy)
    @settings(max_examples=30)
    def test_leaf_count_matches_input(self, leaves):
        """Property: leaf_count siempre coincide con el input."""
        tree = MerkleTree(leaves)
        assert tree.leaf_count == len(leaves)

    @given(hash_list_strategy)
    @settings(max_examples=30)
    def test_incremental_equals_batch(self, leaves):
        """Property: construcción incremental == batch."""
        tree_batch = MerkleTree(leaves)

        tree_inc = MerkleTree()
        for leaf in leaves:
            tree_inc.add_leaf(leaf)

        assert tree_batch.root == tree_inc.root
