"""Run beside a copied incomplete-form.php on a host with PHP. Never sends mail."""
import base64
import json
import pathlib
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

root = pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='rcn-incomplete-test-') as directory:
    temp = pathlib.Path(directory)
    endpoint = root / 'incomplete-form.php'
    if not endpoint.exists():
        endpoint = root.parent / 'incomplete-form.php'
    (temp / 'incomplete-form.php').write_bytes(endpoint.read_bytes())
    subprocess.run(['php', '-l', str(endpoint)], check=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    # Override sendmail with a local file sink. Nothing reaches SMTP or a recipient.
    server = subprocess.Popen(['php', '-d', 'sendmail_path=/usr/bin/tee ' + str(temp / 'mail.txt'),
                               '-d', 'sys_temp_dir=' + directory, '-S', f'127.0.0.1:{port}', '-t', directory],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def call(data=None, origin='https://book.rivercruisenetwork.com', content='application/json', method='POST'):
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(f'http://127.0.0.1:{port}/incomplete-form.php', data=body,
                                         headers={'Origin': origin, 'Content-Type': content}, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        return response.status, json.loads(response.read())['result']
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.1): break
            except OSError: time.sleep(0.1)
        payload = {'page': '/avalon-waterways.html', 'fields': {'first_name': 'TEST', 'email': 'btl101@gmail.com'}, 'is_test': True}
        assert call(method='GET') == (405, 'method_not_allowed')
        assert call(payload, origin='https://other.example') == (403, 'origin_not_allowed')
        assert call(payload, content='text/plain') == (415, 'json_required')
        assert call({'page': [], 'fields': {}}) == (400, 'invalid_page')
        assert call({'page': '/', 'fields': {'first_name': []}}) == (400, 'invalid_field')
        assert call({'page': '/', 'fields': {'additional_info': 'x' * 17000}}) == (413, 'too_large')
        assert not (temp / 'mail.txt').exists(), 'Rejected requests must not email'
        assert call(payload) == (200, 'accepted')
        mail = (temp / 'mail.txt').read_text()
        headers, encoded = mail.split('\n\n', 1)
        body = base64.b64decode(encoded).decode()
        assert 'To: btl101@gmail.com' in headers
        assert 'sales@' not in mail and '\nCc:' not in headers and '\nBcc:' not in headers
        assert '[TEST]' in headers and 'Missing required fields: Phone, Preferred itinerary' in body
        assert 'Email: btl101@gmail.com' in body and 'Ireland:' in body and 'Toronto:' in body
        assert call(payload) == (200, 'duplicate')
        assert (temp / 'mail.txt').read_text() == mail
        complete = {'page': '/', 'fields': {name: 'filled' for name in
            ['first_name', 'email', 'phone', 'destination', 'travel_date', 'duration', 'guests', 'budget', 'operator']}}
        assert call(complete) == (422, 'no_missing_required_fields')
        assert call({'page': '/', 'fields': {}}) == (200, 'accepted'), 'Even empty attempted forms are reported'
        for i in range(28):
            payload['fields']['first_name'] = 'TEST ' + str(i)
            assert call(payload) == (200, 'accepted')
        payload['fields']['first_name'] = 'OVER LIMIT'
        assert call(payload) == (429, 'rate_limited')
        state_file = next(temp.glob('rcn-incomplete-*.json'))
        state = state_file.read_text()
        assert 'btl101@gmail.com' not in state and 'TEST' not in state and '127.0.0.1' not in state
        assert state_file.stat().st_mode & 0o777 == 0o600
        print('PASS: Ben-only mail, required-field validation, empty attempts, deduplication, CSRF/size/type guards, private hash-only state and rate limit; no real emails sent.')
    finally:
        server.terminate()
        server.wait(timeout=5)
