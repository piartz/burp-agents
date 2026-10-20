# Workflows for Claude Code and Codex

Use the same named agents in either client. Start with [setup](setup.md) and supply
`engagement.toml`'s scope, limits and relevant account context in each handoff. A
specialist's smaller task budget still applies even if engagement budget remains.
Read-only agents use analysis; sends and Collaborator operations require active.

## 1. Map captured traffic

> Use burp-surface-mapper to inventory 100 captured HTTP requests for the engagement's
> target services. Record methods, observed paths, parameter names, account contexts
> supported by evidence, and source references. Include observed coverage gaps without
> sending requests or claiming complete coverage.

This inventories what was observed, not all endpoints that could exist.

## 2. Triage candidates

> Delegate to burp-triager. Read at most 100 in-scope captured requests with page size
> at most 50. Return the 10 strongest candidates for manual review and actual batch
> coverage. Do not send traffic.

The original triager remains available for quick prioritization independently of a
full endpoint inventory.

## 3. Review Scanner findings

> Use burp-scanner-reviewer to read up to 50 in-scope Scanner issues. Group likely
> duplicates while retaining every original reference and Scanner severity/confidence.
> Rank evidence quality, identify missing corroboration, and propose bounded manual
> verification steps. Do not run scans, resend requests or change issue states.

Scanner claims remain distinct from validated observations. Similar titles alone do
not justify merging issues from different insertion points or accounts.

## 4. Compare request variants, preserving protocol

> In active mode, delegate to burp-repeater-operator. Use the supplied HTTP/2 request
> and its captured baseline response. Try exactly three independent path-ID variants
> from our supplied test objects. Keep the same account and headers. Create review
> tabs, send each variant once, and return status/header/raw and normalized content
> deltas. Use the engagement's explicit volatile-field exclusions; report semantic
> changes even when lengths match. Budget: three sends, no extra controls.

Supply HTTP/2 pseudo-headers, ordinary headers and body separately. HTTP/1.1 requests
use the corresponding HTTP/1 tools. Never silently downgrade to make a tool fit.
If a fresh baseline/session check is needed, return the missing requirement rather
than exceeding the task budget.

## 5. Check authorization against an access matrix

> Use burp-authz-comparer for only the two access_matrix cases supplied in our
> engagement handoff. Account labels refer to our test sessions. First review the
> supplied recent identity-check captures against each expected_identity. Use the
> supplied resource/owner assertions to distinguish protected data from an error or
> login page. If sessions are valid, execute each case once in active mode; budget
> two sends. Return expected versus observed allow/deny/inconclusive, account/owner
> labels, session references, comparison evidence and limitations. Do not refresh
> credentials, enumerate objects or add cases.

The sample matrix is illustrative; replace it with your own test assets. Supply
credentials securely for execution. `credential_ref` is not an automatic resolver.
If working entirely from supplied captures, use analysis mode and request no sends.
A body/status difference alone cannot establish an access-control failure.

## 6. Collect OOB evidence

> Use burp-oob-specialist in active mode. For our supplied POST /api/fetch request,
> preserve its HTTP protocol and replace only the url field with one fresh Collaborator
> URL. The engagement permits this exact POST. Send once, retain the payload ID and
> poll only that ID up to three times within 30 seconds. Return injection point,
> payload, request outcome, observed interactions and elapsed observation window.
> No extra fields, payload variants or retries.

Ensure the configured method/path restrictions permit the requested operation first.
A missing callback within the observation window is not proof of absence of an issue.

## 7. Review WebSocket captures

> Delegate to burp-websocket-analyst. Review at most 100 captured messages for the
> supplied in-scope connection/session references. Inventory operations, message
> directions and account/resource identifiers; flag authorization-testing candidates
> with exact evidence references and limitations. Redact token values. Do not send
> or replay frames or establish connections.

Opaque frames stay opaque unless a decoded representation with provenance is supplied.
No WebSocket frame-sending automation is provided by these profiles.

## 8. Prepare a finding draft and evidence export

> Use burp-evidence-writer for the selected issue, Organizer and request references
> from this task. Draft reproduction steps actually performed, observed versus
> expected behavior, affected service, account preconditions and limitations. Return
> a version-1 structured evidence bundle with secrets redacted. Do not send requests,
> create Organizer items, invent source IDs or claim unverified impact.

The main agent saves the returned evidence under Git-ignored `artifacts/`, then uses
[the offline exporter](evidence.md) for JSON/Markdown and reviews the redaction. The
writer can read existing Organizer items; it cannot save or annotate them in Burp.

## Putting it together

Map/triage → review existing Scanner evidence → select a specific candidate →
validate test sessions → perform bounded variants or access-matrix cases → collect
OOB evidence if warranted → draft and review the finding. WebSocket analysis is an
additional read-only path for applications that use it.

Pass source references and scope between steps. Avoid concurrent account mutations
or session refreshes; the gateway shares request budget/pacing, not application state.
The main agent runs local comparison/export helpers; specialist allowlists expose
MCP capabilities only. No specialist should claim to have run a helper it cannot call.

## Switching clients and fallback

Each client needs its own MCP registration/profile and a fresh session. Session
history and credentials do not transfer automatically. Both clients share the ledger
only when configured with the same engagement ID and state path.

For clients without native custom agents, supply both
`agents/_shared/contract.md` and the selected `agents/<role>.md` body to the main
session. Frontmatter is repository metadata, not a universal registration format:

> Read agents/_shared/contract.md and agents/burp-triager.md. Perform that role in
> this session under the engagement handoff, triaging at most 100 captured requests
> and returning five candidates. Do not send traffic. State that this ran in the main
> session rather than claiming a native specialist was spawned.

If local files cannot be read, paste both instruction bodies into an MCP-capable
session connected to the gateway. The fallback preserves the task contract; it does
not create a separate agent or independent permissions.
