"""
Tests unitarios del motor de hashing.

Valida:
- Determinismo: mismo input → mismo hash siempre
- Sensibilidad: cambio mínimo → hash diferente
- Canonicalización: orden de claves no afecta el hash
- Canonicalización anidada: diccionarios dentro de diccionarios
- Combinación de hashes: operación base del Merkle Tree
- Property-based testing con Hypothesis
"""

import hashlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.hashing import (
    canonicalize,
    combine_hashes,
    hash_data,
    hash_log_entry,
    _sort_recursive,
)


# ============================================================
# Tests de hash_data
# ============================================================

class TestHashData:
    """Tests para la función hash_data."""

    def test_hash_known_vector(self):
        """Verifica contra un vector SHA-256 conocido."""
        # SHA-256 de "hello" es conocido
        data = b"hello"
        expected = hashlib.sha256(b"hello").hexdigest()
        assert hash_data(data) == expected

    def test_hash_empty_bytes(self):
        """SHA-256 de bytes vacíos produce un hash válido."""
        result = hash_data(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected
        assert len(result) == 64  # SHA-256 siempre produce 64 hex chars

    def test_hash_determinism(self):
        """Mismo input siempre produce el mismo hash."""
        data = b"datos de prueba para determinismo"
        hash1 = hash_data(data)
        hash2 = hash_data(data)
        assert hash1 == hash2

    def test_hash_sensitivity(self):
        """Un cambio de un solo byte produce un hash completamente diferente."""
        data1 = b"dato original"
        data2 = b"dato originam"  # Cambiado 'l' por 'm'
        hash1 = hash_data(data1)
        hash2 = hash_data(data2)
        assert hash1 != hash2

    def test_hash_output_format(self):
        """El hash es un string hexadecimal lowercase de 64 caracteres."""
        result = hash_data(b"test")
        assert len(result) == 64
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_type_error_on_string(self):
        """Lanza TypeError si se pasa un string en lugar de bytes."""
        with pytest.raises(TypeError, match="Se esperaba bytes"):
            hash_data("no soy bytes")

    def test_hash_type_error_on_int(self):
        """Lanza TypeError si se pasa un int."""
        with pytest.raises(TypeError, match="Se esperaba bytes"):
            hash_data(42)

    @given(st.binary(min_size=0, max_size=1000))
    @settings(max_examples=50)
    def test_hash_determinism_property(self, data):
        """Property test: hash_data es siempre determinista."""
        assert hash_data(data) == hash_data(data)

    @given(st.binary(min_size=1, max_size=1000))
    @settings(max_examples=50)
    def test_hash_output_length_property(self, data):
        """Property test: el output siempre tiene 64 caracteres hex."""
        result = hash_data(data)
        assert len(result) == 64


# ============================================================
# Tests de canonicalize
# ============================================================

class TestCanonicalize:
    """Tests para la serialización canónica."""

    def test_key_order_independence(self):
        """Diccionarios con mismos datos pero distinto orden → misma serialización."""
        dict1 = {"b": 1, "a": 2, "c": 3}
        dict2 = {"a": 2, "c": 3, "b": 1}
        assert canonicalize(dict1) == canonicalize(dict2)

    def test_nested_key_order_independence(self):
        """Diccionarios anidados también se ordenan recursivamente."""
        dict1 = {"outer": {"z": 1, "a": 2}, "inner": {"m": 3, "b": 4}}
        dict2 = {"inner": {"b": 4, "m": 3}, "outer": {"a": 2, "z": 1}}
        assert canonicalize(dict1) == canonicalize(dict2)

    def test_no_spaces_in_output(self):
        """La serialización no contiene espacios (separadores compactos)."""
        data = {"key": "value", "number": 42}
        result = canonicalize(data).decode("utf-8")
        assert " " not in result

    def test_utf8_encoding(self):
        """Caracteres Unicode se preservan correctamente."""
        data = {"nombre": "José", "ciudad": "Zürich"}
        result = canonicalize(data)
        decoded = result.decode("utf-8")
        assert "José" in decoded
        assert "Zürich" in decoded

    def test_deterministic_output(self):
        """La misma entrada siempre produce la misma salida."""
        data = {"event": "login", "user": "admin", "timestamp": "2026-01-01T00:00:00"}
        result1 = canonicalize(data)
        result2 = canonicalize(data)
        assert result1 == result2

    def test_list_preservation(self):
        """Las listas mantienen su orden (no se ordenan, solo los dict keys)."""
        data = {"items": [3, 1, 2]}
        result = canonicalize(data).decode("utf-8")
        assert '"items":[3,1,2]' in result

    def test_nested_list_with_dicts(self):
        """Listas que contienen diccionarios: los dicts internos se ordenan."""
        data = {"logs": [{"z": 1, "a": 2}, {"m": 3, "b": 4}]}
        result = canonicalize(data).decode("utf-8")
        # Las claves dentro de cada dict de la lista deben estar ordenadas
        assert '"a":2' in result
        assert '"z":1' in result

    def test_type_error_on_non_dict(self):
        """Lanza TypeError si no recibe un diccionario."""
        with pytest.raises(TypeError, match="Se esperaba dict"):
            canonicalize("no soy un dict")

    def test_type_error_on_list(self):
        """Lanza TypeError si recibe una lista."""
        with pytest.raises(TypeError, match="Se esperaba dict"):
            canonicalize([1, 2, 3])

    def test_value_error_on_empty_dict(self):
        """Lanza ValueError si el diccionario está vacío."""
        with pytest.raises(ValueError, match="no puede estar vacío"):
            canonicalize({})

    def test_deeply_nested_structure(self):
        """Funciona con estructuras profundamente anidadas."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "z_key": "deep_value",
                        "a_key": "another_value",
                    }
                }
            }
        }
        result = canonicalize(data).decode("utf-8")
        # a_key debe aparecer antes que z_key
        assert result.index('"a_key"') < result.index('"z_key"')


# ============================================================
# Tests de hash_log_entry
# ============================================================

class TestHashLogEntry:
    """Tests para el hashing de log entries."""

    def test_same_data_different_order_same_hash(self):
        """Logs con mismos datos pero diferente orden de claves → mismo hash."""
        log1 = {"event": "login", "user": "admin", "source": "app_a"}
        log2 = {"source": "app_a", "event": "login", "user": "admin"}
        assert hash_log_entry(log1) == hash_log_entry(log2)

    def test_different_data_different_hash(self):
        """Logs con datos diferentes → hashes diferentes."""
        log1 = {"event": "login", "user": "admin"}
        log2 = {"event": "logout", "user": "admin"}
        assert hash_log_entry(log1) != hash_log_entry(log2)

    def test_output_is_valid_sha256(self):
        """El resultado es un hash SHA-256 válido."""
        log = {"event": "test", "data": 123}
        result = hash_log_entry(log)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_manual_verification(self):
        """Verifica manualmente que hash_log_entry = hash(canonicalize(log))."""
        log = {"event": "login", "user": "admin"}
        expected = hashlib.sha256(canonicalize(log)).hexdigest()
        assert hash_log_entry(log) == expected

    def test_minimal_log(self):
        """Funciona con un log de un solo campo."""
        log = {"event": "ping"}
        result = hash_log_entry(log)
        assert len(result) == 64

    def test_complex_log(self):
        """Funciona con un log complejo con datos anidados."""
        log = {
            "event_type": "file_access",
            "severity": "warning",
            "source_app": "file_server",
            "payload": {
                "file_path": "/etc/passwd",
                "action": "read",
                "user_id": "usr_123",
                "metadata": {
                    "ip": "192.168.1.100",
                    "port": 443,
                },
            },
        }
        result = hash_log_entry(log)
        assert len(result) == 64

    @given(
        st.fixed_dictionaries({
            "event": st.text(min_size=1, max_size=50),
            "value": st.integers(),
        })
    )
    @settings(max_examples=50)
    def test_hash_log_determinism_property(self, log):
        """Property test: hash_log_entry es siempre determinista."""
        assert hash_log_entry(log) == hash_log_entry(log)


# ============================================================
# Tests de combine_hashes
# ============================================================

class TestCombineHashes:
    """Tests para la combinación de hashes hermanos."""

    def test_combine_known_values(self):
        """Verifica contra un cálculo manual."""
        h1 = hash_data(b"leaf1")
        h2 = hash_data(b"leaf2")
        expected = hashlib.sha256((h1 + h2).encode("utf-8")).hexdigest()
        assert combine_hashes(h1, h2) == expected

    def test_combine_is_order_sensitive(self):
        """combine(a, b) != combine(b, a) — el orden importa."""
        h1 = hash_data(b"left")
        h2 = hash_data(b"right")
        assert combine_hashes(h1, h2) != combine_hashes(h2, h1)

    def test_combine_determinism(self):
        """Mismos inputs siempre producen el mismo resultado."""
        h1 = hash_data(b"a")
        h2 = hash_data(b"b")
        result1 = combine_hashes(h1, h2)
        result2 = combine_hashes(h1, h2)
        assert result1 == result2

    def test_combine_output_format(self):
        """El output es un hash SHA-256 válido."""
        h1 = hash_data(b"x")
        h2 = hash_data(b"y")
        result = combine_hashes(h1, h2)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_combine_empty_left_raises(self):
        """Lanza ValueError si el hash izquierdo está vacío."""
        with pytest.raises(ValueError, match="no pueden estar vacíos"):
            combine_hashes("", hash_data(b"x"))

    def test_combine_empty_right_raises(self):
        """Lanza ValueError si el hash derecho está vacío."""
        with pytest.raises(ValueError, match="no pueden estar vacíos"):
            combine_hashes(hash_data(b"x"), "")

    def test_combine_invalid_hex_raises(self):
        """Lanza ValueError si los hashes no son hex válidos."""
        with pytest.raises(ValueError, match="hexadecimales válidas"):
            combine_hashes("not_hex!", hash_data(b"x"))

    def test_combine_with_self(self):
        """Combinar un hash consigo mismo produce un resultado válido (caso nodo impar)."""
        h = hash_data(b"solo_leaf")
        result = combine_hashes(h, h)
        assert len(result) == 64
        # Debe ser diferente al hash original
        assert result != h


# ============================================================
# Tests de _sort_recursive (función interna)
# ============================================================

class TestSortRecursive:
    """Tests para el ordenamiento recursivo interno."""

    def test_sorts_dict_keys(self):
        """Ordena las claves de un diccionario."""
        result = _sort_recursive({"c": 1, "a": 2, "b": 3})
        assert list(result.keys()) == ["a", "b", "c"]

    def test_sorts_nested_dicts(self):
        """Ordena recursivamente los diccionarios anidados."""
        data = {"outer": {"z": 1, "a": 2}}
        result = _sort_recursive(data)
        assert list(result["outer"].keys()) == ["a", "z"]

    def test_preserves_list_order(self):
        """No reordena las listas, solo ordena dicts dentro de ellas."""
        data = {"items": [3, 1, 2]}
        result = _sort_recursive(data)
        assert result["items"] == [3, 1, 2]

    def test_sorts_dicts_inside_lists(self):
        """Ordena las claves de diccionarios que están dentro de listas."""
        data = [{"z": 1, "a": 2}]
        result = _sort_recursive(data)
        assert list(result[0].keys()) == ["a", "z"]

    def test_preserves_primitives(self):
        """No modifica valores primitivos."""
        assert _sort_recursive(42) == 42
        assert _sort_recursive("hello") == "hello"
        assert _sort_recursive(True) is True
        assert _sort_recursive(None) is None
