#!/bin/bash
cd /d/Documentation/understory
BUNDLE_ROOT="D:/Documentation/knowledge-base" \
LLM_PROVIDER=ollama \
LLM_MODEL="qwen3.5:397b-cloud" \
pnpm --filter @understory/server mcp:stdio
