from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.auth import (
    MessageResponse,
    TokenRefresh,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from services.auth import (
    create_tokens,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account and return authentication tokens.

    Endpoint: POST /auth/register

    Inputs:
        Content-Type: application/json

        Body Parameters:
            email (str, required):
                - Valid email format
                - Example: "user@example.com"

            username (str, required):
                - Length: 3-50 characters
                - Allowed characters: a-z, A-Z, 0-9, underscore (_)
                - Example: "john_doe123"

            password (str, required):
                - Minimum length: 8 characters
                - Must contain at least 1 lowercase letter (a-z)
                - Must contain at least 1 uppercase letter (A-Z)
                - Must contain at least 1 number (0-9)
                - Example: "MyPassword123"

    Returns:
        201 Created:
            {
                "access_token": str,   # JWT for authenticating requests
                "refresh_token": str,  # JWT for obtaining new tokens
                "token_type": "bearer"
            }

    Raises:
        400 Bad Request: {"detail": "Email already registered"}
        400 Bad Request: {"detail": "Username already taken"}
        422 Unprocessable Entity: Validation failed (invalid email, username, or password format)

    Example (TypeScript):
        interface TokenResponse {
            access_token: string;
            refresh_token: string;
            token_type: string;
        }

        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: 'user@example.com',
                username: 'john_doe123',
                password: 'MyPassword123'
            })
        });
        const data: TokenResponse = await response.json();

        // Store tokens
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
    """
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Return tokens
    return create_tokens(new_user)


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate an existing user and return authentication tokens.

    Endpoint: POST /auth/login

    Inputs:
        Content-Type: application/x-www-form-urlencoded (NOT JSON)

        Form Parameters:
            username (str, required):
                - User's email address OR username
                - Field is named "username" per OAuth2 spec, but accepts either
                - Example: "user@example.com" or "john_doe123"

            password (str, required):
                - User's password
                - Example: "MyPassword123"

        Example (TypeScript):
            interface TokenResponse {
                access_token: string;
                refresh_token: string;
                token_type: string;
            }

            const formData = new URLSearchParams();
            formData.append('username', 'user@example.com');  // or username
            formData.append('password', 'MyPassword123');

            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData
            });
            const data: TokenResponse = await response.json();

            // Store tokens
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);

    Returns:
        200 OK:
            {
                "access_token": str,   # JWT for authenticating requests
                "refresh_token": str,  # JWT for obtaining new tokens
                "token_type": "bearer"
            }

    Raises:
        401 Unauthorized: {"detail": "Invalid email/username or password"}
    """
    # Find user by email OR username (OAuth2 form uses 'username' field for both)
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/username or password",
        )

    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/username or password",
        )

    # Return tokens (OAuth2 expects 'access_token' and 'token_type')
    tokens = create_tokens(user)
    return tokens


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout the current authenticated user.

    Endpoint: POST /auth/logout

    Inputs:
        Headers:
            Authorization (str, required):
                - Format: "Bearer <access_token>"
                - Example: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

        Body: None

    Returns:
        200 OK:
            {
                "message": "Successfully logged out"
            }

    Raises:
        401 Unauthorized: {"detail": "Not authenticated"} - Missing Authorization header
        401 Unauthorized: {"detail": "Token has expired"} - Access token expired
        401 Unauthorized: {"detail": "Could not validate credentials"} - Invalid token

    Example (TypeScript):
        interface MessageResponse {
            message: string;
        }

        const accessToken = localStorage.getItem('access_token');

        const response = await fetch('/auth/logout', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        const data: MessageResponse = await response.json();

        // Clear stored tokens
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

    Note:
        This endpoint does NOT invalidate tokens server-side (stateless JWT).
        Client MUST delete both access_token and refresh_token from storage.
    """
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """
    Obtain new authentication tokens using a valid refresh token.

    Endpoint: POST /auth/refresh

    Inputs:
        Content-Type: application/json

        Headers:
            Authorization: Not required

        Body Parameters:
            refresh_token (str, required):
                - The refresh_token obtained from /auth/login or /auth/register
                - Example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

    Returns:
        200 OK:
            {
                "access_token": str,   # New JWT for authenticating requests
                "refresh_token": str,  # New JWT for obtaining new tokens
                "token_type": "bearer"
            }

    Raises:
        401 Unauthorized: {"detail": "Invalid token type"} - Not a refresh token
        401 Unauthorized: {"detail": "Invalid token payload"} - Malformed token
        401 Unauthorized: {"detail": "User not found"} - User no longer exists
        401 Unauthorized: {"detail": "Token has expired"} - Refresh token expired

    Note:
        Call when access_token expires (401 on protected routes).
        Replace both stored tokens with new ones from response.
        If refresh_token expired, user must re-login via /auth/login.
    """
    payload = decode_token(token_data.refresh_token)

    # Ensure it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Find user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Return new tokens
    return create_tokens(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Retrieve the currently authenticated user's profile information.

    Endpoint: GET /auth/me

    Inputs:
        Headers:
            Authorization (str, required):
                - Format: "Bearer <access_token>"
                - Example: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

        Query Parameters: None

        Body: None

    Returns:
        200 OK:
            {
                "id": int,            # Unique user ID (e.g., 1)
                "email": str,         # User's email (e.g., "user@example.com")
                "username": str,      # User's username (e.g., "john_doe123")
                "created_at": str     # ISO 8601 timestamp (e.g., "2025-01-15T10:30:00")
            }

    Raises:
        401 Unauthorized: {"detail": "Not authenticated"} - Missing Authorization header
        401 Unauthorized: {"detail": "Token has expired"} - Access token expired
        401 Unauthorized: {"detail": "Could not validate credentials"} - Invalid token or user not found
    """
    return current_user

