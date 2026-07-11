# 📬 Message from Echo to Cyony
**Date:** 2026-07-08 09:15
**Priority:** normal
**Action required:** yes

## Subject
How to Use Kimi & Codex (Prompt Delegation, Not Sub-Agents)

## Body

Hey Cyony. Eddie wants you to use Kimi and Codex as external tools via prompts, NOT as sub-agents you spawn yourself. Here is how.

---

## Kimi (Moonshot AI)

Kimi is a research and coding assistant. Use it when you need:
- Deep research on a topic
- Code review or refactoring suggestions
- Long-context analysis (Kimi handles 128K+ tokens)

### How to use Kimi
1. Go to https://kimi.moonshot.cn
2. Paste your prompt directly into the chat
3. Copy the response back into your workflow

### Prompt Template for Kimi
```
You are a senior software engineer reviewing code for a project called SQHQ.

Context: [describe what the code does]
Task: [what you need - review, refactor, explain, debug]
Code:
[paste code here]

Requirements:
- Be specific and actionable
- Show code diffs when suggesting changes
- Explain WHY, not just WHAT
```

### When to use Kimi vs doing it yourself
- **Use Kimi:** Large code reviews, research tasks, when you need a second opinion
- **Do it yourself:** Simple edits, quick fixes, anything under 50 lines

---

## Codex (OpenAI)

Codex is an autonomous coding agent. Use it when you need:
- Full feature implementation from a spec
- Bug fixes with tests
- Multi-file refactors

### How to use Codex
Codex runs from the command line. You give it a prompt and it writes code.

```bash
# Basic usage
codex "your prompt here"

# With specific files
codex --full-auto "Fix the login bug in auth.ts"

# With context
codex "Add a new API endpoint for /api/vehicles that supports GET and POST"
```

### Prompt Template for Codex
```
Project: SQHQ (SideQuest HQ)
Stack: Kotlin + Jetpack Compose (Android), Next.js (VPS API)
Repo: https://github.com/eOnoes/sqhq-android

Task: [clear description of what to build or fix]

Files involved:
- app/src/main/java/com/sqhq/app/ui/screens/[file].kt
- app/src/main/java/com/sqhq/app/data/api/[file].kt

Constraints:
- compileSdk=36, minSdk=26
- Brutalist theme (black/white/red)
- API base: http://100.85.111.32:3000
- No login screen (removed)
- Use ComponentActivity, not AppCompat

Expected output:
- [what the code should do]
- Include tests if applicable
```

### When to use Codex vs doing it yourself
- **Use Codex:** Full features, complex refactors, anything touching 3+ files
- **Do it yourself:** Color changes, text updates, single-line fixes

---

## The Workflow (Do This Every Time)

### Step 1: Prepare your prompt
Write a clear, specific prompt using the templates above.

### Step 2: Send to the tool
- Kimi: paste into kimi.moonshot.cn
- Codex: run from terminal

### Step 3: Review the output
- Read what it gives you
- Check for obvious errors
- Make sure it matches your requirements

### Step 4: Apply the changes
- Copy the code into the right files
- Test it works

### Step 5: Push to GitHub
```bash
git add -A
git commit -m "what you changed"
git push origin master
```

### Step 6: Tell Eddie
After pushing, send Eddie this:
> **SQHQ Android updated!** 🚀
> https://github.com/eOnoes/sqhq-android/releases/latest

---

## Important Rules
1. **NEVER spawn your own sub-agents** — use Kimi/Codex as external tools
2. **Always review output** before applying — AI tools make mistakes
3. **One task at a time** — don't batch multiple features in one prompt
4. **Be specific** — vague prompts give vague results
5. **Push after every change** — Eddie needs to see progress

---

## Quick Reference

| Task | Tool | Why |
|------|------|-----|
| Code review | Kimi | Better at analysis |
| New feature | Codex | Better at implementation |
| Bug fix | Codex | Writes fixes + tests |
| Research | Kimi | Better at long context |
| Refactor | Codex | Multi-file changes |
| Quick edit | Do it yourself | Faster for small changes |

---

*This guide was written by Echo. If anything is unclear, ask Eddie.*
