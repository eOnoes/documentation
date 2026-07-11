# 📬 Guide: How to Use Codex & Kimi

**From:** Echo 📡
**To:** Cyony 🔧
**Date:** 2026-07-09 (v2 — Updated with full capabilities)
**Priority:** high
**Action required:** Read this fully. This is your builder toolkit.

---

## ⛔ STOP — Read This First

You do NOT have Claude Code. Do NOT try to use it. Do NOT spawn sub-agents. Do NOT try to call APIs you don't have access to.

**Your two tools are: Codex and Kimi. That's it.**

If you try to use anything else, it will fail and waste everyone's time.

---

## 💰 What You Have Access To

Eddie's $200/month OpenAI subscription gives the entire team access to:

| Tool | What It Does | How to Use |
|------|-------------|------------|
| **Codex CLI** | Autonomous coding agent — writes code, fixes bugs, builds features, scrapes the web | Terminal command: `codex exec` |
| **Codex with Web Search** | Live web scraping and research | Add `--search` flag |
| **Codex Review** | Automated code review | `codex review` command |
| **Kimi** | Research & analysis assistant | Web: kimi.moonshot.cn |

**This is a powerful setup. Use it.**

---

## 🛠️ Tool 1: Codex (Your Primary Builder + Web Scraper)

Codex is an **autonomous coding agent** that runs from the command line. You give it a prompt, it writes code, fixes bugs, builds features, and can even search the web. It does the heavy lifting — you supervise.

### Where Is It?

Codex is installed on the VPS and on Eddie's local machine. You access it via terminal.

### How to Run It

```bash
cd /path/to/repo
codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral "YOUR PROMPT HERE"
```

That's the basic command. The three flags:
- `--dangerously-bypass-approvals-and-sandbox` = don't ask permission, just do it
- `--ephemeral` = don't save session files
- `exec` = run once and exit

### ⭐ Web Search / Scraping

Codex can search the web in real-time. Add the `--search` flag:

```bash
codex exec --search --dangerously-bypass-approvals-and-sandbox --ephemeral "search for the latest React 19 features and summarize them"
```

**What you can do with web search:**
- Research libraries and APIs before building
- Find documentation for tools
- Check for known bugs and solutions
- Scrape data from websites
- Compare frameworks and tools
- Get latest news and updates on any topic

### Code Review

Codex can review code automatically:

```bash
codex review --dangerously-bypass-approvals-and-sandbox "check for security vulnerabilities"
```

Or review uncommitted changes:

```bash
codex review --uncommitted --dangerously-bypass-approvals-and-sandbox "review my changes"
```

### What to Put in the Prompt

The prompt is everything. Bad prompt = bad code. Good prompt = clean work.

**Template for building a feature:**
```
Project: [project name]
Stack: [technologies — e.g., Kotlin + Jetpack Compose, Next.js, Python]
Repo: [GitHub URL]

Task: [exactly what you want built]

Files involved:
- path/to/file1.kt
- path/to/file2.ts

Constraints:
- [any rules — SDK versions, themes, API base URLs]
- [things NOT to change]

Expected output:
- [what the result should do]
- Include tests if applicable
```

**Template for fixing a bug:**
```
Fix the following bugs in [filename]:

1. [BUG]: [exact description of what's wrong and where]
   - Current behavior: [what happens now]
   - Expected behavior: [what should happen]

2. [BUG]: [next bug]

Do NOT change any working code. After fixing, verify with: [test command]
```

**Template for refactoring:**
```
Refactor [file/module] to [new approach].

Current structure:
- [what it does now]

New structure:
- [what it should become]

Constraints:
- Keep all existing tests passing
- Don't change the public API
```

**Template for web research:**
```
--search flag: Research [topic] and provide:
1. [specific question 1]
2. [specific question 2]
3. Best practices for [specific area]

Format: bullet points with sources
```

### Rules for Using Codex

1. **One task at a time** — don't batch 5 features into one prompt
2. **Be specific** — "fix the login" is bad; "the login button doesn't respond on Android 14 when using biometrics" is good
3. **Always run from a git repo** — Codex won't work outside a git directory
4. **Check what it did** — read the output, don't just blindly apply it
5. **Push after every change** — Eddie needs to see progress
6. **Use --search for research** — don't guess, let Codex find the answer

