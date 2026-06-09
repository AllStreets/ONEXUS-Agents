import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";

// Canonical site URL. Single source of truth — JSON-LD, the sitemap,
// Open Graph tags, and robots.txt all derive from this. When the custom
// domain agents.onexus.dev gets DNS + Vercel domain config wired up,
// change SITE_URL to https://agents.onexus.dev and the entire site
// flips canonical in one commit.
export const SITE_URL = "https://onexus-agents.vercel.app";

export default defineConfig({
  site: SITE_URL,
  output: "static",
  integrations: [
    sitemap({
      // search-index.json is a 1MB data endpoint, not a navigable page.
      // Skip so crawlers don't waste budget on it.
      filter: (page) => !page.endsWith("/search-index.json"),
      changefreq: "daily",
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
