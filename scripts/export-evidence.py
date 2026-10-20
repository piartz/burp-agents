#!/usr/bin/env python3
"""Validate and redact an evidence bundle to a new JSON or Markdown artifact."""
import argparse
import json
import os
from pathlib import Path

from burp_evidence import redact_evidence, validate_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--secret-key', action='append', default=[])
    options = parser.parse_args()
    try:
        bundle = json.loads(options.input.read_text())
        validate_bundle(bundle)
        cleaned = redact_evidence(bundle, options.secret_key)
        if options.format == 'json':
            output = json.dumps(cleaned, indent=2, ensure_ascii=False) + '\n'
        else:
            lines = ['# Engagement evidence', '', f"Engagement: {cleaned['engagement_id']}", '',
                     'Draft for review. Secrets are redacted on a best-effort basis.', '']
            for record in cleaned['records']:
                lines.extend([f"## {record['id']}", '', f"Agent: {record['agent']}", '',
                              f"Task: {record['task']}", ''])
                for field in ('source_refs', 'observations', 'limitations', 'request', 'response', 'comparison', 'reproduction_steps'):
                    if field in record:
                        lines.extend([f'### {field.replace("_", " ").title()}', '',
                                      '````json', json.dumps(record[field], indent=2, ensure_ascii=False), '````', ''])
            output = '\n'.join(lines)
        # Never overwrite original evidence or an existing export. Private by default.
        descriptor = os.open(options.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(output)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