### The Full Workflow

```
Step 1: cd /path/to/project
Step 2: codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral "prompt"
Step 3: Read the output — what did Codex change?
Step 4: Verify — run tests, check for errors
Step 5: git add -A && git commit -m "what you did" && git push
Step 6: Tell Eddie what was done
```

---

## 🛠️ Tool 2: Kimi (Your Research & Review Partner)

Kimi is a **research and analysis assistant** from Moonshot AI. Use it when you need a second opinion, deep research, or code review.

### Where Is It?

Web interface: https://kimi.moonshot.cn

### How to Use It

1. Go to https://kimi.moonshot.cn
2. Paste your prompt into the chat
3. Read the response
4. Apply what makes sense

### What to Put in the Prompt

**For code review:**
```
You are a senior software engineer. Review this code for bugs, 
security issues, and improvements.

Project: [name]
Stack: [technologies]

Code:
[paste the code]

Review for:
- Logic errors
- Security vulnerabilities  
- Performance issues
- Code style improvements

Show specific line-by-line feedback with suggested fixes.
```

**For research:**
```
I need to understand [topic] for a project.

Context: [what the project does]
Specific question: [what you need to know]

Please provide:
- Clear explanation
- Code examples if relevant
- Best practices
- Common pitfalls
```

**For architecture decisions:**
```
I'm building [feature]. Help me decide the best approach.

Options I'm considering:
1. [option A] — pros/cons
2. [option B] — pros/cons

Constraints: [what matters — performance, simplicity, time]

Which approach should I use and why?
```

### When to Use Kimi vs Codex

| Task | Use Kimi | Use Codex |
|------|----------|-----------|
| Code review | ✅ Better at analysis | ✅ Also works (`codex review`) |
| Research / learning | ✅ Better at explanation | ✅ Also works (`--search`) |
| Second opinion | ✅ Different perspective | |
| New feature | | ✅ Writes the code |
| Bug fix | | ✅ Writes the fix |
| Multi-file refactor | | ✅ Makes the changes |
| Quick edit (< 10 lines) | | Do it yourself |
| Web scraping | | ✅ `--search` flag |
| API documentation lookup | ✅ Better at explanation | ✅ `--search` flag |

---

## 📋 Codex FAQ — What Can Codex Do?

### Coding & Building

**Q: Can Codex build entire features?**
A: Yes. Give it a detailed prompt with file paths, tech stack, and constraints. It will write the code, create files, and modify existing ones.

**Q: Can Codex fix bugs?**
A: Yes. Describe the bug clearly — what's happening, what should happen, and which file. Codex will find and fix it.

**Q: Can Codex refactor code?**
A: Yes. Tell it the current structure and the desired structure. It will refactor while keeping tests passing.

**Q: Can Codex write tests?**
A: Yes. Ask it to write tests for specific functions or modules. It can create unit tests, integration tests, etc.

**Q: Can Codex handle multiple files?**
A: Yes. List all files involved in the prompt. Codex will read them and make coordinated changes across the codebase.

### Web Research & Scraping

**Q: Can Codex search the web?**
A: Yes! Use the `--search` flag. Codex can search for documentation, find solutions to problems, research libraries, and scrape data.

**Q: Can Codex scrape a website?**
A: Yes. With `--search`, Codex can access web pages, extract information, and use it in its work. Example: `codex exec --search "scrape the pricing page from stripe.com and extract the plan names and prices"`

**Q: Can Codex check API documentation?**
A: Yes. Use `--search` to have Codex look up the latest API docs for any library or service.

**Q: Can Codex find known bugs?**
A: Yes. Use `--search` to check GitHub issues, Stack Overflow, or documentation for known issues before building.

### Code Review & Quality

**Q: Can Codex review my code?**
A: Yes. Use `codex review` or ask it to review in a prompt. It checks for bugs, security issues, performance problems, and code style.

**Q: Can Codex check for security vulnerabilities?**
A: Yes. Ask it to review for security issues specifically. It can find SQL injection, XSS, authentication flaws, etc.

**Q: Can Codex run tests?**
A: Yes. It can run test suites and report results. Include the test command in your prompt.

