# Guardrails and known limitations

Two separate categories of things to know before relying on this workflow: Anthropic's
model-level safety behavior, and a technical limitation in how subagent tool
permissions interact with MCP servers.

## Anthropic's safety behavior on dual-use security tasks

Claude (Sonnet/Opus, and to a lesser extent Haiku) applies safety judgment to
security-adjacent requests. In practice this means:

- Clearly framed, scoped, defensive/authorized-testing requests (triage traffic,
  diff responses, confirm an OOB callback from Collaborator) generally work fine, as
  reflected by the subagents in this repo.
- Requests that look like generating novel offensive exploit code, obfuscating payloads
  to evade detection, targeting unscoped/unspecified real-world systems, or anything
  that reads as "help me attack X" rather than "help me test X, which I'm authorized to
  test," are more likely to be declined or scoped down.
- This can show up mid-engagement: a model might decline to draft an aggressive
  variant of a payload even if your earlier prompts in the same session were about an
  authorized pentest. If that happens, the cause is usually that the request read as
  ambiguous about scope/authorization in isolation — re-state the engagement context
  (client, scope, authorization) explicitly rather than assuming it carries over.

### Cyber Verification Program (CVP)

Anthropic runs a **Cyber Verification Program** for professional security
practitioners (red teamers, pentesters, security researchers) that can reduce friction
on legitimate dual-use requests by giving Anthropic context that your organization does
this work under authorization. If you do offensive security work regularly and keep
hitting unnecessary friction, it's worth applying for verification through Anthropic
rather than trying to word around the model's judgment — check Anthropic's current
documentation/support channels for how to apply, since program details and the
application process can change.

## Technical limitation: subagent `tools:` field and MCP permissions

The `tools:` field in a subagent's frontmatter is meant to scope which tools that
subagent can call. In practice, **this scoping is not always airtight for MCP tools**,
particularly when the MCP server is defined inline/locally rather than referenced by a
stable, project-level configuration — depending on your Claude Code version, a subagent
can sometimes still see or call MCP tools beyond what's listed in its `tools:` field.

Mitigations:

- Prefer defining the MCP server once, at the **project level** (this repo's
  `.mcp.json`), rather than inline per-subagent, so tool scoping is consistent and
  auditable in one place.
- Where supported by your Claude Code version, use a subagent's `disallowedTools` field
  as a second, explicit denylist alongside `tools:` — don't rely on `tools:` alone as
  the only boundary, especially for a Haiku-backed subagent you plan to run with
  auto-approve enabled on Burp's side (see `docs/mcp-config.md`).
- Periodically check Burp's MCP activity/audit log (see `docs/mcp-config.md`) to
  confirm which tools a given subagent actually invoked during a run, rather than
  trusting the `tools:` field as a guarantee.
- Treat this as defense-in-depth with the auto-approve scoping in Burp itself: even if
  a subagent calls an unexpected MCP tool, a tight auto-approve allowlist limits the
  blast radius to in-scope hosts.

Re-check this behavior against your current Claude Code release notes — tool-scoping
enforcement for subagent/MCP interactions is an area that has changed between
versions and is likely to keep evolving.
