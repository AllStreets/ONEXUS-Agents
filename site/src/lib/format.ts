export function formatStars(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 10);
}

export function relativeDays(iso: string | null, now = new Date()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const days = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "1d ago";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export function formatScore(s: number): string {
  return s.toFixed(3);
}

export function categoryGlyph(slug: string): string {
  const map: Record<string, string> = {
    coding: "code",
    "web-dev": "globe",
    "data-engineering": "database",
    "data-science-ml": "scatter-chart",
    "financial-modeling": "trending-up",
    "legal-research": "scale",
    "customer-support": "headset",
    "content-writing": "pen-tool",
    "image-generation": "image",
    "video-generation": "video",
    "audio-speech": "mic",
    translation: "languages",
    "search-rag": "search",
    "browser-automation": "compass",
    "desktop-os-automation": "monitor",
    "document-processing": "file-text",
    "email-scheduling": "mail",
    "devops-sre": "server",
    "security-pentesting": "shield",
    bioinformatics: "dna",
    "scientific-research": "flask-conical",
    "education-tutoring": "graduation-cap",
    "reasoning-math": "sigma",
    "multi-agent-orchestration": "network",
    healthcare: "heart-pulse",
    "travel-planning": "plane",
    "sales-crm": "handshake",
    marketing: "megaphone",
    "social-media": "at-sign",
    "e-commerce": "shopping-cart",
    "real-estate": "home",
    cooking: "chef-hat",
    music: "music",
    "game-playing": "gamepad",
    robotics: "bot",
    "knowledge-management": "library",
    "pdf-forms": "file-input",
    "spreadsheet-excel": "table",
    "sql-analytics": "database-zap",
    "3d-cad": "box",
  };
  return map[slug] ?? "circle";
}
