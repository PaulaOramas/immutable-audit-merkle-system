"""
🛡️ Demo interactiva del Sistema de Auditoría con Árboles de Merkle
===================================================================

Este script demuestra visualmente cómo funciona el núcleo criptográfico:
1. Hashing de logs con serialización canónica
2. Construcción del Árbol de Merkle
3. Generación de pruebas criptográficas
4. Verificación de integridad
5. Detección de manipulación

Ejecutar: python demo.py
"""

from app.core.hashing import hash_data, hash_log_entry, combine_hashes, canonicalize
from app.core.merkle_tree import MerkleTree
from app.core.proof import generate_proof, verify_proof


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def demo_hashing():
    separator("1️⃣  MOTOR DE HASHING SHA-256")

    # Hash de datos crudos
    data = b"Hola Mundo"
    h = hash_data(data)
    print(f"  Dato:  {data.decode()}")
    print(f"  SHA-256: {h}")
    print(f"  Longitud: {len(h)} caracteres hex\n")

    # Serialización canónica
    print("  --- Serialización Canónica ---")
    log1 = {"user": "admin", "event": "login", "source": "app_web"}
    log2 = {"source": "app_web", "event": "login", "user": "admin"}

    canonical1 = canonicalize(log1).decode("utf-8")
    canonical2 = canonicalize(log2).decode("utf-8")

    print(f"  Log 1 (original): {log1}")
    print(f"  Log 2 (reordenado): {log2}")
    print(f"  Canónico 1: {canonical1}")
    print(f"  Canónico 2: {canonical2}")
    print(f"  ¿Iguales?  {'✅ SÍ' if canonical1 == canonical2 else '❌ NO'}")

    hash1 = hash_log_entry(log1)
    hash2 = hash_log_entry(log2)
    print(f"\n  Hash Log 1: {hash1}")
    print(f"  Hash Log 2: {hash2}")
    print(f"  ¿Mismo hash? {'✅ SÍ' if hash1 == hash2 else '❌ NO'}")


def demo_merkle_tree():
    separator("2️⃣  CONSTRUCCIÓN DEL ÁRBOL DE MERKLE")

    # Simular 4 logs de diferentes aplicaciones
    logs = [
        {"event": "login", "user": "admin", "source": "app_web", "severity": "info"},
        {"event": "file_access", "user": "juan", "source": "file_server", "severity": "warning"},
        {"event": "db_query", "user": "sistema", "source": "api_backend", "severity": "info"},
        {"event": "logout", "user": "admin", "source": "app_web", "severity": "info"},
    ]

    print("  Logs de auditoría recibidos:")
    leaf_hashes = []
    for i, log in enumerate(logs):
        h = hash_log_entry(log)
        leaf_hashes.append(h)
        print(f"    Log {i}: {log['event']:15s} | {log['user']:10s} | Hash: {h[:20]}...")

    # Construir árbol
    tree = MerkleTree(leaf_hashes)

    print(f"\n  Árbol construido:")
    print(f"    Hojas:  {tree.leaf_count}")
    print(f"    Altura: {tree.height} niveles")
    print(f"    🔑 Merkle Root: {tree.root}")

    # Visualizar niveles
    print(f"\n  Estructura del árbol (de hojas a raíz):")
    level_names = ["Hojas (logs)", "Nodos intermedios", "Raíz"]
    for i, level in enumerate(tree.levels):
        name = level_names[i] if i < len(level_names) else f"Nivel {i}"
        print(f"    Nivel {i} ({name}):")
        for j, h in enumerate(level):
            print(f"      [{j}] {h[:32]}...")

    return tree, leaf_hashes, logs


def demo_proof(tree, leaf_hashes, logs):
    separator("3️⃣  GENERACIÓN DE PRUEBA CRIPTOGRÁFICA")

    # Generar proof para el log 1 (file_access)
    target_index = 1
    target_log = logs[target_index]
    target_hash = leaf_hashes[target_index]

    print(f"  Generando prueba para Log {target_index}:")
    print(f"    Evento: {target_log['event']}")
    print(f"    Usuario: {target_log['user']}")
    print(f"    Hash: {target_hash[:32]}...")

    proof = generate_proof(tree, target_index)

    print(f"\n  Prueba de Merkle ({len(proof)} pasos):")
    for i, step in enumerate(proof):
        direction = "⬅️  izquierda" if step.position == "left" else "➡️  derecha"
        print(f"    Paso {i+1}: hermano en {direction}")
        print(f"            Hash: {step.hash[:32]}...")

    return proof, target_index


