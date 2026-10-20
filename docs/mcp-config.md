# Burp Suite MCP server configuration

This project's `.mcp.json` points Claude Code at a Burp Suite MCP server running
locally. This file explains how to enable that server inside Burp and what security
options to set before letting subagents touch it.

## 1. Install the MCP Server extension in Burp

1. Open Burp Suite Professional.
2. Go to **Extensions → BApp Store**.
3. Search for **"MCP Server"** and install it (the official PortSwigger MCP Server
   extension). If it isn't available in your BApp Store yet, check PortSwigger's
   extension documentation for the current distribution method — extension names and
   availability can change between Burp releases.
4. Once installed, a new **MCP** tab appears in Burp's main UI.

## 2. Configure the server in Burp

1. Open the **MCP** tab.
2. Note the listening port — it defaults to **9876** in most builds, but confirm this
   in your own installation since it's configurable.
3. Confirm whether your version exposes **SSE** (`http://127.0.0.1:9876/sse` or
   similar) or a **stdio**-launched process. This repo's `.mcp.json` assumes SSE on
   `127.0.0.1:9876`; adjust the URL/transport type if your extension differs.
4. Start/enable the server from the MCP tab.

## 3. Auto-approve targets — read this before enabling anything

The MCP Server extension typically has an **auto-approve** / allowlist setting that
controls which requests/actions from an MCP client are executed without a manual
click-through confirmation in Burp's UI.

- **Do not auto-approve all targets/domains by default.** Scope the allowlist to the
  specific hosts covered by your current, authorized engagement only.
- Treat auto-approve as equivalent to giving an LLM client (including any `haiku`-model
  subagent) unattended send/request capability against those hosts. Haiku-backed
  subagents in this repo (`burp-triager`, `burp-repeater-operator`) are intentionally
  cheap and fast, which also means they are more prone to misreading instructions or
  being steered by unexpected content in traffic (e.g. prompt-injection-like strings
  reflected in a response body). An over-broad auto-approve list turns a classification
  mistake into an unintended request against a host that may be out of scope.
- Review the extension's logging/audit view periodically to see what the MCP client
  actually sent, especially while iterating on new subagent prompts.
- When in doubt, leave auto-approve off and manually confirm each MCP-driven action in
  Burp while you're still validating a new workflow; only loosen it once you trust the
  specific subagent's behavior on a specific target.

## 4. Point Claude Code at the server

Either rely on this repo's `.mcp.json` (committed at the project root), or register the
server manually:

```
claude mcp add burp --transport sse http://127.0.0.1:9876/sse
```

(Use `claude mcp add burp --transport stdio -- <command>` instead if your build of the
extension only exposes a stdio-launched process rather than SSE.)

See `docs/setup.md` for the full step-by-step flow, including how to verify the
connection.
