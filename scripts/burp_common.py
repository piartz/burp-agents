"""Shared capability catalog and validated engagement settings. Python 3.11+."""
from pathlib import Path
import math
import tomllib

ANALYSIS_TOOLS = (
    'get_proxy_http_history', 'get_proxy_http_history_regex', 'get_scanner_issues',
    'get_organizer_items', 'get_organizer_items_regex',
    'get_proxy_websocket_history', 'get_proxy_websocket_history_regex',
)
SEND_TOOLS = ('send_http1_request', 'send_http2_request')
TAB_TOOLS = ('create_repeater_tab', 'create_repeater_tab_http2')
ACTIVE_TOOLS = ANALYSIS_TOOLS + SEND_TOOLS + TAB_TOOLS + (
    'generate_collaborator_payload', 'get_collaborator_interactions',
)
PROFILES = {'analysis': ANALYSIS_TOOLS, 'active': ACTIVE_TOOLS}


def load_engagement(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        config = tomllib.load(stream)
    if not isinstance(config.get('engagement_id'), str) or not config['engagement_id'].strip():
        raise ValueError('engagement_id must be a nonempty string')
    limits = config['limits']
    for key in ('max_requests', 'max_polls', 'max_history_count'):
        if type(limits.get(key)) is not int or limits[key] < (1 if key == 'max_history_count' else 0):
            raise ValueError(f'limits.{key} must be a nonnegative integer (history count > 0)')
    pace = limits.get('min_interval_seconds')
    if type(pace) not in (int, float) or not math.isfinite(pace) or pace < 0:
        raise ValueError('min_interval_seconds must be finite and nonnegative')
    for key in ('allowed_methods', 'excluded_paths'):
        if not isinstance(config.get(key), list) or any(not isinstance(v, str) for v in config[key]):
            raise ValueError(f'{key} must be a list of strings')
    if not config['allowed_methods']:
        raise ValueError('allowed_methods must not be empty')
    targets = config.get('targets', [])
    if not targets:
        raise ValueError('At least one exact target is required')
    for target in targets:
        host = target.get('host')
        if not isinstance(host, str) or not host or any(c in host for c in '/*?@#\\\r\n '):
            raise ValueError('targets require exact hostnames or IPs, without wildcards')
        if type(target.get('port')) is not int or not 1 <= target['port'] <= 65535:
            raise ValueError('target.port must be 1..65535')
        if type(target.get('https')) is not bool:
            raise ValueError('target.https must be a boolean')
    upstream = config['upstream']
    if not isinstance(upstream.get('command'), str) or not upstream['command']:
        raise ValueError('upstream.command is required')
    if not isinstance(upstream.get('args'), list) or any(not isinstance(a, str) for a in upstream['args']):
        raise ValueError('upstream.args must be a list of strings')
    config['state_path'] = str(path.parent / config.get('state_path', '.burp/state.sqlite3'))
    return config
