---
type: System Architecture
title: Muncher MCP Package Versions
description: Version tracking and update pattern for local token muncher MCP packages.
tags:
  - munchers
  - mcp
  - versions
timestamp: '2026-07-18T21:46:41.106Z'
---
Local token munchers are installed via pip in user site-packages (normal site-packages not writeable).

## Update Pattern

```bash
pip install --upgrade jcodemunch-mcp jdocmunch-mcp jdatamunch-mcp
```

## Current Versions (as of 2026-07-17)

| Package | Version |
|---------|---------|
| `jcodemunch-mcp` | 1.108.133 |
| `jdocmunch-mcp` | 1.98.0 |
| `jdatamunch-mcp` | 1.19.1 |

## Roles

- **jcodemunch-mcp** — Extracts symbols from code
- **jdocmunch-mcp** — Extracts symbols from documentation
- **jdatamunch-mcp** — Extracts symbols from data files

These munchers feed the [Enrichment Pipeline](/system/deep-architecture.md) in the Deep knowledge system, allowing local preprocessing before cloud token processing.

# Roles

- **jcodemunch-mcp** — Extracts symbols from code
- **jdocmunch-mcp** — Extracts symbols from documentation
- **jdatamunch-mcp** — Extracts symbols from data files

These munchers feed the [Enrichment Pipeline](/system/deep-architecture.md) in the Deep knowledge system, allowing local preprocessing before cloud token processing.

**Runtime context:** Munchers run locally on Eddie's machines alongside [Local AI Models](/system/local-models.md) (Bonsai 27B, Qwen 2.5 3B), sharing the same GPU/CPU resources.

# Related

- [Deep Knowledge System](/system/deep-architecture.md) — Enrichment pipeline that uses these munchers
- [Local AI Models](/system/local-models.md) — Runtime context: munchers share GPU/CPU with local models
- [VSCode AI Coding Features Comparison](/research/vscode-ai-features-comparison.md) — Research confirming MCP is now industry standard; Tripp.Harness already uses MCP via munchers but needs broader MCP client support
