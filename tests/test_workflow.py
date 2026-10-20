import concurrent.futures
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from burp_common import PROFILES, load_engagement
from burp_evidence import compare_responses, redact_evidence, session_health, validate_bundle
from burp_policy import Denied, Policy


def response(body, status=200, **values):
    return {'status': status, 'headers': {}, 'body': body, 'body_complete': True, **values}


def settings(directory, max_requests=2, interval=0):
    return {'engagement_id': 'test', 'state_path': str(Path(directory) / 'state.sqlite3'),
            'targets': [{'host': 'app.example.test', 'port': 443, 'https': True}],
            'allowed_methods': ['GET'], 'excluded_paths': ['/logout*', '/payments*'],
            'limits': {'max_requests': max_requests, 'max_polls': 1,
                       'max_history_count': 100, 'min_interval_seconds': interval}}


def http1(path='/api/orders/123', host='app.example.test', method='GET'):
    return {'targetHostname': host, 'targetPort': 443, 'usesHttps': True,
            'content': f'{method} {path} HTTP/1.1\r\nHost: {host}\r\n\r\n'}


def http2(path='/api/orders/123'):
    return {'targetHostname': 'app.example.test', 'targetPort': 443, 'usesHttps': True,
            'pseudoHeaders': {'method': 'GET', 'scheme': 'https', 'authority': 'app.example.test', 'path': path},
            'headers': {}, 'requestBody': ''}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = settings(self.temp.name)
        self.policy = Policy(self.config, 'active')

    def tearDown(self):
        self.policy.db.close()
        self.temp.cleanup()

    def test_protocols_and_scope(self):
        self.policy.validate('send_http1_request', http1())
        self.policy.validate('send_http2_request', http2())
        for args in [http1(host='outside.test'), http1(method='POST'), http1('/logout'),
                     http1('/%70ayments/1'), http1('/x/../payments/1'),
                     http1('/%2fpayments/1')]:
            with self.subTest(args=args), self.assertRaises(Denied):
                self.policy.validate('send_http1_request', args)

    def test_conflicting_authority(self):
        one = http1()
        one['content'] = one['content'].replace('Host: app.example.test', 'Host: outside.test')
        two = http2()
        two['pseudoHeaders'][':authority'] = 'outside.test'
        three = http2()
        three['headers']['Host'] = 'outside.test'
        for name, args in [('send_http1_request', one), ('send_http2_request', two), ('send_http2_request', three)]:
            with self.subTest(name=name), self.assertRaises(Denied):
                self.policy.validate(name, args)

    def test_analysis_denies_even_undiscovered_tools(self):
        analysis = Policy(self.config, 'analysis')
        try:
            for name in ('send_http1_request', 'create_repeater_tab', 'generate_collaborator_payload', 'set_project_options'):
                with self.assertRaises(Denied):
                    analysis.validate(name, http1())
        finally:
            analysis.db.close()

    def test_pagination_and_polling(self):
        self.policy.validate('get_proxy_http_history', {'count': 10, 'offset': 0})
        for args in ({'count': 101, 'offset': 0}, {'count': True, 'offset': 0}, {'count': 1, 'offset': -1}):
            with self.assertRaises(Denied):
                self.policy.validate('get_proxy_http_history', args)
        with self.assertRaises(Denied):
            self.policy.validate('get_collaborator_interactions', {})
        self.policy.reserve('get_collaborator_interactions')
        with self.assertRaises(Denied):
            self.policy.reserve('get_collaborator_interactions')

    def test_shared_budget_and_pacing(self):
        self.policy.db.close()
        config = settings(self.temp.name, max_requests=3, interval=0.03)
        def reserve(_):
            policy = Policy(config, 'active')
            try:
                policy.reserve('send_http1_request')
                return True
            except Denied:
                return False
            finally:
                policy.db.close()
        start = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            outcomes = list(executor.map(reserve, range(8)))
        self.assertEqual(sum(outcomes), 3)
        self.assertGreaterEqual(time.monotonic() - start, 0.05)
        self.policy = Policy(config, 'active')
        with self.assertRaises(Denied):
            self.policy.reserve('send_http2_request')


