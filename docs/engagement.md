# Engagement configuration and gateway

Copy [engagement.example.toml](../config/engagement.example.toml) to a local
`engagement.toml`. Both clients use the same file and SQLite ledger. No API key,
Python packages or separate service are needed. Python 3.11+ is required at runtime.

## Configuration

| Setting | Meaning |
| --- | --- |
| `engagement_id` | Stable identifier for this engagement; ledger counters are keyed by it |
| `state_path` | SQLite ledger path relative to the engagement file; shared across agent processes |
| `targets` | Exact host, port and HTTPS boolean; no wildcard hosts |
| `allowed_methods` | Explicit method allowlist; GET/HEAD/OPTIONS in the example |
| `excluded_paths` | Path globs checked against decoded and normalized request paths |
| `limits.max_requests` | Total attempted HTTP sends across both protocols/processes |
| `limits.max_polls` | Total Collaborator interaction polls across payloads/processes |
| `limits.max_history_count` | Maximum requested page size for history/issues/Organizer reads |
| `limits.min_interval_seconds` | Minimum interval between forwarding active calls across processes |
| `upstream` | Java executable and arguments for Burp's extracted stdio proxy; no shell execution |
| `accounts` | Test-account labels, credential references and expected session identity assertions |
| `access_matrix` | Explicit account/method/path/owner/expected outcome cases |
| `comparison` | Length tolerance and explicitly ignored headers/volatile JSON pointers |

The gateway enforces the scope and `limits` entries, not account semantics or the
expected access matrix. The main agent passes the latter to specialists and reviews
their evidence. Credentials must be supplied securely for explicitly requested sends;
the gateway does not resolve credential references or manage login sessions.

## Profiles

`analysis` exposes captured HTTP/WebSocket history, Organizer items and Scanner issue
reads (including supported regex variants). `active` adds HTTP/1.1 and HTTP/2 sends,
Repeater tab creation, Collaborator payload generation and correlated polling.
Templates for both clients are under `config/mcp/`; restart after switching profiles.
Keep only one Burp connection registered, through the gateway, to avoid an unfiltered
alternate connection. For global registration, use absolute paths to the gateway
script and engagement file in the selected template.

Calls outside the profile are rejected even if the client invokes a tool that was
not advertised in `tools/list`. Other MCP methods such as resource reads, config edits,
Intruder and upstream-initiated sampling are not exposed. The gateway forwards normal
MCP initialization, tool listing/calling, ping and lifecycle/cancellation notifications.
Tool catalog pagination is preserved, with each page filtered by the profile.

For active requests the gateway checks the explicit target service against the
allowlist and verifies that HTTP/1 Host or HTTP/2 authority/scheme agrees. Only
origin-form paths and explicit HTTP/2 pseudo-headers are accepted. Repeater tabs
receive the same scope/method/path checks, though tab creation consumes no send budget.
A subsequent send is a separate counted call. Collaborator polls require a payload ID.

The gateway forwards through Burp's packaged stdio proxy, which bridges to the
extension's SSE server. It neither sends HTTP traffic itself nor starts Scanner jobs.
Missing tools remain missing; the gateway does not fabricate capabilities.

## Budgets and pacing

SQLite transactions reserve budget and dispatch slots across gateway processes using
the **same ledger path and engagement ID**, including different clients. Restarts do
not reset counters. Each send attempt counts even if upstream/Burp denies it, fails,
times out or returns an error. Poll attempts count similarly. No automatic retries
or refunds occur. Different state files do not share limits.

Active calls are paced, including tabs and Collaborator operations. This controls
forwarding times, not concurrency inside Burp, redirects followed internally by an
extension, or traffic generated elsewhere. Caller task budgets and polling observation
windows may be smaller than engagement-wide limits and must also be respected.

Do not delete the ledger or change the engagement ID to continue a budget-exhausted
task. Review and deliberately adjust the configured budget if further testing is
needed. A new engagement should have its own identifier and reviewed configuration.

## Boundaries

Path/method restrictions are syntactic controls, not an understanding of application
semantics; a GET can still change state. Filters are not a replacement for Burp-side
request permissions. Analysis tools can return other hosts' captured data: use a
project containing the engagement's data and filter results before reporting.

Account freshness, ownership assertions, redaction review and per-task action limits
are agent/main-session responsibilities. A client with independent shell access or a
direct Burp connection can bypass this gateway. The gateway is not a system sandbox.
The upstream process and its installation are trusted local components.
