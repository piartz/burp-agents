#!/usr/bin/env python3
"""stdio MCP gateway enforcing an engagement profile before forwarding to Burp."""
import argparse
import json
import subprocess
import sys
import threading

from burp_common import PROFILES, load_engagement
from burp_policy import Denied, Policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engagement', default='engagement.toml')
    parser.add_argument('--profile', choices=PROFILES, default='analysis')
    options = parser.parse_args()
    try:
        config = load_engagement(options.engagement)
        policy = Policy(config, options.profile)
        upstream = subprocess.Popen([config['upstream']['command'], *config['upstream']['args']],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                    encoding='utf-8', bufsize=1)
    except (OSError, ValueError, KeyError) as exc:
        print(f'Gateway startup failed: {exc}', file=sys.stderr)
        return 1
    lock = threading.Lock()
    input_lock = threading.Lock()
    pending = {}

    def forward(message):
        with input_lock:
            upstream.stdin.write(json.dumps(message) + '\n')
            upstream.stdin.flush()

    def emit(message):
        with lock:
            print(json.dumps(message, ensure_ascii=False), flush=True)

    def error(identifier, code, message):
        emit({'jsonrpc': '2.0', 'id': identifier, 'error': {'code': code, 'message': message}})

    def relay():
        try:
            for line in upstream.stdout:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError('Upstream sent a non-object JSON-RPC message')
                # Do not allow upstream-initiated sampling, elicitation or tool requests.
                if 'method' in message and 'id' in message:
                    print('Gateway blocked an upstream-initiated request', file=sys.stderr)
                    forward({'jsonrpc': '2.0', 'id': message['id'], 'error': {
                        'code': -32601, 'message': 'Client requests are not exposed by this gateway'}})
                    continue
                with lock:
                    method = pending.pop(message.get('id'), None)
                if method == 'tools/list' and isinstance(message.get('result'), dict):
                    tools = message['result'].get('tools', [])
                    message['result']['tools'] = [t for t in tools if t.get('name') in policy.tools]
                if method == 'initialize' and isinstance(message.get('result'), dict):
                    message['result']['capabilities'] = {'tools': {'listChanged': True}}
                emit(message)
        except (ValueError, TypeError, OSError) as exc:
            print(f'Gateway upstream failure: {exc}', file=sys.stderr)
        finally:
            with lock:
                identifiers = list(pending)
                pending.clear()
            for identifier in identifiers:
                error(identifier, -32000, 'Upstream connection closed; result is unavailable')

    reader = threading.Thread(target=relay, daemon=True)
    reader.start()
    try:
        for line in sys.stdin:
            identifier = None
            try:
                message = json.loads(line)
                if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
                    raise ValueError('Expected a JSON-RPC 2.0 object')
                identifier = message.get('id')
                if identifier is not None and type(identifier) not in (str, int):
                    identifier = None
                    raise ValueError('Invalid request ID')
                with lock:
                    if identifier is not None and identifier in pending:
                        raise ValueError('Duplicate outstanding request ID')
                method = message.get('method')
                if method == 'tools/call':
                    if identifier is None:
                        raise Denied('Tool calls require a request ID')
                    params = message.get('params', {})
                    if not isinstance(params, dict):
                        raise ValueError('Tool params must be an object')
                    name, arguments = params.get('name'), params.get('arguments', {})
                    policy.validate(name, arguments)
                    policy.reserve(name)
                elif method not in ('initialize', 'ping', 'tools/list', 'notifications/initialized', 'notifications/cancelled'):
                    raise Denied('JSON-RPC method is not exposed by this gateway')
                if method == 'initialize':
                    params = message.setdefault('params', {})
                    if not isinstance(params, dict):
                        raise ValueError('Initialize params must be an object')
                    # No upstream-initiated sampling, roots, elicitation or other features.
                    params['capabilities'] = {}
                if identifier is not None:
                    with lock:
                        pending[identifier] = method
                forward(message)
            except Denied as exc:
                if identifier is not None:
                    error(identifier, -32001, str(exc))
            except (ValueError, TypeError) as exc:
                error(identifier, -32600, str(exc))
            except (OSError, BrokenPipeError):
                if identifier is not None:
                    error(identifier, -32000, 'Upstream unavailable; any reserved budget remains consumed')
                break
    finally:
        try:
            upstream.stdin.close()
        except OSError:
            pass
        try:
            upstream.wait(timeout=5)
        except subprocess.TimeoutExpired:
            upstream.terminate()
            try:
                upstream.wait(timeout=2)
            except subprocess.TimeoutExpired:
                upstream.kill()
                upstream.wait()
        reader.join(timeout=2)
        policy.db.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
