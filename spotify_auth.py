#!/usr/bin/env python3
"""One-time Spotify sign-in: writes spotify_token.json for the dashboard.

Create an app at https://developer.spotify.com/dashboard (API: Web API,
redirect URI exactly http://127.0.0.1:8888/callback), then on a machine with
a web browser (e.g. the Mac):

    python3 spotify_auth.py CLIENT_ID      # then paste the secret when asked

Approve the access in the browser, then copy spotify_token.json to the
dashboard directory on the Pi. It holds the client ID/secret and a refresh
token, so main.py needs no other Spotify settings. Keep it out of git.
"""
import base64
import getpass
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

REDIRECT_URI = 'http://127.0.0.1:8888/callback'
SCOPES = 'user-read-currently-playing user-read-recently-played'
HERE = os.path.dirname(os.path.realpath(__file__))
TOKEN = os.path.join(HERE, 'spotify_token.json')

if len(sys.argv) not in (2, 3):
    sys.exit(__doc__)
client_id = sys.argv[1]
client_secret = sys.argv[2] if len(sys.argv) == 3 else getpass.getpass('Client secret (hidden): ').strip()
if not client_secret:
    sys.exit('No client secret given.')
state = secrets.token_urlsafe(16)
result = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != '/callback':
            self.send_response(404); self.end_headers(); return
        q = urllib.parse.parse_qs(url.query)
        if q.get('state', [''])[0] != state:
            result['error'] = 'state mismatch'
        elif 'error' in q:
            result['error'] = q['error'][0]
        else:
            result['code'] = q.get('code', [''])[0]
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'Done. You can close this tab and go back to the terminal.')

    def log_message(self, *args):
        pass


server = HTTPServer(('127.0.0.1', 8888), Handler)
threading.Thread(target=server.handle_request, daemon=True).start()

auth_url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
    'client_id': client_id, 'response_type': 'code', 'redirect_uri': REDIRECT_URI,
    'scope': SCOPES, 'state': state,
})
print(f"Opening the browser to sign in. If it doesn't open, visit:\n{auth_url}\n")
webbrowser.open(auth_url)

for _ in range(300):
    if result: break
    time.sleep(1)
server.server_close()
if 'code' not in result:
    sys.exit(f"Sign-in failed: {result.get('error', 'timed out after 5 minutes')}")

basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
req = urllib.request.Request(
    'https://accounts.spotify.com/api/token',
    data=urllib.parse.urlencode({'grant_type': 'authorization_code', 'code': result['code'],
                                 'redirect_uri': REDIRECT_URI}).encode(),
    headers={'Authorization': f'Basic {basic}',
             'Content-Type': 'application/x-www-form-urlencoded'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        tok = json.load(resp)
except urllib.error.HTTPError as e:
    sys.exit(f"Token exchange failed ({e.code}): {e.read().decode(errors='replace')}")

with open(TOKEN, 'w') as f:
    json.dump({'client_id': client_id, 'client_secret': client_secret,
               'refresh_token': tok['refresh_token'], 'access_token': tok['access_token'],
               'expires_at': time.time() + tok.get('expires_in', 3600) - 60}, f, indent=2)
os.chmod(TOKEN, 0o600)
print(f"Wrote {TOKEN}. Copy it to the dashboard directory on the Pi.")