def demo_verification(tree, leaf_hashes, proof, target_index):
    separator("4️⃣  VERIFICACIÓN DE INTEGRIDAD")

    target_hash = leaf_hashes[target_index]

    # Verificación exitosa
    result = verify_proof(target_hash, proof, tree.root)
    print(f"  Verificando Log {target_index} contra el Merkle Root...")
    print(f"    Leaf hash: {target_hash[:32]}...")
    print(f"    Root:      {tree.root[:32]}...")
    print(f"    Resultado: {'✅ ÍNTEGRO — El log no ha sido alterado' if result else '❌ ALTERADO'}")


def demo_tamper_detection(tree, leaf_hashes, proof, target_index, logs):
    separator("5️⃣  DETECCIÓN DE MANIPULACIÓN")

    # Simular que alguien altera el log en la base de datos
    original_log = logs[target_index]
    tampered_log = dict(original_log)
    tampered_log["user"] = "hacker_malicioso"

    print(f"  ⚠️  Simulando alteración del Log {target_index}:")
    print(f"    Original:  user = '{original_log['user']}'")
    print(f"    Alterado:  user = '{tampered_log['user']}'")

    tampered_hash = hash_log_entry(tampered_log)
    original_hash = leaf_hashes[target_index]

    print(f"\n    Hash original: {original_hash[:32]}...")
    print(f"    Hash alterado: {tampered_hash[:32]}...")
    print(f"    ¿Hashes iguales? {'✅ SÍ' if original_hash == tampered_hash else '❌ NO — ¡Se detectó el cambio!'}")

    # Intentar verificar el log alterado con la prueba original
    result = verify_proof(tampered_hash, proof, tree.root)
    print(f"\n  Verificando el log ALTERADO con la prueba original...")
    print(f"    Resultado: {'✅ Verificado' if result else '❌ VERIFICACIÓN FALLIDA — La alteración fue detectada'}")

    # Verificar que el original sigue siendo válido
    result_original = verify_proof(original_hash, proof, tree.root)
    print(f"\n  Verificando el log ORIGINAL (control)...")
    print(f"    Resultado: {'✅ ÍNTEGRO — El original sigue verificando correctamente' if result_original else '❌ Error'}")


def demo_incremental():
    separator("6️⃣  CONSTRUCCIÓN INCREMENTAL (TIEMPO REAL)")

    print("  Simulando llegada de logs en tiempo real...\n")
    tree = MerkleTree()

    incoming_logs = [
        {"event": "startup", "source": "servidor_1"},
        {"event": "connection", "source": "db_master"},
        {"event": "query", "source": "api_gateway"},
        {"event": "cache_miss", "source": "redis_01"},
        {"event": "alert", "source": "monitor"},
    ]

    for i, log in enumerate(incoming_logs):
        h = hash_log_entry(log)
        tree.add_leaf(h)
        print(f"    ➕ Log {i+1} recibido: {log['event']:15s} | Hojas: {tree.leaf_count} | Root: {tree.root[:24]}...")

    print(f"\n  📊 Estado final del batch:")
    print(f"    Total de logs: {tree.leaf_count}")
    print(f"    Altura del árbol: {tree.height}")
    print(f"    🔑 Merkle Root: {tree.root}")

    # Verificar todos los logs
    print(f"\n  Verificando todos los logs del batch:")
    all_valid = True
    for i in range(tree.leaf_count):
        proof = generate_proof(tree, i)
        valid = verify_proof(tree.get_leaf(i), proof, tree.root)
        status = "✅" if valid else "❌"
        print(f"    Log {i+1}: {status} (proof de {len(proof)} pasos)")
        all_valid = all_valid and valid

    print(f"\n  {'✅ Todos los logs verificados correctamente' if all_valid else '❌ Hubo errores'}")


def main():
    print("\n" + "🛡️" * 20)
    print("  DEMO: Sistema de Auditoría Inmutable con Árboles de Merkle")
    print("🛡️" * 20)

    # 1. Hashing
    demo_hashing()

    # 2. Merkle Tree
    tree, leaf_hashes, logs = demo_merkle_tree()

    # 3. Proof generation
    proof, target_index = demo_proof(tree, leaf_hashes, logs)

    # 4. Verification
    demo_verification(tree, leaf_hashes, proof, target_index)

    # 5. Tamper detection
    demo_tamper_detection(tree, leaf_hashes, proof, target_index, logs)

    # 6. Incremental
    demo_incremental()

    separator("🏁  FIN DE LA DEMO")
    print("  El núcleo criptográfico funciona correctamente.")
    print("  Próximo paso: Fase 2 — Persistencia y Modelo de Datos\n")


if __name__ == "__main__":
    main()
