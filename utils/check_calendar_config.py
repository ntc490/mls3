#!/usr/bin/env python3
"""
Debug script to check Google Calendar configuration
"""
import os
import config
from utils.google_calendar import is_calendar_enabled

print("=" * 60)
print("Google Calendar Configuration Check")
print("=" * 60)

print(f"\n1. GOOGLE_CALENDAR_ENABLED: {config.GOOGLE_CALENDAR_ENABLED}")
print(f"   Environment variable MLS3_GOOGLE_CALENDAR: {os.getenv('MLS3_GOOGLE_CALENDAR', 'NOT SET')}")

print(f"\n2. CREDENTIALS_FILE: {config.CREDENTIALS_FILE}")
print(f"   File exists: {os.path.exists(config.CREDENTIALS_FILE)}")

print(f"\n3. BISHOP_CALENDAR_ID: {config.BISHOP_CALENDAR_ID if config.BISHOP_CALENDAR_ID else 'NOT SET'}")
print(f"   Environment variable MLS3_BISHOP_CALENDAR_ID: {os.getenv('MLS3_BISHOP_CALENDAR_ID', 'NOT SET')}")

print(f"\n4. COUNSELOR_CALENDAR_ID: {config.COUNSELOR_CALENDAR_ID if config.COUNSELOR_CALENDAR_ID else 'NOT SET'}")
print(f"   Environment variable MLS3_COUNSELOR_CALENDAR_ID: {os.getenv('MLS3_COUNSELOR_CALENDAR_ID', 'NOT SET')}")

print(f"\n5. TOKEN_FILE: {config.TOKEN_FILE}")
print(f"   File exists: {os.path.exists(config.TOKEN_FILE)}")

print(f"\n" + "=" * 60)
print(f"is_calendar_enabled() returns: {is_calendar_enabled()}")
print("=" * 60)

if not is_calendar_enabled():
    print("\n⚠️  Calendar is NOT enabled. Check the issues above.")
else:
    print("\n✓ Calendar is enabled and configured!")
