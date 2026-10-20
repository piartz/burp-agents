# Example workflows

These are natural-language prompts you can give to your main Claude Code session
(running Sonnet or Opus) so it delegates mechanical work to the subagents in
`.claude/agents/`. The main agent stays in charge of judgment calls; subagents handle
repetitive, well-scoped execution.

All examples assume you're working inside an authorized, scoped engagement (see
`docs/guardrails.md`).

## 1. Mass triage of proxy history

> "Pull the last 500 requests from the Burp proxy history and use burp-triager to give
> me the 10 most suspicious endpoints — focus on anything that looks like IDOR,
> leftover debug/admin routes, or unexpected 200s."

What happens: the main agent delegates to `burp-triager` (Haiku), which scans the
history and returns a ranked shortlist with reasons. The main agent should then review
that shortlist itself before deciding what to test further — don't act on the Haiku
output uncritically.

## 2. Systematic Repeater probing

> "Take the request `GET /api/user/123` from the proxy history and use
> burp-repeater-operator to try IDs 1, 2, 100, and 'admin' in place of 123. Also try it
> with and without the Authorization header, and with an added `X-Forwarded-For:
> 127.0.0.1` header. Report anything that differs from the baseline in status code or
> response length."

What happens: `burp-repeater-operator` (Haiku) sends each variant via Repeater, diffs
against the baseline response, and reports only the deltas — it does not tell you
whether any of this is exploitable. That interpretation is your job (or the main
agent's, at Sonnet/Opus level).

## 3. OOB verification via Collaborator

> "The `url` parameter on `POST /api/fetch` looks like it might be fetched
> server-side with no SSRF protections — the response doesn't reflect anything useful.
> Use burp-oob-specialist to generate a Collaborator payload, inject it into that `url`
> parameter, send the request, and poll Collaborator for a hit."

What happens: `burp-oob-specialist` (Sonnet) generates a fresh Collaborator payload,
sends exactly that one request, polls for interactions, and reports the raw evidence
(interaction type, timestamp, source) plus the exact payload used — again without
overclaiming severity.

## General tips

- Be explicit about scope in every prompt ("use burp-X for Y") — the subagents are
  built to do exactly what they're told, not to go exploring on their own.
- Treat Haiku subagent output as a first draft. Spot-check a few of its findings
  against the raw Burp history before acting on them.
- Chain workflows: triage → pick a candidate → repeater-operator to probe it →
  oob-specialist if a probe suggests a blind/async issue. Keep each step's output in
  the conversation so the next step (and you) have context.
