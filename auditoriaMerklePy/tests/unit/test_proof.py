"""
Tests unitarios de generación y verificación de pruebas de Merkle.

Valida:
- Pruebas de ida y vuelta (generate → verify → True)
- Detección de manipulación (alterar dato → verify → False)
- Casos límite (una hoja, árbol vacío)
- Todos los índices de un árbol grande
- Property-based testing con Hypothesis
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.hashing import hash_data, combine_hashes
from app.core.merkle_tree import MerkleTree
from app.core.proof import ProofStep, generate_proof, verify_proof


# ============================================================
# Tests de ProofStep
# ============================================================

class TestProofStep:
    """Tests del dataclass ProofStep."""

    def test_create_right_step(self):
        """Crear un ProofStep con posición 'right'."""
        step = ProofStep(hash="abc123", position="right")
        assert step.hash == "abc123"
        assert step.position == "right"

    def test_create_left_step(self):
        """Crear un ProofStep con posición 'left'."""
        step = ProofStep(hash="def456", position="left")
        assert step.position == "left"

    def test_invalid_position_raises(self):
        """Posición inválida lanza ValueError."""
        with pytest.raises(ValueError, match="Posición inválida"):
            ProofStep(hash="abc", position="center")

    def test_immutability(self):
        """ProofStep es inmutable (frozen dataclass)."""
        step = ProofStep(hash="abc", position="left")
        with pytest.raises(AttributeError):
            step.hash = "new_value"

    def test_to_dict(self):
        """to_dict serializa correctamente."""
        step = ProofStep(hash="abc123", position="right")
        result = step.to_dict()
        assert result == {"hash": "abc123", "position": "right"}


# ============================================================
# Tests de generate_proof
# ============================================================

class TestGenerateProof:
    """Tests para la generación de pruebas de Merkle."""

    def test_single_leaf_empty_proof(self):
        """Árbol con 1 hoja: la prueba es vacía."""
        leaf = hash_data(b"only_leaf")
        tree = MerkleTree([leaf])
        proof = generate_proof(tree, 0)
        assert proof == []

    def test_two_leaves_proof_left(self):
        """Árbol con 2 hojas: prueba de la hoja izquierda."""
        h0 = hash_data(b"left")
        h1 = hash_data(b"right")
        tree = MerkleTree([h0, h1])

        proof = generate_proof(tree, 0)
        assert len(proof) == 1
        assert proof[0].hash == h1
        assert proof[0].position == "right"

    def test_two_leaves_proof_right(self):
        """Árbol con 2 hojas: prueba de la hoja derecha."""
        h0 = hash_data(b"left")
        h1 = hash_data(b"right")
        tree = MerkleTree([h0, h1])

        proof = generate_proof(tree, 1)
        assert len(proof) == 1
        assert proof[0].hash == h0
        assert proof[0].position == "left"

    def test_four_leaves_proof_depth(self):
        """Árbol con 4 hojas: la prueba tiene 2 pasos (log2(4))."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        for i in range(4):
            proof = generate_proof(tree, i)
            assert len(proof) == 2

    def test_eight_leaves_proof_depth(self):
        """Árbol con 8 hojas: la prueba tiene 3 pasos (log2(8))."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(8)]
        tree = MerkleTree(leaves)

        for i in range(8):
            proof = generate_proof(tree, i)
            assert len(proof) == 3

    def test_empty_tree_raises(self):
        """Generar prueba de árbol vacío lanza ValueError."""
        tree = MerkleTree()
        with pytest.raises(ValueError, match="árbol vacío"):
            generate_proof(tree, 0)

    def test_index_out_of_range_raises(self):
        """Índice fuera de rango lanza IndexError."""
        tree = MerkleTree([hash_data(b"leaf")])
        with pytest.raises(IndexError, match="fuera de rango"):
            generate_proof(tree, 5)

    def test_negative_index_raises(self):
        """Índice negativo lanza IndexError."""
        tree = MerkleTree([hash_data(b"leaf")])
        with pytest.raises(IndexError, match="fuera de rango"):
            generate_proof(tree, -1)


# ============================================================
# Tests de verify_proof (ida y vuelta)
# ============================================================

class TestVerifyProofRoundTrip:
    """Tests de ida y vuelta: generate → verify → True."""

    def test_single_leaf_verifies(self):
        """Árbol de 1 hoja: verificación exitosa."""
        leaf = hash_data(b"single")
        tree = MerkleTree([leaf])
        proof = generate_proof(tree, 0)
        assert verify_proof(leaf, proof, tree.root) is True

    def test_two_leaves_both_verify(self):
        """Árbol de 2 hojas: ambas hojas verifican."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(2)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True

    def test_four_leaves_all_verify(self):
        """Árbol de 4 hojas: todas las hojas verifican."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True

    def test_eight_leaves_all_verify(self):
        """Árbol de 8 hojas: todas las hojas verifican."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(8)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True

    def test_three_leaves_all_verify(self):
        """Árbol de 3 hojas (impar): todas las hojas verifican."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(3)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True

    def test_five_leaves_all_verify(self):
        """Árbol de 5 hojas (impar): todas las hojas verifican."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(5)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True

    def test_seven_leaves_all_verify(self):
        """Árbol de 7 hojas (impar): todas las hojas verifican."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(7)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True

    def test_large_tree_all_verify(self):
        """Árbol de 100 hojas: todas las hojas verifican."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(100)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True


