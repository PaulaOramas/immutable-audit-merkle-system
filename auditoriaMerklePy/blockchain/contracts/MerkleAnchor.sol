// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MerkleAnchor
 * @notice Contrato para anclar Merkle Roots del sistema de auditoría.
 *
 * Cada vez que el sistema cierra un batch (grupo de logs), calcula un
 * Merkle Root y lo ancla en esta blockchain. Esto proporciona una
 * evidencia inmutable y verificable de que los datos existían en un
 * momento determinado.
 *
 * Flujo:
 *   1. Backend cierra un batch → calcula Merkle Root
 *   2. Backend llama anchorRoot(root, batchId)
 *   3. El contrato almacena {root, timestamp, batchId}
 *   4. Se emite el evento RootAnchored para indexación
 *
 * Verificación:
 *   Cualquiera puede llamar getAnchor(id) para verificar que un
 *   Merkle Root fue anclado en un momento específico.
 */
contract MerkleAnchor {

    // ============================================================
    // Estructuras
    // ============================================================

    struct Anchor {
        bytes32 merkleRoot;    // Merkle Root del batch
        uint256 timestamp;     // Timestamp del bloque (inmutable)
        string batchId;        // ID del batch en el sistema de auditoría
    }

    // ============================================================
    // Estado
    // ============================================================

    /// @notice Mapping de ID incremental → Anchor
    mapping(uint256 => Anchor) public anchors;

    /// @notice Cantidad total de anclajes realizados
    uint256 public anchorCount;

    /// @notice Dirección del owner (quien desplegó el contrato)
    address public owner;

    // ============================================================
    // Eventos
    // ============================================================

    /// @notice Emitido cuando se ancla un nuevo Merkle Root
    event RootAnchored(
        uint256 indexed id,
        bytes32 merkleRoot,
        uint256 timestamp,
        string batchId
    );

    // ============================================================
    // Modificadores
    // ============================================================

    modifier onlyOwner() {
        require(msg.sender == owner, "Solo el owner puede anclar");
        _;
    }

    // ============================================================
    // Constructor
    // ============================================================

    constructor() {
        owner = msg.sender;
    }

    // ============================================================
    // Funciones de escritura
    // ============================================================

    /**
     * @notice Ancla un Merkle Root en la blockchain.
     * @dev Solo el owner puede anclar. El timestamp se toma del bloque.
     * @param _merkleRoot Hash raíz del árbol Merkle (32 bytes)
     * @param _batchId Identificador del batch en el sistema de auditoría
     */
    function anchorRoot(
        bytes32 _merkleRoot,
        string calldata _batchId
    ) external onlyOwner {
        require(_merkleRoot != bytes32(0), "Merkle root no puede ser vacio");

        anchors[anchorCount] = Anchor(
            _merkleRoot,
            block.timestamp,
            _batchId
        );

        emit RootAnchored(anchorCount, _merkleRoot, block.timestamp, _batchId);
        anchorCount++;
    }

    // ============================================================
    // Funciones de lectura
    // ============================================================

    /**
     * @notice Obtiene un anclaje por su ID.
     * @param _id ID del anclaje (0-indexed)
     * @return merkleRoot Hash raíz del árbol Merkle
     * @return timestamp Momento del anclaje (timestamp del bloque)
     * @return batchId Identificador del batch
     */
    function getAnchor(uint256 _id)
        external
        view
        returns (bytes32 merkleRoot, uint256 timestamp, string memory batchId)
    {
        require(_id < anchorCount, "Anclaje no existe");
        Anchor memory a = anchors[_id];
        return (a.merkleRoot, a.timestamp, a.batchId);
    }

    /**
     * @notice Verifica si un Merkle Root específico fue anclado.
     * @param _merkleRoot Merkle Root a verificar
     * @return found Si el root fue encontrado
     * @return anchorId ID del anclaje (si fue encontrado)
     * @return timestamp Timestamp del anclaje (si fue encontrado)
     */
    function verifyRoot(bytes32 _merkleRoot)
        external
        view
        returns (bool found, uint256 anchorId, uint256 timestamp)
    {
        for (uint256 i = 0; i < anchorCount; i++) {
            if (anchors[i].merkleRoot == _merkleRoot) {
                return (true, i, anchors[i].timestamp);
            }
        }
        return (false, 0, 0);
    }
}
