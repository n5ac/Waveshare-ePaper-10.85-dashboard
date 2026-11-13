#!/usr/bin/env python3
"""One-time Gmail sign-in: turns credentials.json into token.json.

main.py only *reads* token.json (and refreshes it); it never starts a sign-in.
Run this on a machine with a web browser (e.g. the Mac), then copy token.json
to the dashboard directory on the Pi.

    pip3 install google-auth-oauthlib
    python3 gmail_auth.py            # reads ./credentials.json, writes ./token.json
"""
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']  # must match main.py
HERE = os.path.dirname(os.path.realpath(__file__))
CREDS = os.path.join(HERE, 'credentials.json')
TOKEN = os.path.join(HERE, 'token.json')

if not os.path.exists(CREDS):
    sys.exit(f"Missing {CREDS}: download the Desktop OAuth client JSON from Google Cloud and save it there.")

flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
# prompt='consent' guarantees Google returns a refresh token, which the Pi needs
# to keep working without a browser.
creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')

with open(TOKEN, 'w') as f:
    f.write(creds.to_json())
print(f"Wrote {TOKEN} (refresh token: {'yes' if creds.refresh_token else 'NO, run again'})")
