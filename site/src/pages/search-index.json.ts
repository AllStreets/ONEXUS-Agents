import type { APIRoute } from "astro";
import { loadAllAgents, loadCategories } from "@/lib/catalog";

export const GET: APIRoute = () => {
  const cats = loadCategories().categories;
  const catNameBySlug: Record<string, string> = {};
  for (const c of cats) catNameBySlug[c.slug] = c.name;

  const categories = cats.map((c) => ({
    kind: "category" as const,
    slug: c.slug,
    name: c.name,
    description: c.description,
    href: `/catalog/${c.slug}`,
  }));

  const agents = loadAllAgents().map((a) => ({
    kind: "agent" as const,
    slug: a.slug,
    name: a.name,
    tagline: a.tagline,
    tags: a.tags,
    category: a.category,
    categoryName: catNameBySlug[a.category] ?? a.category,
    runnable: a.runnable,
    href: `/catalog/${a.category}/${a.slug}`,
  }));

  return new Response(JSON.stringify({ categories, agents }), {
    headers: { "Content-Type": "application/json" },
  });
};
