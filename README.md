# burp-ai-pentest-workflow

A Claude Code project that wires up **Burp Suite Professional** (via its MCP Server
extension) with a small set of **specialized subagents**, so a pentester can delegate
mechanical, well-scoped traffic-analysis work to cheap/fast models while keeping
judgment calls at the Sonnet/Opus level.

This is a workflow scaffold, not an automated scanner: every subagent here is built to
do one narrow, mechanical job and report raw findings — it's still on you (and your
main Claude session) to interpret results and decide what's actually exploitable.

## What's in this repo

```
burp-ai-pentest-workflow/
├── .mcp.json                        # Burp MCP server config for Claude Code
├── .claude/
│   └── agents/
│       ├── burp-triager.md              # Haiku — triages proxy history into a shortlist
│       ├── burp-repeater-operator.md    # Haiku — sends systematic Repeater variations
│       └── burp-oob-specialist.md       # Sonnet — Collaborator-based OOB verification
├── docs/
│   ├── setup.md                     # Step-by-step install/config/verify guide
│   ├── workflows.md                 # Example prompts for each subagent
│   ├── guardrails.md                # Safety-classifier behavior + MCP tool-scoping caveat
│   └── mcp-config.md                # Burp-side MCP Server extension + auto-approve setup
└── README.md                        # This file
```

## Prerequisites

- **Burp Suite Professional** (Collaborator and the MCP Server extension require Pro).
- **Claude Code** installed and working.
- An **authorized, scoped target** — see "Limits and responsibility" below.

## Quick install

1. Clone/copy this repo (or just use it directly as a Claude Code project directory).
2. Make the subagents available:
   - **Project-scoped (recommended)**: leave them in `.claude/agents/` inside this repo
     — they're automatically available when you run Claude Code from this directory.
   - **Global**: copy the files in `.claude/agents/` into `~/.claude/agents/` if you
     want them available from any project.
3. Configure the MCP connection — see `docs/mcp-config.md` and `docs/setup.md` for the
   full walkthrough (install the Burp MCP Server extension, confirm the port, adjust
   `.mcp.json` if needed).
4. Restart Claude Code (or start a fresh session in this directory) so it picks up both
   the MCP server and the subagent definitions.
5. Verify the connection by asking Claude to list the last few proxy history entries
   (see `docs/setup.md` step 4).

## Try it

With Burp running, some traffic captured in the proxy history, and the MCP connection
verified, try:

> "Pull the last 100 requests from the Burp proxy history and use burp-triager to give
> me the 5 most suspicious endpoints to look at next."

See `docs/workflows.md` for more examples, including Repeater-based probing and
Collaborator-based OOB verification.

## Limits and responsibility

- **Haiku-backed subagents (`burp-triager`, `burp-repeater-operator`) are cheap and
  fast, but more error-prone than the main model.** Use them for mechanical,
  well-defined tasks — scanning a list, diffing responses against a baseline — and
  always have a human (or the main Sonnet/Opus session) review their findings before
  acting on them. They are not a substitute for your own analysis.
- **The main agent (Sonnet/Opus) should make the actual security judgment calls** —
  what's actually exploitable, what severity to assign, what to report. Subagents here
  are execution/classification helpers, not decision-makers.
- **Only use this against targets you are explicitly authorized to test**, within a
  defined engagement scope (pentest authorization, bug bounty program terms, your own
  lab environment, etc.). Nothing in this repo should be pointed at systems you don't
  have permission to test.
- Read `docs/guardrails.md` before relying on this in a real engagement — it covers
  both Anthropic's safety behavior on dual-use requests and a known technical caveat
  about subagent `tools:` scoping with MCP servers.