# ============================================================
# Tests de detección de manipulación
# ============================================================

class TestTamperDetection:
    """Tests que demuestran la detección de manipulación."""

    def test_tampered_leaf_fails_verification(self):
        """Modificar una hoja hace que la verificación falle."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        # Generar prueba para leaf_0
        proof = generate_proof(tree, 0)

        # Intentar verificar con un hash diferente (hoja adulterada)
        tampered_hash = hash_data(b"tampered_data")
        assert verify_proof(tampered_hash, proof, tree.root) is False

    def test_tampered_root_fails_verification(self):
        """Verificar contra un root falso falla."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        proof = generate_proof(tree, 0)
        fake_root = hash_data(b"fake_root")

        assert verify_proof(leaves[0], proof, fake_root) is False

    def test_tampered_proof_step_fails(self):
        """Modificar un paso de la prueba hace que falle."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        proof = generate_proof(tree, 0)

        # Reemplazar el primer paso con un hash falso
        tampered_proof = [
            ProofStep(hash=hash_data(b"fake"), position=proof[0].position)
        ] + proof[1:]

        assert verify_proof(leaves[0], tampered_proof, tree.root) is False

    def test_swapped_proof_positions_fail(self):
        """Intercambiar la posición de un paso hace que falle."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        proof = generate_proof(tree, 0)

        # Cambiar "right" a "left" en el primer paso
        swapped_position = "left" if proof[0].position == "right" else "right"
        tampered_proof = [
            ProofStep(hash=proof[0].hash, position=swapped_position)
        ] + proof[1:]

        assert verify_proof(leaves[0], tampered_proof, tree.root) is False

    def test_removed_proof_step_fails(self):
        """Quitar un paso de la prueba hace que falle."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(8)]
        tree = MerkleTree(leaves)

        proof = generate_proof(tree, 0)
        # Quitar el último paso
        incomplete_proof = proof[:-1]

        assert verify_proof(leaves[0], incomplete_proof, tree.root) is False

    def test_extra_proof_step_fails(self):
        """Agregar un paso extra a la prueba hace que falle."""
        leaves = [hash_data(f"leaf_{i}".encode()) for i in range(4)]
        tree = MerkleTree(leaves)

        proof = generate_proof(tree, 0)
        # Agregar un paso extra
        extra_step = ProofStep(hash=hash_data(b"extra"), position="right")
        extended_proof = proof + [extra_step]

        assert verify_proof(leaves[0], extended_proof, tree.root) is False

    def test_proof_from_different_tree_fails(self):
        """Una prueba de un árbol no sirve para otro."""
        leaves1 = [hash_data(f"tree1_leaf_{i}".encode()) for i in range(4)]
        leaves2 = [hash_data(f"tree2_leaf_{i}".encode()) for i in range(4)]

        tree1 = MerkleTree(leaves1)
        tree2 = MerkleTree(leaves2)

        # Prueba generada del árbol 1
        proof_from_tree1 = generate_proof(tree1, 0)

        # Intentar verificar contra el root del árbol 2
        assert verify_proof(leaves1[0], proof_from_tree1, tree2.root) is False

    def test_empty_leaf_hash_fails(self):
        """Leaf hash vacío falla la verificación."""
        assert verify_proof("", [], hash_data(b"root")) is False

    def test_empty_expected_root_fails(self):
        """Root esperado vacío falla la verificación."""
        assert verify_proof(hash_data(b"leaf"), [], "") is False


# ============================================================
# Tests de verificación manual paso a paso
# ============================================================

class TestManualVerification:
    """Verificación manual para demostrar el funcionamiento interno."""

    def test_manual_four_leaf_tree(self):
        """Reconstrucción manual del proof de un árbol de 4 hojas."""
        h0 = hash_data(b"A")
        h1 = hash_data(b"B")
        h2 = hash_data(b"C")
        h3 = hash_data(b"D")

        tree = MerkleTree([h0, h1, h2, h3])

        # Proof para h0 (índice 0):
        # h0 está a la izquierda → hermano h1 está a la derecha
        # combine(h0, h1) = h01 → h01 está a la izquierda → hermano h23 a la derecha
        proof = generate_proof(tree, 0)

        # Verificar manualmente
        h01 = combine_hashes(h0, h1)
        h23 = combine_hashes(h2, h3)
        manual_root = combine_hashes(h01, h23)

        # El proof debe contener h1 (right) y h23 (right)
        assert proof[0] == ProofStep(hash=h1, position="right")
        assert proof[1] == ProofStep(hash=h23, position="right")

        # Verificar usando verify_proof
        assert verify_proof(h0, proof, manual_root) is True
        assert tree.root == manual_root

    def test_manual_verify_leaf_2_of_4(self):
        """Reconstrucción manual del proof para la hoja 2 de un árbol de 4."""
        h0 = hash_data(b"A")
        h1 = hash_data(b"B")
        h2 = hash_data(b"C")
        h3 = hash_data(b"D")

        tree = MerkleTree([h0, h1, h2, h3])

        # Proof para h2 (índice 2):
        # h2 está a la izquierda → hermano h3 está a la derecha
        # combine(h2, h3) = h23 → h23 está a la derecha → hermano h01 a la izquierda
        proof = generate_proof(tree, 2)

        h01 = combine_hashes(h0, h1)
        assert proof[0] == ProofStep(hash=h3, position="right")
        assert proof[1] == ProofStep(hash=h01, position="left")

        assert verify_proof(h2, proof, tree.root) is True


# ============================================================
# Property-based tests con Hypothesis
# ============================================================

hash_strategy = st.text(
    alphabet="0123456789abcdef", min_size=64, max_size=64
)


class TestProofProperties:
    """Property-based tests para proofs."""

    @given(st.lists(hash_strategy, min_size=1, max_size=32))
    @settings(max_examples=30)
    def test_all_leaves_verify_property(self, leaves):
        """Property: para cualquier árbol, todas las hojas verifican."""
        tree = MerkleTree(leaves)
        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root) is True

    @given(
        st.lists(hash_strategy, min_size=2, max_size=32),
        st.binary(min_size=1, max_size=100),
    )
    @settings(max_examples=30)
    def test_tampered_leaf_fails_property(self, leaves, tamper_data):
        """Property: una hoja adulterada nunca verifica (con alta probabilidad)."""
        tree = MerkleTree(leaves)
        proof = generate_proof(tree, 0)

        tampered = hash_data(tamper_data)
        # Solo verificar que falle si el hash es diferente al original
        if tampered != leaves[0]:
            assert verify_proof(tampered, proof, tree.root) is False
