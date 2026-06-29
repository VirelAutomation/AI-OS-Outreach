"""
Run this ONCE to get your Gmail refresh token.
It opens a browser, you log in with jxabros@gmail.com, approve access,
and the refresh token is printed. Paste it into .env as GMAIL_REFRESH_TOKEN.

Usage:
    python forge_system/get_gmail_token.py
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

CLIENT_FILE = os.getenv(
    "GOOGLE_OAUTH_CLIENT_FILE",
    str(Path(__file__).parent.parent / "credentials" / "google-oauth-client.json")
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
creds = flow.run_local_server(port=0)

print("\n" + "=" * 60)
print("GMAIL_REFRESH_TOKEN =", creds.refresh_token)
print("=" * 60)
print("\nPaste the line above into forge_system/.env")
print("The system will use jxabros@gmail.com for cold email sends.")
