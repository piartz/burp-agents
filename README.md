# burp-ai-pentest-workflow

Shared Burp Suite Professional workflows for **Claude Code** and **OpenAI Codex
(GPT)**, with eight focused agents, enforced MCP capability profiles, and offline
helpers for response comparison, session checks and redacted evidence exports.

The human/main agent chooses the test and interprets evidence. Specialists perform
bounded tasks; this repository does not automate unrestricted scanning.

## Agents

| Agent | Job | Profile | Claude default |
| --- | --- | --- | --- |
| `burp-triager` | Rank captured traffic for review | analysis | Haiku |
| `burp-surface-mapper` | Inventory observed endpoints, parameters and coverage gaps | analysis | Haiku |
| `burp-scanner-reviewer` | Group Scanner findings and prioritize verification | analysis | Sonnet |
| `burp-evidence-writer` | Draft reproducible findings from selected evidence | analysis | Sonnet |
| `burp-websocket-analyst` | Review captured handshakes/messages; no frame sending | analysis | Sonnet |
| `burp-repeater-operator` | Execute specified HTTP/1.1 or HTTP/2 variants | active | Haiku |
| `burp-authz-comparer` | Evaluate an explicit test-account access matrix | active* | Sonnet |
| `burp-oob-specialist` | One specified injection point and correlated OOB evidence | active | Sonnet |

*The authorization comparer can also analyze supplied captures without sends in the
analysis profile. Codex agents inherit the parent's model and reasoning effort.
See [OpenAI's custom-agent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Quick start

You need Python 3.11+, Burp with the MCP Server extension, a compatible Java runtime
for its extracted stdio proxy, and Claude Code or a local Codex client supporting
custom agents. Scanner findings and Collaborator require Burp Professional.

1. Enable Burp's MCP extension and extract `mcp-proxy-all.jar`.
2. Copy `config/engagement.example.toml` to `engagement.toml`. Set exact target
   services, allowed methods, budgets and Java/JAR paths. Keep credentials in your
   own secret store; account entries contain labels and references only.
3. **Claude Code:** the committed `.mcp.json` uses the gateway's analysis profile.
   **Codex:** copy `config/mcp/codex-analysis.toml` to `.codex/config.toml`, merging
   into any existing configuration. Trust the project when prompted.
4. Start a fresh session from this directory, list MCP tools, and read a small batch
   of captured history. No sending tools should appear in the analysis profile.
5. For active verification, switch to the matching `claude-active.json` or
   `codex-active.toml` template under `config/mcp/`, then restart the session.

Full installation, global-agent setup and transport troubleshooting:
[setup guide](docs/setup.md). All local configuration and artifacts are Git-ignored.

## Use it

> Use engagement.toml's scope and limits. Delegate to burp-surface-mapper to inventory
> 100 captured requests, then burp-scanner-reviewer to group up to 50 Scanner issues.
> Return source references and bounded verification suggestions. Do not send traffic.

See [workflows](docs/workflows.md) for all eight roles and the single-session fallback.
Pass engagement context and evidence explicitly when switching clients.

## Shared capabilities

- **HTTP/1.1 and HTTP/2:** preserve protocol, authority, headers and bodies.
- **Gateway controls:** capability allowlists, exact host/port/TLS scope, method/path
  restrictions, shared persistent request/poll budgets and pacing across processes.
- **Response comparison:** meaningful headers and normalized JSON, raw results
  retained, equal-length content changes detected and truncated bodies marked unknown.
- **Session checks:** explicit identity assertions distinguish valid, invalid,
  mismatched and unknown test sessions; no automatic login or credential refresh.
- **Evidence:** structured records, source provenance, redacted JSON/Markdown exports
  and private output permissions. Review redaction before sharing.

Gateway controls apply only to calls through the configured gateway. They do not
filter Burp history by host or govern direct Burp/UI activity. See
[engagement configuration](docs/engagement.md), [evidence helpers](docs/evidence.md)
and [guardrails](docs/guardrails.md) for exact boundaries.

## Repository layout

```text
agents/*.md                  # Edit these shared role definitions
agents/_shared/contract.md    # Shared engagement/protocol/evidence instructions
.claude/agents/               # Generated native Claude agents
.codex/agents/                # Generated native Codex agents
config/engagement.example.toml
config/evidence.example.json
config/mcp/                  # Generated analysis/active templates for both clients
scripts/burp-gateway.py       # stdio MCP gateway; launches Burp's packaged proxy
scripts/compare-responses.py  # Offline comparison and identity checks
scripts/export-evidence.py    # Offline redacted JSON/Markdown exports
scripts/sync-agents.py        # Generate/check native agents and profile templates
tests/test_workflow.py        # Offline tests, including a mock MCP transport
```

## Maintaining and checking

Edit shared roles, the shared contract, or the capability catalog in
`scripts/burp_common.py`, then regenerate and validate:

```bash
python3 scripts/sync-agents.py
python3 scripts/sync-agents.py --check
python3 -m unittest discover -s tests -v
```

Agent frontmatter accepts one unquoted scalar per line: `name`, `description`,
`claude_model`, and comma-separated server-side `tools`. Both adapters embed the same
shared contract and role instructions. Generated files ship with the repository.
Tests run locally with the standard library and a mock server; they do not contact
Burp or a test target. See [capability coverage](docs/mcp-config.md) for limitations.
