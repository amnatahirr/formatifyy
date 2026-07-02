from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, EmailStr
import bcrypt
from datetime import datetime
from database import get_db
import requests
import os
from config import settings
import uuid
from urllib.parse import quote
from auth_utils import create_access_token

from auth_utils import create_access_token
from fastapi.responses import RedirectResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory store for OAuth sessions (use Redis in production)
oauth_sessions = {}

class SignUpRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    university_id: int = None

class SignUpResponse(BaseModel):
    id: int
    username: str
    email: str
    message: str

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    token: str

@router.post("/signup", response_model=SignUpResponse)
async def signup(request: SignUpRequest):
    """Register a new user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user already exists
        existing = cursor.execute(
            "SELECT id FROM users WHERE email = ?",
            (request.email,)
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash password
        hashed_password = bcrypt.hashpw(
            request.password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
        
        # Create user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, university_id, role)
            VALUES (?, ?, ?, ?, ?)
        """, (
            request.username,
            request.email,
            hashed_password,
            request.university_id,
            "student"
        ))
        conn.commit()
        
        user_id = cursor.lastrowid
        conn.close()
        
        return SignUpResponse(
            id=user_id,
            username=request.username,
            email=request.email,
            message="User registered successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login user and return token"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Find user by email
        user = cursor.execute(
            "SELECT id, username, email, password_hash, role FROM users WHERE email = ?",
            (request.email,)
        ).fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not bcrypt.checkpw(
            request.password.encode('utf-8'),
            user["password_hash"].encode('utf-8')
        ):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        conn.close()
        
        # Create simple token (use JWT in production)
        token = create_access_token({"user_id": user["id"]})
        print("LOGIN USER:", user["email"], user["role"])
        return LoginResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            role=user["role"],
            token=token
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/google/authorize")
async def google_authorize(link_to_user_id: int = Query(None)):
    """Return Google OAuth URL for the app to open in browser.
    
    Args:
        link_to_user_id: Optional user ID to link Google Drive tokens to existing account.
                        If provided, tokens will be stored for this user instead of creating new one.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID environment variable.")
    
    # Create a session ID to track this OAuth flow
    session_id = str(uuid.uuid4())
    oauth_sessions[session_id] = {
        "provider": "google", 
        "status": "pending",
        "link_to_user_id": link_to_user_id  # Store the user ID to link tokens to
    }
    
    # Use localhost redirect URI for Desktop applications
    # This works with all OAuth client ID types and is more reliable
    redirect_uri = "http://localhost:8000/api/auth/google/callback"
    
    # URL encode the redirect URI
    encoded_redirect_uri = quote(redirect_uri, safe='')
    
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        "response_type=code&"
        f"redirect_uri={encoded_redirect_uri}&"
        "scope=openid%20email%20profile%20https://www.googleapis.com/auth/drive&"
        "access_type=offline&"
        "prompt=consent&"
        f"state={session_id}"
    )
    print(f"[v0] Google OAuth URL created for session {session_id}")
    print(f"[v0] Redirect URI: {redirect_uri}")
    print(f"[v0] Link to user ID: {link_to_user_id}")
    # Return the URL as plain text that the app can open
    return google_auth_url

@router.get("/google/callback")
async def google_callback(code: str = Query(...), state: str = Query(...)):
    """Handle Google OAuth callback from localhost browser redirect"""
    try:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(status_code=400, detail="Google OAuth not configured")
        
        print(f"[v0] Google callback received with state: {state}")
        
        # Get the session to check if we need to link to existing user
        session_data = oauth_sessions.get(state, {})
        link_to_user_id = session_data.get("link_to_user_id")
        print(f"[v0] Link to user ID from session: {link_to_user_id}")
        
        # Exchange code for token
        token_url = "https://oauth2.googleapis.com/token"
        # Use the same localhost redirect URI that was used in the initial request
        redirect_uri = "http://localhost:8000/api/auth/google/callback"
        
        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        
        token_response = requests.post(token_url, data=token_data)
        if token_response.status_code != 200:
            print(f"[v0] Token exchange failed: {token_response.text}")
            raise Exception("Failed to exchange code for token")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        
        # Get user info from Google
        userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        
        if userinfo_response.status_code != 200:
            raise Exception("Failed to get user info from Google")
        
        user_info = userinfo_response.json()
        google_email = user_info.get("email")
        google_username = user_info.get("name", google_email.split("@")[0])
        
        print(f"[v0] Google auth successful for: {google_email}")
        
        # Create or get user in database
        conn = get_db()
        cursor = conn.cursor()
        
        # If link_to_user_id is provided, link tokens to that user instead of creating/finding by Google email
        if link_to_user_id:
            # Verify the user exists
            user = cursor.execute(
                "SELECT id, username, email, role FROM users WHERE id = ?",
                (link_to_user_id,)
            ).fetchone()
            
            if not user:
                conn.close()
                raise HTTPException(status_code=404, detail="User to link not found")
            
            user_id = user["id"]
            username = user["username"]
            email = user["email"]
            role = user["role"]
            print(f"[v0] Linking Google Drive to existing user: {email} (ID: {user_id})")
        else:
            # Original behavior: find or create user by Google email
            user = cursor.execute(
                "SELECT id, username, email, role FROM users WHERE email = ?",
                (google_email,)
            ).fetchone()
            
            if not user:
                # Create new user
                hashed_password = bcrypt.hashpw(
                    "oauth_user".encode('utf-8'),
                    bcrypt.gensalt()
                ).decode('utf-8')
                
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, university_id, role)
                    VALUES (?, ?, ?, ?, ?)
                """, (google_username, google_email, hashed_password, 1, "student"))
                conn.commit()
                
                user_id = cursor.lastrowid
                username = google_username
                email = google_email
                role = "student"
                print(f"[v0] Created new user: {google_email}")
            else:
                user_id = user["id"]
                role = user["role"]
                username = user["username"]
                email = user["email"]
                print(f"[v0] Found existing user: {google_email}")
        
        # Store Google OAuth tokens for Drive access BEFORE closing connection
        refresh_token = tokens.get("refresh_token")
        token_expiry = tokens.get("expires_in")
        
        print(f"[v0] Storing Google Drive tokens for user {user_id}")
        print(f"[v0] Access token length: {len(access_token) if access_token else 0}")
        print(f"[v0] Refresh token: {'Yes' if refresh_token else 'No'}")
        print(f"[v0] Token expiry: {token_expiry}")
        
        try:
            # Use INSERT OR REPLACE (UPSERT) to handle both insert and update
            cursor.execute(
                """INSERT OR REPLACE INTO google_drive_tokens (user_id, access_token, refresh_token, token_expiry, created_at, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (user_id, access_token, refresh_token, token_expiry)
            )
            conn.commit()
            
            # Verify the tokens were actually saved
            verify = cursor.execute(
                "SELECT access_token FROM google_drive_tokens WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            
            if verify:
                print(f"[v0] Verified Google Drive tokens stored for user {user_id}")
            else:
                print(f"[v0] Verification failed - tokens not found after insert")
                
        except Exception as token_err:
            print(f"[v0] Token storage error: {token_err}")
            import traceback
            traceback.print_exc()
        
        conn.close()
        
        # Create token
        token = create_access_token({"user_id": user_id})
        
        
        # Store the session data for the app to retrieve
        if state in oauth_sessions:
            oauth_sessions[state] = {
                "provider": "google",
                "status": "authenticated",
                "id": user_id,
                "username": username,
                "email": email,
                "role": role,
                "token": token,
                "has_google_drive": True,
                "google_email": google_email  # Store the Google email used for Drive
            }
            print(f"[v0] Updated session {state} with user data")
        
        # Show success message in browser
        display_name = google_email if link_to_user_id else username
        message = "Google Drive connected successfully!" if link_to_user_id else "Sign In Successful"
        
        html_response = f"""
        <html>
        <head><title>Formatify - {message}</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: white;">
            <h1 style="color: #4ade80;">&#10003; {message}</h1>
            <p>Google Account: {google_email}</p>
            {"<p>Linked to account: " + email + "</p>" if link_to_user_id else "<p>Welcome, " + username + "!</p>"}
            <p>You can now return to the Formatify app.</p>
            <p style="color: #888; margin-top: 30px; font-size: 12px;">
                You can close this window.
            </p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_response)
    except Exception as e:
        print(f"[v0] Google callback error: {e}")
        html_response = f"""
        <html>
        <head><title>Formatify - Failed</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: white;">
            <h1 style="color: #ef4444;">&#10007; Connection Failed</h1>
            <p>Error: {str(e)}</p>
            <p>Please try again in the app.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_response)

@router.get("/google/debug/tokens")
async def debug_tokens(user_id: int = Query(...)):
    """Debug endpoint to check if tokens are stored"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user exists
        user = cursor.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            conn.close()
            return {"error": "User not found", "user_id": user_id}
        
        # Check if tokens exist
        token = cursor.execute(
            "SELECT id, access_token, refresh_token, token_expiry, created_at, updated_at FROM google_drive_tokens WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        
        conn.close()
        
        if token:
            return {
                "user_id": user_id,
                "email": user["email"],
                "tokens_found": True,
                "access_token_length": len(token["access_token"]) if token["access_token"] else 0,
                "has_refresh_token": bool(token["refresh_token"]),
                "token_expiry": token["token_expiry"],
                "created_at": token["created_at"],
                "updated_at": token["updated_at"]
            }
        else:
            return {
                "user_id": user_id,
                "email": user["email"],
                "tokens_found": False,
                "message": "No Google Drive tokens stored for this user"
            }
    except Exception as e:
        return {"error": str(e)}

@router.get("/google/status")
async def google_status():
    """Check if Google OAuth authentication is complete"""
    # Return the latest authenticated session
    for session_id, session_data in list(oauth_sessions.items()):
        if session_data.get("provider") == "google" and session_data.get("status") == "authenticated":
            # Remove session after retrieval
            session = oauth_sessions.pop(session_id)
            return {
                "authenticated": True,
                "id": session.get("id"),
                "username": session.get("username"),
                "email": session.get("email"),
                "role": session.get("role"),
                "token": session.get("token"),
                "has_google_drive": session.get("has_google_drive", False),
                "google_email": session.get("google_email")
            }
    
    return {"authenticated": False}

@router.get("/google/drive-picker")
async def google_drive_picker(user_id: int = Query(...)):
    """Return Google Drive picker URL for selecting documents"""
    try:
        # Check if user has Google Drive tokens
        conn = get_db()
        cursor = conn.cursor()
        
        token_row = cursor.execute(
            "SELECT access_token FROM google_drive_tokens WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        
        conn.close()
        
        if not token_row:
            raise HTTPException(status_code=401, detail="Google Drive not authorized. Please sign in with Google first.")
        
        # Create a unique picker session
        picker_session_id = str(uuid.uuid4())
        oauth_sessions[picker_session_id] = {
            "type": "drive_picker",
            "user_id": user_id,
            "status": "pending"
        }
        
        # Return a URL that opens Google Drive for file selection
        # The user will need to select a file and we'll handle it via a callback
        drive_picker_url = (
            "https://drive.google.com/drive/u/0/home?"
            f"state={picker_session_id}"
        )
        
        print(f"[v0] Created Drive picker session {picker_session_id} for user {user_id}")
        
        return {
            "picker_url": drive_picker_url,
            "session_id": picker_session_id,
            "message": "Select a .docx or .pdf file from your Google Drive"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[v0] Drive picker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/google/exchange-code")
async def google_exchange_code(code: str = Query(...), state: str = Query(...)):
    """Mobile endpoint to exchange authorization code for tokens directly.
    This is used by Flutter apps that cannot handle browser redirects."""
    try:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(status_code=400, detail="Google OAuth not configured")
        
        print(f"[v0] Mobile Google exchange code request with state: {state}")
        
        # Use the same redirect URI that was used in the auth request
        redirect_uri = "reportai://oauth-callback/google"
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        
        token_response = requests.post(token_url, data=token_data)
        if token_response.status_code != 200:
            print(f"[v0] Token exchange failed: {token_response.text}")
            raise Exception("Failed to exchange code for token")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        
        # Get user info from Google
        userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        
        if userinfo_response.status_code != 200:
            raise Exception("Failed to get user info from Google")
        
        user_info = userinfo_response.json()
        email = user_info.get("email")
        username = user_info.get("name", email.split("@")[0])
        
        print(f"[v0] Google auth successful for: {email}")
        
        # Create or get user in database
        conn = get_db()
        cursor = conn.cursor()
        
        user = cursor.execute(
            "SELECT id, username, email, role FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        
        if not user:
            # Create new user
            hashed_password = bcrypt.hashpw(
                "oauth_user".encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, university_id, role)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, hashed_password, 1, "student"))
            conn.commit()
            
            user_id = cursor.lastrowid
            role = "student"
            print(f"[v0] Created new user: {email}")
        else:
            user_id = user["id"]
            role = user["role"]
            username = user["username"]
            print(f"[v0] Found existing user: {email}")
        
        # Store Google OAuth tokens for Drive access
        refresh_token = tokens.get("refresh_token")
        token_expiry = tokens.get("expires_in")
        
        print(f"[v0] Storing Google Drive tokens for user {user_id}")
        print(f"[v0] Access token length: {len(access_token) if access_token else 0}")
        print(f"[v0] Refresh token: {'Yes' if refresh_token else 'No'}")
        
        try:
            cursor.execute(
                """INSERT OR REPLACE INTO google_drive_tokens (user_id, access_token, refresh_token, token_expiry, created_at, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (user_id, access_token, refresh_token, token_expiry)
            )
            conn.commit()
            print(f"[v0] Google Drive tokens stored for user {user_id}")
        except Exception as token_err:
            print(f"[v0] Token storage error: {token_err}")
        
        conn.close()
        
        # Create auth token
        auth_token = f"google_{user_id}_{datetime.now().timestamp()}"
        
        # Return user data and tokens
        return {
            "authenticated": True,
            "id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "token": auth_token,
            "has_google_drive": True
        }
        
    except Exception as e:
        print(f"[v0] Google exchange code error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/github/authorize")
async def github_authorize():
    """Return GitHub OAuth URL for the app to open in browser"""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=400, detail="GitHub OAuth not configured. Please set GITHUB_CLIENT_ID environment variable.")
    
    # Create a session ID to track this OAuth flow
    session_id = str(uuid.uuid4())
    oauth_sessions[session_id] = {"provider": "github", "status": "pending"}
    
    # Use localhost redirect URI
    redirect_uri = "http://localhost:8000/api/auth/github/callback"
    encoded_redirect_uri = quote(redirect_uri, safe='')
    
    github_auth_url = (
        "https://github.com/login/oauth/authorize?"
        f"client_id={settings.GITHUB_CLIENT_ID}&"
        f"redirect_uri={encoded_redirect_uri}&"
        "scope=read:user%20user:email&"
        f"state={session_id}"
    )
    print(f"[v0] GitHub OAuth URL created for session {session_id}")
    return github_auth_url

@router.get("/github/callback")
async def github_callback(code: str = Query(...), state: str = Query(...)):
    """Handle GitHub OAuth callback"""
    try:
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise HTTPException(status_code=400, detail="GitHub OAuth not configured")
        
        print(f"[v0] GitHub callback received with state: {state}")
        
        # Exchange code for token
        token_url = "https://github.com/login/oauth/access_token"
        token_data = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": "http://localhost:8000/api/auth/github/callback"
        }
        headers = {"Accept": "application/json"}
        
        token_response = requests.post(token_url, data=token_data, headers=headers)
        if token_response.status_code != 200:
            raise Exception("Failed to exchange code for token")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        
        if not access_token:
            raise Exception("No access token received from GitHub")
        
        # Get user info from GitHub
        userinfo_url = "https://api.github.com/user"
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        
        if userinfo_response.status_code != 200:
            raise Exception("Failed to get user info from GitHub")
        
        user_info = userinfo_response.json()
        
        # Get user email (might be private)
        email = user_info.get("email")
        if not email:
            # Try to get email from emails endpoint
            emails_response = requests.get("https://api.github.com/user/emails", headers=headers)
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary_email = next((e for e in emails if e.get("primary")), None)
                if primary_email:
                    email = primary_email.get("email")
        
        if not email:
            email = f"{user_info.get('login')}@github.local"
        
        username = user_info.get("name") or user_info.get("login")
        
        print(f"[v0] GitHub auth successful for: {email}")
        
        # Create or get user in database
        conn = get_db()
        cursor = conn.cursor()
        
        user = cursor.execute(
            "SELECT id, username, email, role FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        
        if not user:
            # Create new user
            hashed_password = bcrypt.hashpw(
                "oauth_user".encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, university_id, role)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, hashed_password, 1, "student"))
            conn.commit()
            
            user_id = cursor.lastrowid
            role = "student"
            print(f"[v0] Created new user: {email}")
        else:
            user_id = user["id"]
            role = user["role"]
            username = user["username"]
            print(f"[v0] Found existing user: {email}")
        
        conn.close()
        
        # Create token
        token = create_access_token({"user_id": user_id})
        
        # Store the session data for the app to retrieve
        if state in oauth_sessions:
            oauth_sessions[state] = {
                "provider": "github",
                "status": "authenticated",
                "id": user_id,
                "username": username,
                "email": email,
                "role": role,
                "token": token
            }
            print(f"[v0] Updated session {state} with user data")
        
        # Show success message in browser
        html_response = f"""
        <html>
        <head><title>Formatify - Sign In Successful</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: white;">
            <h1 style="color: #4ade80;">&#10003; Sign In Successful</h1>
            <p>Welcome, {username}!</p>
            <p>You can now return to the Formatify app.</p>
            <p style="color: #888; margin-top: 30px; font-size: 12px;">
                You can close this window.
            </p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_response)
    except Exception as e:
        print(f"[v0] GitHub callback error: {e}")
        html_response = f"""
        <html>
        <head><title>Formatify - Sign In Failed</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: white;">
            <h1 style="color: #ef4444;">&#10007; Sign In Failed</h1>
            <p>Error: {str(e)}</p>
            <p>Please try again in the app.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_response)

@router.get("/github/status")
async def github_status():
    """Check if GitHub OAuth authentication is complete"""
    # Return the latest authenticated session
    for session_id, session_data in list(oauth_sessions.items()):
        if session_data.get("provider") == "github" and session_data.get("status") == "authenticated":
            # Remove session after retrieval
            session = oauth_sessions.pop(session_id)
            return {
                "authenticated": True,
                "id": session.get("id"),
                "username": session.get("username"),
                "email": session.get("email"),
                "role": session.get("role"),
                "token": session.get("token")
            }
    
    return {"authenticated": False}
