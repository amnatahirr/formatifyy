#!/usr/bin/env python3
"""Verify Google Drive tokens in database"""

import sqlite3
from database import get_db

def check_tokens():
    conn = get_db()
    cursor = conn.cursor()
    
    print("\n=== Google Drive Tokens Status ===\n")
    
    # Check all users
    users = cursor.execute("SELECT id, username, email FROM users").fetchall()
    print(f"Total users in database: {len(users)}\n")
    
    for user in users:
        user_id = user["id"]
        email = user["email"]
        
        token = cursor.execute(
            "SELECT id, access_token, refresh_token, token_expiry FROM google_drive_tokens WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        
        if token:
            access_len = len(token["access_token"]) if token["access_token"] else 0
            refresh = "Yes" if token["refresh_token"] else "No"
            expiry = token["token_expiry"] if token["token_expiry"] else "Not set"
            print(f"User {user_id}: {email}")
            print(f"  - Access Token: {access_len} chars")
            print(f"  - Refresh Token: {refresh}")
            print(f"  - Expiry: {expiry}\n")
        else:
            print(f"User {user_id}: {email}")
            print(f"  - NO TOKENS STORED\n")
    
    conn.close()

if __name__ == "__main__":
    check_tokens()
