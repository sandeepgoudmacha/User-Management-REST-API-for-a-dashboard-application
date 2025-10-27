"""Authentication API endpoints."""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
import uuid

from app.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    get_current_user,
    get_current_active_user,
    generate_api_key,
    create_user_session,
    verify_token,
)
from app.auth.models import (
    User,
    UserCreate,
    UserLogin,
    Token,
    UserProfile,
)
from app.cache import get_redis_client
from app.config import get_settings

router = APIRouter()
settings = get_settings()

# In-memory user store (replace with database in production)
users_db = {}


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Register a new user.

    Requirements:
    - Valid email address
    - Password minimum 8 characters
    - Passwords must match
    """
    # Validate passwords match
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )

    # Check if user exists
    if user_data.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create user
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(user_data.password)

    user = {
        "id": user_id,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "hashed_password": hashed_password,
        "is_active": True,
        "is_verified": False,
        "created_at": datetime.utcnow(),
        "last_login": None,
        "role": "user",
        "api_key": None,
    }

    # Store user
    users_db[user_data.email] = user

    # Store in Redis if available
    redis_client = await get_redis_client()
    if redis_client:
        await redis_client.setex(
            f"user:{user_id}",
            86400 * 30,  # 30 days
            str(user)
        )

    return User(**user)


@router.post("/login", response_model=Token)
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login with email and password.

    Returns access and refresh tokens.
    """
    # Find user
    user = users_db.get(form_data.username)  # OAuth2 uses 'username' field

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user["last_login"] = datetime.utcnow()

    # Create tokens
    access_token = create_access_token(
        data={"sub": user["id"], "email": user["email"], "scopes": []}
    )
    refresh_token = create_refresh_token(
        data={"sub": user["id"], "email": user["email"]}
    )

    # Create session
    session_id = await create_user_session(user["id"])

    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400  # 24 hours
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    """
    Logout current user.

    Invalidates session and clears cookies.
    """
    # Clear session in Redis
    redis_client = await get_redis_client()
    if redis_client:
        # Remove user sessions
        await redis_client.delete(f"session:*{current_user.id}*")

    # Clear cookies
    response.delete_cookie(key="session_id")

    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token.
    """
    try:
        # Verify refresh token
        token_data = verify_token(refresh_token, token_type="refresh")

        # Create new access token
        access_token = create_access_token(
            data={"sub": token_data.user_id, "email": token_data.email, "scopes": token_data.scopes}
        )

        return Token(
            access_token=access_token,
            token_type="bearer"
        )

    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_active_user)):
    """
    Get current user profile.
    """
    # Get additional profile data
    redis_client = await get_redis_client()
    usage_stats = {}
    preferences = {}

    if redis_client:
        # Get usage statistics
        stats_data = await redis_client.hgetall(f"user_stats:{current_user.id}")
        if stats_data:
            usage_stats = {
                "searches": int(stats_data.get(b"searches", 0)),
                "suggestions": int(stats_data.get(b"suggestions", 0)),
                "analyses": int(stats_data.get(b"analyses", 0)),
            }

        # Get preferences
        prefs_data = await redis_client.get(f"user_prefs:{current_user.id}")
        if prefs_data:
            # Parse preferences
            pass

    # Get user's API key if exists
    user_data = users_db.get(current_user.email, {})
    api_key = user_data.get("api_key")

    return UserProfile(
        **current_user.dict(),
        api_key=api_key,
        usage_stats=usage_stats,
        preferences=preferences,
        subscription=None  # Add subscription logic
    )


@router.put("/me", response_model=User)
async def update_profile(
    full_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update user profile.
    """
    # Update user data
    if current_user.email in users_db:
        if full_name:
            users_db[current_user.email]["full_name"] = full_name
            current_user.full_name = full_name

    return current_user


@router.post("/api-key", response_model=dict)
async def generate_user_api_key(current_user: User = Depends(get_current_active_user)):
    """
    Generate API key for current user.

    API keys allow programmatic access without login.
    """
    # Generate new API key
    api_key = generate_api_key()

    # Store API key
    if current_user.email in users_db:
        users_db[current_user.email]["api_key"] = api_key

    # Store in Redis for fast lookup
    redis_client = await get_redis_client()
    if redis_client:
        await redis_client.setex(
            f"api_key:{api_key}",
            86400 * 90,  # 90 days
            current_user.id
        )

    return {
        "api_key": api_key,
        "message": "API key generated successfully. Keep it secure!"
    }


@router.delete("/api-key")
async def revoke_api_key(current_user: User = Depends(get_current_active_user)):
    """
    Revoke current user's API key.
    """
    # Remove API key
    if current_user.email in users_db:
        old_key = users_db[current_user.email].get("api_key")
        users_db[current_user.email]["api_key"] = None

        # Remove from Redis
        if old_key:
            redis_client = await get_redis_client()
            if redis_client:
                await redis_client.delete(f"api_key:{old_key}")

    return {"message": "API key revoked successfully"}


@router.post("/verify-email")
async def verify_email(token: str):
    """
    Verify email address with token.
    """
    # In production, implement email verification logic
    return {"message": "Email verified successfully"}


@router.post("/reset-password")
async def request_password_reset(email: str):
    """
    Request password reset email.
    """
    # Check if user exists
    if email not in users_db:
        # Don't reveal if email exists
        return {"message": "If the email exists, a reset link has been sent"}

    # In production, send reset email
    return {"message": "If the email exists, a reset link has been sent"}


@router.put("/reset-password")
async def reset_password(token: str, new_password: str):
    """
    Reset password with token.
    """
    # In production, validate reset token and update password
    return {"message": "Password reset successfully"}