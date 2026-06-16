# Correction & status — 2026-06-16

A one-time explainer covering what drifted off track and what is now repaired,
written alongside the SMADP and NEXUS corrections of the same date.

## What went off track

- **Two dependabot PRs sat red and cluttered the runs view.** PR #115
  (`astro` 4→6) failed the type-check and PR #113 (`@astrojs/sitemap` 3.2→3.7)
  crashed the build. Both fail for the same underlying reason: this repo's
  catalog site is still on Astro 4, and these bumps require a newer Astro than
  the site code has been migrated to. They were never safe to merge as-is.
- **The README did not reflect the downstream elevation.** SMADP and NEXUS were
  rebuilt to consume this catalog more richly, but the catalog repo's own README
  did not mention that the downstream consumers had moved on.

## What is now on track

- **The incompatible bumps are handled, not merged.** The Astro 4→6 major is
  deferred (`@dependabot ignore this major version`) so it stops being
  re-proposed until a deliberate framework upgrade happens; the sitemap bump is
  closed with a note that it is blocked on that same upgrade. Dependabot is now
  clean (0 open PRs).
- **The README is updated** with a "Downstream consumers, elevated" note
  (merged via PR #125).
- **Security hardening continues in its own session** on the
  `chore/security-hardening` line; this correction deliberately did not touch
  that work to avoid conflicts.

## What to watch

- The one real follow-up here is a **deliberate Astro 4 → 5/6 upgrade** of this
  repo's catalog site, after which the sitemap bump (and the deferred Astro
  major) can land. SMADP's site already made the 4 → 5 move cleanly and can
  serve as the reference for the same migration here.
