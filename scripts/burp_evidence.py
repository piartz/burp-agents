"""Offline response comparison, explicit session checks, and evidence redaction."""
import base64
import copy
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_KEYS = frozenset({
    'authorization', 'proxy-authorization', 'cookie', 'set-cookie', 'x-api-key',
    'password', 'passwd', 'secret', 'client_secret', 'token', 'access_token',
    'refresh_token', 'id_token', 'api_key', 'apikey', 'csrf', 'csrf_token', 'session',
    'sessionid', 'jsessionid', 'phpsessid', 'csrftoken', 'x-csrf-token', 'x-xsrf-token',
    'signature', 'sig', 'x-amz-signature', 'x-amz-credential', 'x-amz-security-token',
    'x-goog-signature', 'x-goog-credential', 'oauth_token', 'authorization_code',
})
REDACTED = '[REDACTED]'


def pointer_get(document, pointer):
    if not pointer.startswith('/'):
        raise ValueError('JSON pointers must start with /')
    value = document
    for segment in pointer[1:].split('/'):
        key = segment.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def remove_pointer(document, pointer):
    parts = pointer.rsplit('/', 1)
    parent = pointer_get(document, parts[0]) if parts[0] else document
    key = parts[1].replace('~1', '/').replace('~0', '~')
    if isinstance(parent, list):
        # Preserve array order/indices while masking an explicit volatile field.
        parent[int(key)] = '<ignored>'
    else:
        parent.pop(key, None)


def response_data(response):
    if not isinstance(response, dict):
        raise ValueError('Response must be an object')
    if type(response.get('status')) is not int or not 100 <= response['status'] <= 599:
        raise ValueError('Response status must be an HTTP status integer')
    if type(response.get('body_complete')) is not bool:
        raise ValueError('body_complete must explicitly state completeness')
    headers = response.get('headers', {})
    if not isinstance(headers, dict):
        raise ValueError('Response headers must be an object')
    normalized_headers = {str(k).lower(): v for k, v in headers.items()}
    if 'body_base64' in response:
        body = base64.b64decode(response['body_base64'], validate=True)
        length_source = 'decoded_base64_bytes'
    elif isinstance(response.get('body'), str):
        body = response['body'].encode('utf-8')
        length_source = 'utf8_representation_bytes'
    else:
        raise ValueError('Response requires body text or body_base64')
    return normalized_headers, body, length_source


def compare_responses(baseline, variant, config=None):
    config = config or {}
    a_headers, a_body, a_length_source = response_data(baseline)
    b_headers, b_body, b_length_source = response_data(variant)
    complete = baseline['body_complete'] and variant['body_complete']
    ignored_headers = {h.lower() for h in config.get('ignored_headers', [])}
    header_changes = sorted(k for k in a_headers.keys() | b_headers.keys()
                            if k not in ignored_headers and a_headers.get(k) != b_headers.get(k))
    tolerance = config.get('length_tolerance_percent', 2)
    if type(tolerance) not in (float, int) or not 0 <= tolerance <= 100:
        raise ValueError('length_tolerance_percent must be in 0..100')
    raw_equal = a_body == b_body if complete else None
    normalized_equal = raw_equal
    applied, missing = [], []
    if complete:
        try:
            a_json, b_json = json.loads(a_body), json.loads(b_body)
        except (ValueError, UnicodeError):
            pass
        else:
            for pointer in config.get('ignored_json_pointers', []):
                if not isinstance(pointer, str) or not pointer.startswith('/'):
                    raise ValueError('Ignored JSON pointers must start with /')
                try:
                    pointer_get(a_json, pointer)
                    pointer_get(b_json, pointer)
                except (KeyError, IndexError, ValueError, TypeError):
                    missing.append(pointer)
                    continue
                remove_pointer(a_json, pointer)
                remove_pointer(b_json, pointer)
                applied.append(pointer)
            # JSON comparison ignores formatting and object-key order, preserves types.
            normalized_equal = json.dumps(a_json, sort_keys=True) == json.dumps(b_json, sort_keys=True)
    delta = len(b_body) - len(a_body) if complete else None
    beyond = abs(delta) > len(a_body) * tolerance / 100 if complete else None
    return {
        'status_changed': baseline['status'] != variant['status'],
        'changed_headers': header_changes,
        'ignored_headers': sorted(ignored_headers),
        'body_comparison_available': complete,
        'raw_body_equal': raw_equal,
        'normalized_body_equal': normalized_equal,
        'applied_json_pointers': applied,
        'unmatched_json_pointers': missing,
        'baseline_observed_bytes': len(a_body), 'variant_observed_bytes': len(b_body),
        'length_sources': [a_length_source, b_length_source],
        'length_delta': delta, 'length_beyond_tolerance': beyond,
        'length_tolerance_percent': tolerance,
        'interpretation': 'response differences only; access or vulnerability status needs explicit evidence',
    }


