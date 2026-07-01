# Correction & status — 2026-07-01

A one-time explainer, following the 2026-06-16 correction, covering what looked
off since and where the catalog stands now. Written alongside the SMADP and
NEXUS corrections of the same date.

## What looked off

- **The local working copy looked dormant — it wasn't.** A development machine's
  clone had fallen **15 commits behind `origin/main`** (last local commit #118,
  2026-06-11), so at a glance the project appeared to have gone quiet for three
  weeks. Origin never stopped: the nightly pipeline kept refreshing the catalog
  every day the whole time. The clone has now been fast-forwarded to
  `origin/main` (through the 2026-06-30 refresh, #148).

## Where things stand

The pipeline is healthy and current.

- **Catalog:** **9,660 agents** across **40 populated categories**, **1,020
  runnable (10.6%)**, framework coverage **1,385 / 9,660 (14.3%)** — daily
  refreshes running through 2026-06-30 (#148). Two categories (`coding`,
  `multi-agent-orchestration`) remain at cap.
- **The 06-16 items stayed fixed.** The report count still equals the published
  catalog (no pre-cap overstatement), and the incompatible Dependabot bumps
  remain deliberately handled: the **Astro 4→6 major is still deferred**
  (`@dependabot ignore`) pending a planned site framework upgrade — the one open
  engineering follow-up, and not urgent.
- **Still the shared data layer.** This catalog remains the single source of
  truth both downstream consumers read: **ONEXUS / NEXUS** (its Cortex dispatches
  to `runnable: true` agents via their MCP adapters) and **SMADP** (which syncs
  catalog agents into its safety-grading queue).

Nothing is broken or abandoned; the apparent dormancy was a stale local checkout.

---
*hand-written 2026-07-01.*
