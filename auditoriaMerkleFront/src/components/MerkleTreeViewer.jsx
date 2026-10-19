/**
 * MerkleTreeViewer — Visualización interactiva del árbol Merkle.
 *
 * Dibuja el árbol completo de un batch, mostrando:
 * - Raíz (nivel más alto) en la parte superior
 * - Nodos intermedios
 * - Hojas (nivel 0) en la parte inferior con labels de log
 *
 * Soporta seleccionar una hoja para resaltar su proof path hasta la raíz.
 */
import { useState, useMemo, useEffect } from "react";
import { truncateHash } from "../utils/helpers";

/**
 * Calcula qué nodos forman el proof path desde una hoja seleccionada.
 * En un árbol Merkle binario, el sibling de (level, position) está en:
 *   position XOR 1 (si pos es par → par+1, si impar → impar-1)
 * Y el padre está en (level+1, floor(position/2)).
 */
function computeProofPath(selectedLeafPos, totalLevels, nodesMap) {
  if (selectedLeafPos === null || selectedLeafPos === undefined) return { path: [], siblings: [] };

  const path = [];    // nodes in the direct path to root
  const siblings = []; // sibling nodes used as proof

  let pos = selectedLeafPos;

  for (let level = 0; level < totalLevels; level++) {
    // Current node is in the path
    const nodeKey = `${level}-${pos}`;
    path.push(nodeKey);

    // Find sibling
    const siblingPos = pos % 2 === 0 ? pos + 1 : pos - 1;
    const siblingKey = `${level}-${siblingPos}`;
    if (nodesMap[siblingKey]) {
      siblings.push(siblingKey);
    }

    // Move to parent
    pos = Math.floor(pos / 2);
  }

  // Add the root
  path.push(`${totalLevels - 1}-0`);

  return { path, siblings };
}

