---
type: System Architecture
title: Muncher MCP Package Versions
description: Version tracking and update pattern for local token muncher MCP packages.
tags:
  - munchers
  - mcp
  - versions
timestamp: '2026-07-17T13:20:44.838Z'
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
