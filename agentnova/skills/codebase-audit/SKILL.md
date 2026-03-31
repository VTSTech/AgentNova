---
name: codebase-audit
version: 0.1.0
description: >
  Audit, analyze, and produce a condensed intelligence brief for any codebase.
  Use this skill whenever you need to understand, review, audit, or get oriented on a codebase or project.
  Triggers on phrases like "audit this repo", "review the codebase", "what does this project do",
  "get me up to speed", "brief me on", "understand this code", "code review", or when starting work
  on an unfamiliar codebase. Also triggers when the user asks to clone and review a repo.
  This skill handles two modes: if a brief.md already exists, load it for instant orientation;
  if not, perform a full audit and generate one. This enables efficient context transfer between
  sessions and agents without re-reading the entire codebase.
---

# Codebase Audit & Intelligence Brief

## Purpose

This skill solves a core problem: understanding a codebase exhausts context window budget before
the real work begins. By producing a structured intelligence brief, it allows subsequent
agents or sessions to skip the discovery phase entirely and start with most of their context
window available for execution.

## Two Modes

On skill invocation, the agent should first check for an existing brief:

```
Check /workspace/brief.md (or project root for brief.md)
    │
    ├── EXISTS → Load mode (instant orientation)
    │
    └── MISSING → Audit mode (full analysis & brief generation)
```

---

## Mode 1: Load (Brief Exists)

If `brief.md` is found in `/workspace/` or the project root:

1. Read `brief.md` in full
2. This document IS your orientation — treat it as authoritative
3. Skip the file-discovery phase entirely
4. Proceed directly to the user's task with your full context window available
5. If you need deeper understanding of a specific file, use the **Critical Files Index**
   in the brief to know exactly which files to read — do not blindly scan

### What to do if the brief seems stale

If the brief references files that don't exist, or the project state has clearly changed
since the brief was generated, inform the user and offer to regenerate it.

---

## Mode 2: Audit (Brief Missing)

If no `brief.md` exists, perform a full codebase audit and generate one.

### Step 1: Identify the Target

Ask the user for the codebase source. This could be:
- A git repo URL to clone
- A local directory path
- An already-cloned repo in the workspace

Clone if necessary, then proceed.

### Step 2: Scan & Understand

The goal is NOT to read every file. The goal is to build an efficient mental model of the
project by reading the minimum set of files that maximizes understanding.

**Start here (in order):**
1. Package/lock files → identify tech stack, dependencies, runtime
2. Config files → build tools, environment settings, frameworks
3. Directory structure (top 2-3 levels) → understand organization
4. README / docs → if they exist, they may save you reading code
5. Entry points → main files, server startup, route definitions
6. Type definitions / schemas → if applicable (Prisma, TypeScript interfaces, etc.)

**Then selectively read:**
- Files that appear in dependency chains from entry points
- Files referenced by config or routing
- Files that seem unusually large or complex (likely core logic)
- Test files (sample a few to understand expected behavior)

**Skip immediately:**
- `node_modules/`, `vendor/`, `__pycache__/`, `.git/`
- Generated files, build output, dist folders
- Migration files (unless they reveal schema evolution)
- Lock files beyond initial scan
- Image assets, fonts, static media

### Step 3: Build the Brief

Use the template in `references/brief-template.md` to structure your output.

The brief should be a **map, not a diary**. You are telling another agent where to look
and what to watch out for — not narrating what you read. Every section should answer the
question: "What does the next agent need to know to be effective?"

### Token Budget

The brief must not exceed **16,000 tokens** (approximately 56,000 characters / 11,000 words).
This ensures the consuming agent retains at least half its context window on even the smallest
realistic model (32K context). On larger models (128K, 256K) the brief is effectively free.

After generating the brief, estimate the token count (characters ÷ 3.5) and verify it is
under the limit. If over budget, compress before saving.

### Content Principles

Prioritize **information density** over brevity. You have headroom to be thorough within
the 16K limit — use it for things that genuinely help the next agent:

- **Be specific** — "auth fails silently on expired tokens" not "auth has issues"
- **Include code snippets** for critical functions, tricky logic, or non-obvious patterns
- **Be action-oriented** — "edit this file to change X" not "this file contains X"
- **Be honest about gaps** — if you couldn't understand something, say so
- **Don't pad** — if a section doesn't apply, omit it rather than writing filler

Sections where depth is most valuable:
1. **Critical Files Index** — include key function signatures, important constants
2. **Known Landmines** — these save real debugging time, be thorough
3. **Request Lifecycle** — include actual function call chains, not just descriptions

### Step 4: Save

Save the completed brief to:
- `/workspace/brief.md` (preferred, if ACP workspace is available)
- `{project_root}/brief.md` (fallback)

Inform the user the brief has been generated and is ready for use by other sessions/agents.

---

## Optional: Full Audit Report

If the user explicitly requests a detailed audit report (PDF/DOCX), the brief is the
condensed version — the report is the expanded version. Use the appropriate document skill
(pdf or docx) to produce it. The report should include:

- Everything in the brief, expanded with details and evidence
- Code quality assessment per critical file
- Specific code snippets for issues found
- Dependency analysis and vulnerability notes
- Recommendations with priority levels

The brief is always generated regardless — it's the persistent artifact. The report is
the disposable, detailed deliverable.

---

## Brief Freshness

A brief is only as good as its currency. The brief should include a generated timestamp.
If the project has significant changes, the brief should be regenerated.

Guidance: if more than ~20% of the files referenced in the brief have changed or been
renamed since the brief was generated, it's time for a refresh.

---

## External Endpoints

This skill makes NO network requests. It only accesses local files and the user's codebase.

## Security & Privacy

All analysis is local. The brief contains only structural and architectural information
about the codebase — no credentials, no secrets, no sensitive runtime data.
