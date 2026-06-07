import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../../../catalog");

export type Author = {
  type: "user" | "org";
  handle: string;
  url: string;
};

export type Source = {
  primary: "github" | "huggingface";
  github: string | null;
  huggingface: string | null;
  homepage: string | null;
};

export type Metrics = {
  stars: number | null;
  downloads_30d: number | null;
  last_commit_at: string | null;
  first_commit_at: string | null;
  forks?: number | null;
  watchers?: number | null;
  open_issues?: number | null;
  archived?: boolean | null;
  is_fork?: boolean | null;
  is_template?: boolean | null;
  library_name?: string | null;
  pipeline_tag?: string | null;
  contributors_count?: number | null;
  releases_total?: number | null;
  latest_release_at?: string | null;
  commits_90d?: number | null;
  has_ci?: boolean | null;
  readme_length?: number | null;
  frameworks?: string[];
};

export type Benchmark = {
  name: string;
  score: number;
  as_of: string;
  source_url: string;
};

export type Agent = {
  slug: string;
  name: string;
  tagline: string;
  category: string;
  tags: string[];
  author: Author;
  source: Source;
  license: string;
  metrics: Metrics;
  benchmarks: Benchmark[];
  runnable: boolean;
  adapter_ref: string | null;
  composite_score: number;
  rank_in_category: number;
  discovered_via: "seed" | "auto" | "submission";
  first_seen_at: string;
  last_refreshed_at: string;
};

export type CategoryAnchor = {
  name: string;
  leaderboard_url: string;
  weight_share: number;
} | null;

export type Category = {
  slug: string;
  name: string;
  description: string;
  benchmark_anchor: CategoryAnchor;
  seed_keywords: string[];
  github_search_queries: string[];
  huggingface_filters: { tags: string[] };
};

export type CategoryIndex = {
  version: number;
  updated_at: string;
  categories: Category[];
};

let _categories: CategoryIndex | null = null;
let _agents: Agent[] | null = null;

export function loadCategories(): CategoryIndex {
  if (_categories) return _categories;
  const raw = fs.readFileSync(path.join(ROOT, "_categories.json"), "utf-8");
  _categories = JSON.parse(raw) as CategoryIndex;
  return _categories;
}

export function loadAllAgents(): Agent[] {
  if (_agents) return _agents;
  const out: Agent[] = [];
  for (const dirent of fs.readdirSync(ROOT, { withFileTypes: true })) {
    if (!dirent.isDirectory()) continue;
    if (dirent.name.startsWith("_")) continue;
    const dir = path.join(ROOT, dirent.name);
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith(".json")) continue;
      const raw = fs.readFileSync(path.join(dir, f), "utf-8");
      out.push(JSON.parse(raw) as Agent);
    }
  }
  _agents = out;
  return out;
}

export function agentsByCategory(slug: string): Agent[] {
  return loadAllAgents()
    .filter((a) => a.category === slug)
    .sort((a, b) => a.rank_in_category - b.rank_in_category);
}

export function categoryBySlug(slug: string): Category | undefined {
  return loadCategories().categories.find((c) => c.slug === slug);
}

export function agentBySlug(category: string, slug: string): Agent | undefined {
  return loadAllAgents().find(
    (a) => a.category === category && a.slug === slug
  );
}

export function categoryCounts(): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const a of loadAllAgents()) counts[a.category] = (counts[a.category] ?? 0) + 1;
  return counts;
}

export function totalAgentCount(): number {
  return loadAllAgents().length;
}

export function topAgents(n: number): Agent[] {
  return [...loadAllAgents()]
    .sort((a, b) => b.composite_score - a.composite_score)
    .slice(0, n);
}

export function runnableAgents(): Agent[] {
  return loadAllAgents()
    .filter((a) => a.runnable)
    .sort((a, b) => b.composite_score - a.composite_score);
}

export function runnableAgentsByAdapter(): Record<string, Agent[]> {
  const out: Record<string, Agent[]> = {};
  for (const a of runnableAgents()) {
    const key = a.adapter_ref ?? "unknown";
    (out[key] ??= []).push(a);
  }
  return out;
}

