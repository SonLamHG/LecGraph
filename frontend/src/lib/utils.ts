/** Format seconds into mm:ss or hh:mm:ss */
export function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** Get color for concept importance level */
export function importanceColor(importance: string): string {
  switch (importance?.toLowerCase()) {
    case "high":
      return "#f87171";
    case "medium":
      return "#fbbf24";
    case "low":
      return "#34d399";
    default:
      return "#94a3b8";
  }
}

/** Get color for concept type */
export function conceptTypeColor(type: string): string {
  switch (type?.toLowerCase()) {
    case "theory":
      return "#a78bfa";
    case "technique":
      return "#60a5fa";
    case "tool":
      return "#34d399";
    case "application":
      return "#fbbf24";
    default:
      return "#818cf8";
  }
}