export default function MerkleTreeViewer({ treeData, batchStatus }) {
  const [selectedLeaf, setSelectedLeaf] = useState(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [revealedNodeIndex, setRevealedNodeIndex] = useState(9999); // 9999 means all visible

  // Build a map of all nodes keyed by "level-position"
  const nodesMap = useMemo(() => {
    if (!treeData?.levels) return {};
    const map = {};
    Object.entries(treeData.levels).forEach(([level, nodes]) => {
      nodes.forEach((node) => {
        map[`${level}-${node.position}`] = node;
      });
    });
    return map;
  }, [treeData]);

  // Create an ordered array of nodes (bottom-up, left-to-right) for node-by-node animation
  const allNodesOrdered = useMemo(() => {
    if (!treeData?.levels) return [];
    const ordered = [];
    for (let l = 0; l < treeData.total_levels; l++) {
      const nodes = treeData.levels[l] || [];
      nodes.forEach(n => ordered.push({ level: parseInt(l), position: n.position, ...n }));
    }
    return ordered;
  }, [treeData]);

  // Handle animation stepping
  useEffect(() => {
    if (isAnimating && treeData && allNodesOrdered.length > 0) {
      if (revealedNodeIndex < allNodesOrdered.length - 1) {
        // Different speeds for leaves vs internal nodes
        const currentNode = allNodesOrdered[revealedNodeIndex + 1];
        const delay = currentNode?.level === 0 ? 150 : 400; // Faster for leaves, slower for internal combinations
        
        const timer = setTimeout(() => {
          setRevealedNodeIndex(prev => prev + 1);
        }, delay);
        return () => clearTimeout(timer);
      } else {
        // Animation finished
        const timer = setTimeout(() => setIsAnimating(false), 2000);
        return () => clearTimeout(timer);
      }
    }
  }, [isAnimating, revealedNodeIndex, treeData, allNodesOrdered]);

  // Compute proof path for selected leaf
  const { path: proofPath, siblings: proofSiblings } = useMemo(
    () => computeProofPath(selectedLeaf, treeData?.total_levels || 0, nodesMap),
    [selectedLeaf, treeData, nodesMap]
  );

  if (!treeData || !treeData.levels || treeData.total_nodes === 0) {
    return (
      <div className="merkle-tree-empty">
        <span className="icon">🌳</span>
        <p>Este batch no tiene árbol Merkle aún.</p>
        <p className="text-muted">El árbol se construye cuando el batch se cierra.</p>
      </div>
    );
  }

  const maxLevel = treeData.total_levels - 1;

  // Render levels from root (top) to leaves (bottom)
  const levelKeys = Array.from({ length: treeData.total_levels }, (_, i) => maxLevel - i);
  
  const currentNodeAnimating = allNodesOrdered[revealedNodeIndex];

  return (
    <div className="merkle-tree-viewer">
      <div className="merkle-tree-header">
        <h3 className="merkle-tree-title">
          🌳 Árbol Merkle — Batch #{treeData.batch_number}
        </h3>
        <span className={`badge badge-${batchStatus}`}>{batchStatus}</span>
      </div>

      {selectedLeaf !== null && (
        <div className="merkle-tree-proof-info">
          <span className="proof-info-label">Proof path para</span>
          <span className="proof-info-leaf">
            H(LOG-{selectedLeaf})
          </span>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setSelectedLeaf(null)}
          >
            Limpiar
          </button>
        </div>
      )}

      {/* Animation Controls */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px', flexDirection: 'column', alignItems: 'center' }}>
        <button
          className="btn btn-primary"
          onClick={() => {
            setIsAnimating(true);
            setRevealedNodeIndex(-1); // Start before the first node
          }}
          disabled={isAnimating && revealedNodeIndex < allNodesOrdered.length - 1}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}
        >
          {isAnimating && revealedNodeIndex < allNodesOrdered.length - 1 ? (
            <>⏳ Calculando Nodo {revealedNodeIndex + 1}/{allNodesOrdered.length}...</>
          ) : (
            <>▶️ Recrear Cálculo del Árbol (Paso a Paso)</>
          )}
        </button>
        
        {/* Visualizer of Computation */}
        {isAnimating && revealedNodeIndex >= 0 && revealedNodeIndex < allNodesOrdered.length && currentNodeAnimating && (
          <div style={{ 
            backgroundColor: '#1e293b', color: '#10b981', padding: '12px 24px', 
            borderRadius: '8px', fontFamily: 'monospace', fontSize: '14px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
            textAlign: 'center'
          }}>
            {(() => {
              if (currentNodeAnimating.level === 0) {
                return (
                  <span>
                    Calculando Hoja [{currentNodeAnimating.position}]: <br/> 
                    <span style={{color: '#f8fafc'}}>SHA-256( Datos del Log )</span> ➔ <span style={{color: '#fbbf24'}}>{truncateHash(currentNodeAnimating.hash_value, 8)}</span>
                  </span>
                );
              } else {
                const childLevel = treeData.levels[currentNodeAnimating.level - 1] || [];
                const leftChild = childLevel.find(n => n.position === currentNodeAnimating.position * 2);
                const rightChild = childLevel.find(n => n.position === currentNodeAnimating.position * 2 + 1) || leftChild;
                
                return (
                  <span>
                    Calculando Nivel {currentNodeAnimating.level} Nodo [{currentNodeAnimating.position}]: <br/> 
                    <span style={{color: '#94a3b8'}}>SHA-256(</span> 
                    <span style={{color: '#f8fafc', margin: '0 4px'}}>{leftChild ? truncateHash(leftChild.hash_value, 8) : '???'}</span> 
                    <span style={{color: '#94a3b8'}}>+</span> 
                    <span style={{color: '#f8fafc', margin: '0 4px'}}>{rightChild ? truncateHash(rightChild.hash_value, 8) : '???'}</span> 
                    <span style={{color: '#94a3b8'}}>)</span> ➔ 
                    <span style={{color: '#fbbf24', marginLeft: '6px'}}>{truncateHash(currentNodeAnimating.hash_value, 8)}</span>
                  </span>
                );
              }
            })()}
          </div>
        )}
      </div>

      <div className="merkle-tree-canvas">
        {levelKeys.map((level) => {
          const nodes = treeData.levels[level] || [];
          const isRoot = level === maxLevel;
          const isLeaf = level === 0;
          
          const absoluteIndexBase = allNodesOrdered.findIndex(n => n.level === level);
          
          return (
            <div key={level} className="merkle-tree-level" data-level={level}>
              <div className="merkle-level-label">
                {isRoot ? "RAÍZ" : isLeaf ? "HOJAS" : `Nivel ${level}`}
              </div>
              <div className="merkle-level-nodes">
                {nodes.map((node, i) => {
                  const nodeAbsoluteIndex = absoluteIndexBase + i;
                  const isVisible = !isAnimating || nodeAbsoluteIndex <= revealedNodeIndex;
                  
                  const nodeKey = `${level}-${node.position}`;
                  const isInPath = proofPath.includes(nodeKey);
                  const isSibling = proofSiblings.includes(nodeKey);
                  const isSelected = isLeaf && node.position === selectedLeaf;

                  let nodeClass = "merkle-node";
                  if (isRoot) nodeClass += " merkle-node--root";
                  else if (isLeaf) nodeClass += " merkle-node--leaf";
                  else nodeClass += " merkle-node--internal";

                  if (isSelected) nodeClass += " merkle-node--selected";
                  else if (isInPath) nodeClass += " merkle-node--in-path";
                  else if (isSibling) nodeClass += " merkle-node--sibling";

                  // Add pulse animation when newly revealed
                  if (isAnimating && nodeAbsoluteIndex === revealedNodeIndex) {
                    nodeClass += " pulse-highlight";
                  }

                  return (
                    <div
                      key={nodeKey}
                      className={nodeClass}
                      style={{ opacity: isVisible ? 1 : 0.1, transition: 'all 0.5s ease' }}
                      onClick={isLeaf ? () => setSelectedLeaf(
                        node.position === selectedLeaf ? null : node.position
                      ) : undefined}
                      title={node.hash_value}
                    >
                      <div className="merkle-node-label">
                        {isRoot
                          ? "ROOT"
                          : isLeaf
                            ? `H(${node.log_label || `LOG-${node.position}`})`
                            : `H${node.position}`
                        }
                      </div>
                      <div className="merkle-node-hash">
                        {truncateHash(node.hash_value, 4)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Proof path display */}
      {selectedLeaf !== null && proofSiblings.length > 0 && (
        <div className="merkle-proof-path">
          <div className="proof-path-title">
            Proof path LOG-{selectedLeaf}:
          </div>
          <div className="proof-path-steps">
            {/* Start with the leaf */}
            <span className="proof-step-hash proof-step-hash--leaf">
              {truncateHash(nodesMap[`0-${selectedLeaf}`]?.hash_value, 4)}
            </span>

            {proofSiblings.map((sibKey, i) => {
              const sibNode = nodesMap[sibKey];
              if (!sibNode) return null;

              // The parent is at the next level
              const parentLevel = sibNode.level + 1;
              const parentPos = Math.floor(sibNode.position / 2);
              const parentNode = nodesMap[`${parentLevel}-${parentPos}`];

              return (
                <span key={sibKey} className="proof-step-group">
                  <span className="proof-step-op">+</span>
                  <span className="proof-step-hash proof-step-hash--sibling">
                    {truncateHash(sibNode.hash_value, 4)}
                  </span>
                  <span className="proof-step-op">→</span>
                  <span className="proof-step-hash proof-step-hash--result">
                    {parentNode ? truncateHash(parentNode.hash_value, 4) : "?"}
                  </span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="merkle-tree-footer">
        <span className="text-muted">
          {treeData.total_nodes} nodos · {(treeData.levels[0] || []).length} hojas · {treeData.total_levels} niveles
        </span>
        {selectedLeaf === null && (
          <span className="text-muted">Haz clic en una hoja para ver su proof path</span>
        )}
      </div>
      <style>{`
        @keyframes pulseHighlight {
          0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7); border-color: #2563eb; transform: scale(1.05); }
          70% { box-shadow: 0 0 0 10px rgba(37, 99, 235, 0); transform: scale(1); }
          100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
        }
        .pulse-highlight {
          animation: pulseHighlight 1s ease-out;
        }
      `}</style>
    </div>
  );
}