class EvidenceTests(unittest.TestCase):
    def test_equal_length_semantic_change_is_reported(self):
        result = compare_responses(response('{"owner":"a"}'), response('{"owner":"b"}'))
        self.assertEqual(result['length_delta'], 0)
        self.assertFalse(result['normalized_body_equal'])

    def test_explicit_normalization_preserves_raw(self):
        result = compare_responses(response('{"id":1,"timestamp":1}'),
                                   response('{ "timestamp":2, "id":1 }'),
                                   {'ignored_json_pointers': ['/timestamp', '/missing']})
        self.assertFalse(result['raw_body_equal'])
        self.assertTrue(result['normalized_body_equal'])
        self.assertEqual(result['applied_json_pointers'], ['/timestamp'])
        self.assertEqual(result['unmatched_json_pointers'], ['/missing'])
        self.assertFalse(compare_responses(response('{"id":true}'), response('{"id":1}'))['normalized_body_equal'])

    def test_incomplete_and_binary(self):
        result = compare_responses(response('abc'), response('abc', body_complete=False))
        self.assertIsNone(result['normalized_body_equal'])
        self.assertIsNone(result['length_delta'])
        binary = {'status': 200, 'headers': {}, 'body_base64': 'AAH/', 'body_complete': True}
        self.assertEqual(compare_responses(binary, binary)['baseline_observed_bytes'], 3)

    def test_session_identity_and_login(self):
        account = {'identity_pointer': '/user/id', 'expected_identity': 'a', 'login_path_prefixes': ['/login']}
        self.assertEqual(session_health(response('{"user":{"id":"a"}}'), account)['state'], 'valid')
        self.assertEqual(session_health(response('{"user":{"id":"b"}}'), account)['state'], 'mismatch')
        self.assertEqual(session_health(response('', status=302, headers={'Location': '/login'}), account)['state'], 'invalid')
        self.assertEqual(session_health(response('', status=401), account)['state'], 'invalid')
        self.assertEqual(session_health(response('', status=403), account)['state'], 'unknown')
        self.assertEqual(session_health(response('<html>Login</html>'), account)['state'], 'unknown')

    def test_redaction_and_repeated_secret(self):
        evidence = {'headers': {'Authorization': 'Bearer abc123', 'Cookie': 'session=secret'},
                    'url': 'https://user:pass@app.example.test/api?access_token=tok123&key=ok',
                    'body': '{"password":"private123","owner":"test-user-a"}',
                    'notes': 'Observed abc123; secret; private123; tok123',
                    'raw_response': 'private raw payload', 'body_base64': 'c2VjcmV0'}
        text = json.dumps(redact_evidence(evidence))
        for secret in ('abc123', 'private123', 'tok123', 'user:pass', 'private raw payload', 'c2VjcmV0'):
            self.assertNotIn(secret, text)
        self.assertIn('test-user-a', text)
        self.assertIn('private123', evidence['body'])
        signed = redact_evidence({'url': 'https://app.example.test/file?X-Amz-Signature=sign123&X-Amz-Credential=cred123'})
        self.assertNotIn('sign123', signed['url'])
        self.assertNotIn('cred123', signed['url'])

    def test_export_is_private_and_does_not_overwrite(self):
        bundle = json.loads((ROOT / 'config/evidence.example.json').read_text())
        validate_bundle(bundle)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'export.json'
            command = [sys.executable, str(ROOT / 'scripts/export-evidence.py'),
                       str(ROOT / 'config/evidence.example.json'), '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertNotIn('EXAMPLE_ONLY', output.read_text())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        bundle['records'].append(bundle['records'][0])
        with self.assertRaises(ValueError):
            validate_bundle(bundle)


class GeneratorTests(unittest.TestCase):
    def test_generation_parity_stale_check_and_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            shutil.copytree(ROOT / 'scripts', fixture / 'scripts')
            shutil.copytree(ROOT / 'agents', fixture / 'agents')
            command = [sys.executable, str(fixture / 'scripts/sync-agents.py')]
            subprocess.run(command, check=True, capture_output=True)
            subprocess.run(command + ['--check'], check=True, capture_output=True)
            self.assertEqual(len(list(fixture.glob('.codex/agents/*.toml'))), 8)
            union = set()
            for source in fixture.glob('agents/*.md'):
                header, body = source.read_text()[4:].split('\n---\n', 1)
                metadata = dict(line.split(': ', 1) for line in header.splitlines())
                union.update(metadata['tools'].split(', '))
                codex = tomllib.loads((fixture / '.codex/agents' / (source.stem + '.toml')).read_text())
                claude = (fixture / '.claude/agents' / source.name).read_text()
                self.assertTrue(claude.endswith(codex['developer_instructions']))
                self.assertIn('Shared engagement and evidence contract', codex['developer_instructions'])
                self.assertNotIn('model', codex)
            self.assertEqual(union, set(PROFILES['active']))
            for profile in PROFILES:
                config = tomllib.loads((fixture / f'config/mcp/codex-{profile}.toml').read_text())
                self.assertEqual(set(config['mcp_servers']['burp']['enabled_tools']), set(PROFILES[profile]))
            generated = fixture / '.codex/agents/burp-triager.toml'
            before = generated.read_bytes()
            contract = fixture / 'agents/_shared/contract.md'
            contract.write_text(contract.read_text() + '\nChanged shared requirement.\n')
            self.assertEqual(subprocess.run(command + ['--check'], capture_output=True).returncode, 1)
            self.assertEqual(generated.read_bytes(), before)


class GatewayIntegrationTests(unittest.TestCase):
    def test_mock_mcp_transport_and_enforcement(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            mock = directory / 'mock.py'
            mock.write_text('''import sys, json
for line in sys.stdin:
    m = json.loads(line)
    if 'id' not in m: continue
    method = m['method']
    if method == 'initialize': result = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}, 'resources': {}}, 'serverInfo': {'name': 'mock', 'version': '1'}}
    elif method == 'tools/list': result = {'tools': [{'name': n} for n in ['get_proxy_http_history', 'send_http1_request', 'set_project_options']]}
    else: result = {'content': [{'type': 'text', 'text': m['params']['name']}]}
    print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': result}), flush=True)
''')
            config = (ROOT / 'config/engagement.example.toml').read_text()
            config = config.replace('command = "/absolute/path/to/java"', 'command = ' + json.dumps(sys.executable))
            config = config.replace('args = ["-jar", "/absolute/path/to/mcp-proxy-all.jar", "--sse-url", "http://127.0.0.1:9876"]', 'args = [' + json.dumps(str(mock)) + ']')
            config = config.replace('min_interval_seconds = 1.0', 'min_interval_seconds = 0.0').replace('max_requests = 30', 'max_requests = 1')
            engagement = directory / 'engagement.toml'
            engagement.write_text(config)
            load_engagement(engagement)
            def request(identifier, method, params=None):
                return {'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params or {}}
            def call(identifier, name, args):
                return request(identifier, 'tools/call', {'name': name, 'arguments': args})
            messages = [request(1, 'initialize'), request(2, 'tools/list'),
                        call(3, 'get_proxy_http_history', {'count': 5, 'offset': 0}),
                        call(4, 'send_http1_request', http1()), call(5, 'set_project_options', {}),
                        request(6, 'resources/read')]
            def run(profile, messages):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/burp-gateway.py'), '--engagement', str(engagement), '--profile', profile],
                                        input=''.join(json.dumps(m) + '\n' for m in messages), capture_output=True, text=True, timeout=12)
                self.assertEqual(result.returncode, 0, result.stderr)
                return {m['id']: m for m in map(json.loads, result.stdout.splitlines())}
            analysis = run('analysis', messages)
            self.assertEqual([t['name'] for t in analysis[2]['result']['tools']], ['get_proxy_http_history'])
            self.assertIn('result', analysis[3])
            for identifier in (4, 5, 6): self.assertIn('error', analysis[identifier])
            active = run('active', [call(7, 'send_http1_request', http1()), call(8, 'send_http1_request', http1()),
                                    call(9, 'send_http1_request', http1(host='outside.test'))])
            self.assertIn('result', active[7])
            self.assertIn('error', active[8])
            self.assertIn('error', active[9])
            # Restarting the gateway must not reset the engagement budget.
            restarted = run('active', [call(10, 'send_http1_request', http1())])
            self.assertIn('error', restarted[10])


if __name__ == '__main__':
    unittest.main()
