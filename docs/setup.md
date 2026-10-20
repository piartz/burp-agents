# Setup guide

Both clients use the same eight agents, engagement file, gateway and evidence format.
Native agent files and MCP profile templates are generated and shipped in the repo.

## 1. Prepare Burp and the local environment

Install Burp's **MCP Server** extension, enable it in the **MCP** tab, and extract
`mcp-proxy-all.jar` using the extension's installer/extract option. Confirm the SSE
URL; upstream documents `http://127.0.0.1:9876`, while some older builds use `/sse`.
Use Python 3.11+ and a Java runtime compatible with the packaged proxy (Burp's bundled
Java can be used). See [PortSwigger's setup instructions](https://github.com/PortSwigger/mcp-server/blob/main/README.md).

Professional is required for Scanner issues and Collaborator. The other available
capabilities can be used with Community; absent tools must be reported as unavailable.

## 2. Configure the engagement

Copy `config/engagement.example.toml` to `engagement.toml`. Set the target host,
port/TLS, Java/JAR paths and limits. Review excluded paths and allowed methods; POST
or other methods must be explicitly allowed for tasks that require them. Replace
example account labels and access cases with your test assets. Credential references
are placeholders resolved by you, not stored secrets or an automatic login mechanism.

Read [engagement.md](engagement.md) for enforced controls and their boundaries.
`engagement.toml`, `.burp/`, `artifacts/` and `.codex/config.toml` are Git-ignored.

## 3A. Claude Code

Run Claude Code from this repository. The committed `.mcp.json` launches the gateway
in `analysis` mode. Approve the project server when prompted. The native definitions
in `.claude/agents/` use server name `burp` in their tool lists.

For active testing, replace `.mcp.json` with `config/mcp/claude-active.json` and start
a fresh session. Switch back using `config/mcp/claude-analysis.json`. The sync script
restores the analysis default; personal connection choices belong in local client
configuration if you want to retain them across regeneration.

For global agents, copy `.claude/agents/*.md` to `~/.claude/agents/`. Register the
selected MCP template separately using absolute script/engagement paths. Remove any
old direct SSE connection before relying on gateway restrictions.

## 3B. Codex with GPT

Use a current local client with standalone TOML custom-agent support. Copy
`config/mcp/codex-analysis.toml` to `.codex/config.toml`, merging the
`[mcp_servers.burp]` block into any existing configuration rather than overwriting it.
Trust the project when prompted; the `.codex/agents/*.toml` files define the same
named specialists. The agent model and reasoning effort inherit from the parent.

For active testing, use the block in `config/mcp/codex-active.toml` and start a fresh
session. Its `enabled_tools` list and gateway profile both permit the active tools.
For global agents, copy `.codex/agents/*.toml` to `~/.codex/agents/` and configure the
connection separately with absolute paths. Do not register a parallel direct server.

These formats and transport choices follow [OpenAI's custom-agent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
and [MCP documentation](https://developers.openai.com/codex/mcp/). Codex uses the stdio
gateway, which launches Burp's packaged SSE bridge. It does not consume Claude's
`.mcp.json` as project MCP configuration. Hosted GPT/API clients are not configured by
these local files; see the single-session fallback in [workflows.md](workflows.md).

## 4. Verify in analysis mode

Start a fresh client session in the repository. In Codex, `codex mcp list` shows
configured servers and `/mcp` shows active tools. Ask the main agent:

> List the Burp tools available, then read five captured HTTP history entries using
> count=5 and offset=0. Do not send traffic.

Only analysis tools should appear; send/tab/Collaborator tools should be absent.
Confirm the client actually loads native specialists by delegating one bounded
history task. If custom agents are unavailable, use the explicit fallback.

If startup fails, check Python version, local engagement file, Java/JAR paths, Burp's
server state, URL and matching extension/proxy versions. The gateway prints startup
errors to stderr. If a tool is absent or renamed, compare your installed schemas with
[the upstream implementation](https://github.com/PortSwigger/mcp-server/blob/main/src/main/kotlin/net/portswigger/mcp/tools/Tools.kt),
then update the shared agent sources and capability catalog and regenerate.

## 5. Use active mode deliberately

Switch profiles only for the requested verification task. Supply exact requests,
protocol, account context, variants/access matrix and a budget including any session
controls. HTTP/2 requires the supplied pseudo-header/body schema; never downgrade
silently. Scope/method/path checks apply to tabs and sends. A tab alone is not a send.

Burp-side approval remains separate. Review it for the engagement's exact targets.
Start with small batches, inspect raw results, and use [workflows.md](workflows.md)
and [evidence.md](evidence.md) for the full workflow.

## Alternative bridge when Java cannot start

If the bundled Java executable exits immediately (for example, macOS kills it) and
no suitable system Java is installed, the gateway can launch a Python stdio-to-SSE
bridge instead. [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) supports this
transport. One locally verified combination is mcp-proxy 0.12.0 with MCP SDK 1.30.0
in an isolated Python 3.13 environment:

```bash
uv venv .burp/proxy-venv --python python3.13
uv pip install --python .burp/proxy-venv/bin/python 'mcp-proxy==0.12.0' 'mcp==1.30.0'
```

In `engagement.toml`, replace only the upstream block, using your absolute path:

```toml
[upstream]
command = "/absolute/path/to/burp-agents/.burp/proxy-venv/bin/mcp-proxy"
args = ["--transport", "sse", "--log-level", "WARNING", "http://127.0.0.1:9876"]
```

The gateway and capability profiles are unchanged. Keep the SDK pinned with this
bridge version: allowing SDK 2.x caused an import failure during local validation.
The environment lives in the Git-ignored `.burp/` directory. For an initial
connection check, keep request/poll budgets at zero and do not configure active
scope until selecting your actual engagement targets.
