#!/usr/bin/env python3
"""Compare saved structured responses; optionally check session identity offline."""
import argparse
import json
from pathlib import Path
import tomllib

from burp_evidence import compare_responses, session_health


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('variant', type=Path)
    parser.add_argument('--engagement', type=Path)
    parser.add_argument('--account', help='Check both responses against this account label')
    options = parser.parse_args()
    try:
        config = tomllib.loads(options.engagement.read_text()) if options.engagement else {}
        baseline, variant = (json.loads(p.read_text()) for p in (options.baseline, options.variant))
        result = compare_responses(baseline, variant, config.get('comparison'))
        if options.account:
            account = next((a for a in config.get('accounts', []) if a['label'] == options.account), None)
            if account is None:
                raise ValueError('Account label not found in engagement')
            result['sessions'] = [session_health(r, account) for r in (baseline, variant)]
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
