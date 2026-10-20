# MCP capabilities and connections

Both clients connect through `scripts/burp-gateway.py` to Burp's packaged stdio proxy,
which bridges to the extension's SSE server. The generated `.mcp.json` and
`docs/codex-config.toml` default to the analysis profile. Analysis/active templates
for both clients live under `config/mcp/` and are generated from the same catalog.

Install and enable Burp's **MCP Server** extension, extract `mcp-proxy-all.jar`, and
configure the Java/JAR paths and SSE URL in the local engagement file. Keep the Burp
listener on loopback. PortSwigger documents the default URL as
`http://127.0.0.1:9876`; confirm your installed version. See
[upstream setup](https://github.com/PortSwigger/mcp-server/blob/main/README.md).

## Capability coverage

| Capability | Tools | Profile |
| --- | --- | --- |
| HTTP history | `get_proxy_http_history`, `get_proxy_http_history_regex` | analysis/active |
| Scanner findings | `get_scanner_issues` (Professional) | analysis/active |
| Organizer evidence | `get_organizer_items`, `get_organizer_items_regex` | analysis/active |
| WebSocket captures | `get_proxy_websocket_history`, `get_proxy_websocket_history_regex` | analysis/active |
| HTTP/1.1 | `send_http1_request`, `create_repeater_tab` | active |
| HTTP/2 | `send_http2_request`, `create_repeater_tab_http2` | active |
| OOB evidence | `generate_collaborator_payload`, `get_collaborator_interactions` (Professional) | active |

Names are server-side; client prefixes vary. A profile exposes only capabilities the
installed extension actually supplies. Current upstream distinguishes request sending
from tab creation and provides history/issue reads rather than full scan lifecycle,
Organizer writing or WebSocket frame-sending automation. See
[tool implementations](https://github.com/PortSwigger/mcp-server/blob/main/src/main/kotlin/net/portswigger/mcp/tools/Tools.kt).

## Permissions and limits

The gateway filters tool listings and rejects disallowed calls. Active calls require
exact target service/authority agreement, allowed methods and non-excluded paths.
Shared SQLite transactions enforce attempted-send/poll budgets and pacing across
processes using the same ledger/engagement. See [engagement.md](engagement.md).

Claude's per-agent `tools:` list and Codex's embedded capability instructions remain
role boundaries, not independent system sandboxes. Codex inherits the parent's MCP
servers; the generated server `enabled_tools` list applies to the whole connection.
See [OpenAI's MCP documentation](https://developers.openai.com/codex/mcp/).

Keep one Burp connection configured through the gateway. Direct SSE/JAR connections,
Burp UI activity and unrelated tools bypass its limits. Review Burp's own request
permissions and extension logging; keep configuration editing disabled unless needed.
The gateway does not filter history contents by host or enforce application-level
resource ownership. Use the main agent's scope filtering and session assertions too.

Follow [setup.md](setup.md) to select a client/profile, restart and verify.
