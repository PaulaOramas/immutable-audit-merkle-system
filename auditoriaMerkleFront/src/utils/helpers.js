/**
 * Funciones de utilidad comunes.
 */

/**
 * Trunca un hash para mostrar: abcdef12...7890abcd
 */
export function truncateHash(hash, chars = 8) {
  if (!hash || hash.length <= chars * 2) return hash;
  return `${hash.slice(0, chars)}...${hash.slice(-chars)}`;
}

/**
 * Formatea una fecha ISO a local.
 */
export function formatDate(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleString("es-EC", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/**
 * Mapea un status a un color CSS.
 */
export function statusColor(status) {
  switch (status) {
    case "open":
      return "var(--color-status-open)";
    case "closed":
      return "var(--color-status-closed)";
    case "anchored":
      return "var(--color-status-anchored)";
    default:
      return "var(--color-muted)";
  }
}

/**
 * Mapea integridad a color.
 */
export function integrityColor(integrity) {
  switch (integrity) {
    case "verified":
      return "var(--color-success)";
    case "mismatch":
      return "var(--color-danger)";
    case "not_anchored":
      return "var(--color-warning)";
    default:
      return "var(--color-muted)";
  }
}

/**
 * Copia texto al clipboard.
 */
export async function copyToClipboard(text) {
  await navigator.clipboard.writeText(text);
}
