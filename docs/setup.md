# Setup guide

Step-by-step setup for using this repo's subagents with Burp Suite Professional and
Claude Code.

## Prerequisites

- Burp Suite Professional (the MCP Server extension and Collaborator functionality used
  by `burp-oob-specialist` require the Professional edition).
- Claude Code installed and working.
- An authorized, scoped target to test against (see `docs/guardrails.md` and the
  README's "Limits and responsibility" section).

## 1. Install and start the Burp MCP Server extension

Follow `docs/mcp-config.md` section 1–2: install **MCP Server** from the BApp Store,
open the **MCP** tab, confirm the listening port (default **9876**), and start the
server.

## 2. Add the server to Claude Code

You have two equivalent options:

**Option A — use this repo's `.mcp.json`** (recommended, keeps config in version
control and scoped to this project): just open Claude Code from this project directory;
it will pick up `.mcp.json` automatically. Confirm the URL/port inside it matches your
Burp MCP tab.

**Option B — register manually:**

```bash
claude mcp add burp --transport sse http://127.0.0.1:9876/sse
```

Adjust `--transport` and the URL if your build of the extension uses stdio instead of
SSE (see `docs/mcp-config.md`).

## 3. Restart / reload Claude Code

Restart Claude Code (or start a new session in this project) so it picks up the new
MCP server and the subagent definitions in `.claude/agents/`.

## 4. Verify the connection

Ask Claude directly, without invoking a subagent yet:

> "List the Burp MCP tools you have available, then fetch the last 5 entries from the
> proxy history."

If this works, you should see Claude call something like `mcp__burp__get_proxy_history`
and return real captured requests. If it fails:

- Confirm Burp is running and the MCP tab shows the server as active.
- Confirm the port in `.mcp.json` matches the Burp MCP tab.
- Confirm you've actually browsed/proxied some traffic through Burp so the history
  isn't empty.

## 5. Confirm the exact MCP tool names

Different versions/builds of the Burp MCP extension may expose tools under slightly
different names than this repo assumes (`get_proxy_history`,
`create_repeater_tab`, `generate_collaborator_payload`, `poll_collaborator`,
`send_request`). Ask Claude to list the available `mcp__burp__*` tools and, if names
differ, update the `tools:` frontmatter in the relevant file(s) under
`.claude/agents/` to match.

## 6. Configure auto-approve targets safely

Before running any subagent against real traffic:

1. Open Burp's **MCP** tab → auto-approve / allowlist settings.
2. Add **only** the exact hosts in your current engagement's scope.
3. Leave auto-approve **off** for everything else, and re-confirm the list each time
   you start a new engagement — don't let a prior engagement's hosts linger on the
   allowlist.
4. Re-read the auto-approve warning in `docs/mcp-config.md` and `docs/guardrails.md`
   before enabling it for Haiku-backed subagents specifically.

Once verified, head to `docs/workflows.md` for example prompts to try.
