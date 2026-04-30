---
name: Agent submission
about: Add an open-source agent to the catalog
title: "agent: <category>/<slug>"
labels: ["agent-submission"]
---

## Agent

- **Category:** <!-- e.g. coding -->
- **Slug:** <!-- e.g. my-agent -->
- **Source:** <!-- GitHub URL or HF model URL -->
- **License:** <!-- SPDX identifier, e.g. Apache-2.0 -->
- **Runnable via MCP?** <!-- yes / no -->

## Why this belongs in the catalog

<!--
  One short paragraph. What does the agent do, who uses it, how is it different
  from existing entries in the same category?
-->

## Checklist

- [ ] Added `catalog/<category>/<slug>.json` matching the schema in `README.md`.
- [ ] Filename matches `slug`.
- [ ] `discovered_via` is `submission`.
- [ ] Ran `onexus-agents-validate catalog/<category>/<slug>.json` locally and it passes.
- [ ] If `runnable: true`, also added an `adapters/<slug>/` directory with `mcp.json` + `README.md`.
- [ ] I am the maintainer, or this is a public project I have no ownership claim over.

## Notes for the reviewer

<!-- Optional: anything we should know before merging. -->
