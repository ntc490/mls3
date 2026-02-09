#!/usr/bin/env python3
"""
One-time script to authorize Google Calendar access.
Run this once to generate the token.pickle file.
"""

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import config

SCOPES = ['https://www.googleapis.com/auth/calendar']

def authorize():
    """Run the OAuth flow to get credentials"""
    creds = None
    token_path = config.TOKEN_FILE
    credentials_path = config.CREDENTIALS_FILE

    # Check if we already have a token
    if os.path.exists(token_path):
        print(f"Token already exists at {token_path}")
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

        if creds and creds.valid:
            print("✓ Token is valid!")
            return True
        elif creds and creds.expired and creds.refresh_token:
            print("Token expired, refreshing...")
            creds.refresh(Request())
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            print("✓ Token refreshed!")
            return True

    # Check if credentials file exists
    if not os.path.exists(credentials_path):
        print(f"ERROR: Credentials file not found at {credentials_path}")
        print("Please download credentials.json from Google Cloud Console")
        return False

    print("Starting OAuth flow...")
    print()

    # Create flow
    flow = InstalledAppFlow.from_client_secrets_file(
        credentials_path,
        SCOPES
    )

    # Try to run local server (this handles everything automatically)
    try:
        print("Attempting to start local authorization server...")
        print("This will open your browser automatically.")
        print()
        print("If you see 'This site can't be reached', that's normal!")
        print("Just look at the URL and copy the entire URL from the address bar.")
        print()

        # Use run_local_server with port 0 (auto-select available port)
        creds = flow.run_local_server(
            port=0,
            open_browser=False  # Don't auto-open since Termux has issues
        )

        # Save the credentials
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

        print()
        print("="*70)
        print("✓ SUCCESS!")
        print("="*70)
        print(f"Token saved to: {token_path}")
        print()
        print("You can now use Google Calendar sync in MLS3!")
        print()
        return True

    except Exception as e:
        print(f"ERROR: Failed to authorize: {e}")
        print()
        print("The local server method didn't work.")
        print("Please report this error and we'll try a different approach.")
        return False

if __name__ == '__main__':
    print()
    print("Google Calendar Authorization for MLS3")
    print("=" * 70)
    print()

    success = authorize()

    if not success:
        print()
        print("Authorization failed. Please try again.")
        exit(1)
