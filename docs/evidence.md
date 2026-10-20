# Evidence and response comparison

The evidence writer and other specialists return version-1 JSON bundles shaped like
[the example](../config/evidence.example.json). Each record requires a unique `id`,
`agent`, `task`, and arrays `source_refs`, `observations`, `limitations`. Optional
fields include structured `request`, `response`, `comparison`, `reproduction_steps`
and caller-reviewed impact. Use source references actually returned by Burp; if an
ID is unavailable, record tool name, pagination offset and task/batch reference.

Response objects require integer `status`, a `headers` object, boolean
`body_complete`, and either text `body` or `body_base64`. Header values may be strings
or arrays for repeated headers. Set completeness false for truncation or unknown
coverage. Save transport failures as limitations, never as fabricated HTTP responses.

## Compare saved responses

The main agent can save two response objects and run:

```bash
python3 scripts/compare-responses.py artifacts/baseline.json artifacts/variant.json --engagement engagement.toml
```

The helper reports status changes, changed header names, raw/normalized equality,
length deltas, and the exact applied/unmatched JSON pointer exclusions. JSON object
order and formatting are ignored; array order and value types remain significant.
Only explicitly configured volatile fields are removed. With incomplete bodies,
body equality and full-length deltas are unavailable. Text byte counts describe the
UTF-8 representation, not necessarily original wire bytes; use base64 for exact bytes.

The caller must not exclude resource ownership or identity fields from authorization
assertions. A 200 or equal body size does not establish access. Compare content,
redirects, content type and expected resource/owner assertions as well.

## Check a session

```bash
python3 scripts/compare-responses.py artifacts/session-before.json artifacts/session-after.json --engagement engagement.toml --account user-a
```

`--account` checks **session-check** responses, not arbitrary protected-resource
responses. An identity JSON pointer and expected value are required for a valid
result. States are `valid`, `invalid`, `mismatch` or `unknown`. A 401/login redirect
fails the check; a 403 on a protected resource is not automatically session expiry.
Freshness, association with the tested credentials and login HTML served with 200
must also be reviewed by the main agent. The helper does not log in or refresh tokens.

## Export a draft

```bash
python3 scripts/export-evidence.py artifacts/evidence.json --output artifacts/shareable.json
python3 scripts/export-evidence.py artifacts/evidence.json --output artifacts/finding.md --format markdown --secret-key custom_session
```

The exporter validates record structure and IDs, redacts common credential headers,
secret JSON/form/query fields, URL userinfo and known secrets repeated elsewhere in
the bundle. Binary bodies and explicit `raw_request`/`raw_response` fields are omitted.
Outputs are created with owner-only permissions and must be new files; originals are
never overwritten. Keep raw sensitive captures outside shared artifacts and Git.

Redaction is best effort. Unrecognized tokens, personal data, opaque text and secrets
in unusual encodings may remain. Review the exported artifact before sharing. Preserve
redacted originals' source references so a reviewer can locate protected source data.