def session_health(response, account):
    headers, body, _ = response_data(response)
    if not response['body_complete']:
        return {'state': 'unknown', 'reason': 'incomplete session response'}
    if response['status'] == 401:
        return {'state': 'invalid', 'reason': 'session check returned 401'}
    location = headers.get('location', '')
    if isinstance(location, list):
        location = location[0] if location else ''
    if 300 <= response['status'] < 400 and any(
            urlsplit(location).path.startswith(p) for p in account.get('login_path_prefixes', [])):
        return {'state': 'invalid', 'reason': 'session check redirected to login'}
    pointer, expected = account.get('identity_pointer'), account.get('expected_identity')
    if not pointer or expected is None:
        return {'state': 'unknown', 'reason': 'no expected identity assertion supplied'}
    try:
        observed = pointer_get(json.loads(body), pointer)
    except (ValueError, KeyError, IndexError, TypeError, UnicodeError):
        return {'state': 'unknown', 'reason': 'expected identity field unavailable'}
    if not 200 <= response['status'] < 300:
        return {'state': 'unknown', 'reason': 'session check was not successful'}
    if observed != expected:
        return {'state': 'mismatch', 'reason': 'identity differs from the configured test account'}
    return {'state': 'valid', 'reason': 'successful response matched expected identity'}


def redact_evidence(value, extra_keys=()):
    """Best effort for structured evidence; omit binary bodies and raw HTTP blobs.

    Known secrets are also replaced in free text elsewhere in the same bundle.
    Unrecognized secrets cannot be discovered reliably: review before sharing.
    """
    keys = SECRET_KEYS | {str(k).lower() for k in extra_keys}
    secrets = set()

    def remember(v):
        if isinstance(v, str) and v and v != REDACTED:
            secrets.add(v)
        elif isinstance(v, (dict, list)):
            for item in v.values() if isinstance(v, dict) else v:
                remember(item)

    def remember_header(key, value):
        for item in value if isinstance(value, list) else [value]:
            if not isinstance(item, str):
                continue
            if key in {'authorization', 'proxy-authorization'} and ' ' in item:
                remember(item.split(' ', 1)[1])
            if key in {'cookie', 'set-cookie'}:
                pairs = item.split(';') if key == 'cookie' else item.split(';', 1)[:1]
                for pair in pairs:
                    if '=' in pair:
                        remember(pair.split('=', 1)[1].strip())

    def redact(v):
        if isinstance(v, dict):
            result = {}
            for key, item in v.items():
                if key.lower() in keys:
                    remember(item)
                    remember_header(key.lower(), item)
                    result[key] = REDACTED
                elif key.lower() in {'raw_request', 'raw_response', 'body_base64'}:
                    result[key] = '[OMITTED: unstructured or binary evidence]'
                else:
                    result[key] = redact(item)
            return result
        if isinstance(v, list):
            return [redact(item) for item in v]
        if isinstance(v, str):
            if v.lstrip().startswith(('{', '[')):
                try:
                    return json.dumps(redact(json.loads(v)), ensure_ascii=False)
                except ValueError:
                    pass
            if v.startswith(('https://', 'http://', 'wss://', 'ws://')):
                parsed = urlsplit(v)
                query = []
                for key, item in parse_qsl(parsed.query, keep_blank_values=True):
                    if key.lower() in keys:
                        remember(item)
                        item = REDACTED
                    query.append((key, item))
                netloc = parsed.netloc
                if '@' in netloc:
                    userinfo, netloc = netloc.rsplit('@', 1)
                    remember(userinfo)
                    netloc = REDACTED + '@' + netloc
                return urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(query), ''))
            # Form bodies and URL-like query fragments with recognized secret fields.
            for key in keys:
                pattern = re.compile(r'(?i)(\b' + re.escape(key) + r'=)([^&\s]+)')
                def replace(match):
                    remember(match[2])
                    return match[1] + REDACTED
                v = pattern.sub(replace, v)
            return v
        return v

    cleaned = redact(copy.deepcopy(value))

    def scrub(v):
        if isinstance(v, dict):
            return {k: scrub(item) for k, item in v.items()}
        if isinstance(v, list):
            return [scrub(item) for item in v]
        if isinstance(v, str):
            for secret in sorted(secrets, key=len, reverse=True):
                v = v.replace(secret, REDACTED)
            return v
        return v
    return scrub(cleaned)


def validate_bundle(bundle):
    if not isinstance(bundle, dict):
        raise ValueError('Evidence bundle must be an object')
    if bundle.get('schema_version') != 1 or not isinstance(bundle.get('engagement_id'), str):
        raise ValueError('Evidence requires schema_version=1 and engagement_id')
    records = bundle.get('records')
    if not isinstance(records, list):
        raise ValueError('Evidence records must be a list')
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('Each evidence record must be an object')
        required = ('id', 'agent', 'task', 'source_refs', 'observations', 'limitations')
        if (any(key not in record for key in required)
                or any(not isinstance(record[key], str) or not record[key].strip() for key in ('id', 'agent', 'task'))
                or record['id'] in seen):
            raise ValueError('Evidence records need unique string IDs and required fields')
        if any(not isinstance(record[key], list) for key in ('source_refs', 'observations', 'limitations')):
            raise ValueError('source_refs, observations and limitations must be arrays')
        seen.add(record['id'])