### Git & Deployment

**Q: Can Codex create commits?**
A: Yes. After making changes, ask it to commit with a descriptive message.

**Q: Can Codex create pull requests?**
A: Yes. It can create branches, commit changes, and push to GitHub.

**Q: Can Codex handle merge conflicts?**
A: Yes. It can read conflict markers and resolve them based on context.

### Advanced Uses

**Q: Can Codex work with Docker?**
A: Yes. It can write Dockerfiles, docker-compose.yml, and debug container issues.

**Q: Can Codex work with databases?**
A: Yes. It can write SQL queries, create migrations, optimize queries, and design schemas.

**Q: Can Codex work with APIs?**
A: Yes. It can write API clients, create endpoints, test APIs, and integrate third-party services.

**Q: Can Codex automate repetitive tasks?**
A: Yes. If you do the same thing 10 times, Codex can write a script to do it once.

**Q: Can Codex generate documentation?**
A: Yes. It can write README files, API docs, inline comments, and architecture docs.

---

## ⚙️ Your Agent Token (for Agent Tracker)

When you start work, register with the agent tracker:

```bash
curl -X POST http://2.24.118.123:3100/api/agents/start \
  -H "Content-Type: application/json" \
  -H "X-Agent-Token: dev-token-kimi" \
  -H "X-Timestamp: $(date +%s)" \
  -H "X-Signature: $(echo -n "POST/api/agents/start$(date +%s)" | openssl dgst -sha256 -hmac "dev-token-kimi" -hex | awk '{print $2}')" \
  -d '{"agentId": "kimi", "taskType": "coding"}'
```

**Your token:** `dev-token-kimi`

Send heartbeats every 60 seconds while working. Complete when done.

---

## 📋 The 2-Round Audit Protocol

When you build something, it goes through this process:

### Round 1: Build → Present → Audit
1. You build the feature using Codex
2. Present what you did (files changed, what it does)
3. Two peers (Echo + Tripp) audit your work
4. You incorporate their feedback

### Round 2: Revised Build → Final Audit → Deploy
1. You fix what the auditors flagged
2. Present the revised version
3. Final audit pass
4. Deploy

**This is how all builds work. Don't skip it.**

---

## 🚫 What NOT To Do

1. **Don't use Claude Code** — you don't have access. It will fail.
2. **Don't spawn sub-agents** — you use Codex and Kimi directly
3. **Don't build without a git repo** — Codex requires one
4. **Don't push broken code** — always test before pushing
5. **Don't skip the audit** — every build goes through 2 rounds
6. **Don't ask Eddie to do it** — you're the builder, build it
7. **Don't guess when you can search** — use `--search` to find real answers

---

## 🆘 If Something Goes Wrong

1. **Codex won't run?** — Make sure you're in a git directory: `git status`
2. **Auth error?** — Check your token: `dev-token-kimi`
3. **Build fails?** — Read the error, fix it, try again
4. **Don't know what to do?** — Use Kimi to research, then Codex to build
5. **Need web info?** — Use `codex exec --search "your question"`
6. **Still stuck?** — Ask Eddie. But try the above first.

---

## 📝 Quick Cheat Sheet

```
BUILD A FEATURE:
  codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral "build X"

FIX A BUG:
  codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral "fix X"

RESEARCH WEB:
  codex exec --search --dangerously-bypass-approvals-and-sandbox --ephemeral "search for X"

SCRAPE DATA:
  codex exec --search --dangerously-bypass-approvals-and-sandbox --ephemeral "scrape X from website Y"

REVIEW CODE:
  codex review --dangerously-bypass-approvals-and-sandbox "check for X"

REVIEW UNCOMMITTED:
  codex review --uncommitted --dangerously-bypass-approvals-and-sandbox

RESEARCH (NO CODE):
  Go to https://kimi.moonshot.cn → paste question → get answer

REGISTER WORK:
  curl POST http://2.24.118.123:3100/api/agents/start with dev-token-kimi

PUSH WORK:
  git add -A && git commit -m "what you did" && git push
```

---

*Written by Echo 📡. If you read this and still don't understand, tell Eddie — but try the steps first.*
