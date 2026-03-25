"""
JWT Authentication Module
Provides secure token-based authentication with refresh tokens, 
role-based access control, and session management.
"""

import jwt
import datetime
from datetime import timezone
import os
import hashlib
import secrets
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Try to import flask components, fallback to generic if not available
try:
    from flask import request, jsonify, g
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


class UserRole(Enum):
    """User roles for access control"""
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


@dataclass
class TokenPayload:
    """Structure for JWT token payload"""
    user_id: str
    username: str
    email: str
    role: UserRole
    exp: datetime.datetime
    iat: datetime.datetime
    jti: str  # Unique token ID for revocation


class JWTManager:
    """
    JWT Token Manager for secure authentication
    Handles token creation, validation, refresh, and revocation
    """
    
    def __init__(self, secret_key: Optional[str] = None, 
                 algorithm: str = "HS256",
                 access_token_minutes: int = 15,
                 refresh_token_days: int = 7):
        """
        Initialize JWT Manager
        
        Args:
            secret_key: Secret key for signing tokens. If None, uses SECRET_KEY env var
            algorithm: JWT algorithm (default: HS256)
            access_token_minutes: Access token validity in minutes
            refresh_token_days: Refresh token validity in days
        """
        self.secret_key = secret_key or os.getenv('SECRET_KEY')
        if not self.secret_key:
            # Generate a secure random key if none provided (for development only)
            self.secret_key = secrets.token_hex(32)
            print("⚠️  WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY env var in production!")
        
        self.algorithm = algorithm
        self.access_token_minutes = access_token_minutes
        self.refresh_token_days = refresh_token_days
        
        # Token blacklist for revoked tokens (in production, use Redis/database)
        self._token_blacklist: set = set()
    
    def _generate_jti(self) -> str:
        """Generate unique token ID"""
        return secrets.token_urlsafe(32)
    
    def create_access_token(self, user_id: str, username: str, email: str, 
                           role: str = "user", additional_claims: Optional[Dict] = None) -> str:
        """
        Create a new access token
        
        Args:
            user_id: Unique user identifier
            username: Username
            email: User email
            role: User role (default: "user")
            additional_claims: Additional custom claims
            
        Returns:
            Encoded JWT access token
        """
        now = datetime.datetime.now(timezone.utc)
        payload = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'role': role,
            'iat': now,
            'exp': now + datetime.timedelta(minutes=self.access_token_minutes),
            'jti': self._generate_jti(),
            'type': 'access'
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str, username: str, 
                            additional_claims: Optional[Dict] = None) -> str:
        """
        Create a new refresh token
        
        Args:
            user_id: Unique user identifier
            username: Username
            additional_claims: Additional custom claims
            
        Returns:
            Encoded JWT refresh token
        """
        now = datetime.datetime.now(timezone.utc)
        payload = {
            'user_id': user_id,
            'username': username,
            'iat': now,
            'exp': now + datetime.timedelta(days=self.refresh_token_days),
            'jti': self._generate_jti(),
            'type': 'refresh'
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = 'access') -> Optional[TokenPayload]:
        """
        Verify and decode a JWT token
        
        Args:
            token: JWT token string
            token_type: Expected token type ('access' or 'refresh')
            
        Returns:
            TokenPayload if valid, None otherwise
        """
        try:
            # Check if token is blacklisted
            decoded = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if decoded.get('jti') in self._token_blacklist:
                return None
            
            if decoded.get('type') != token_type:
                return None
            
            return TokenPayload(
                user_id=decoded['user_id'],
                username=decoded['username'],
                email=decoded.get('email', ''),
                role=UserRole(decoded.get('role', 'user')),
                exp=datetime.datetime.fromtimestamp(decoded['exp']),
                iat=datetime.datetime.fromtimestamp(decoded['iat']),
                jti=decoded['jti']
            )
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token by adding it to the blacklist
        
        Args:
            token: JWT token to revoke
            
        Returns:
            True if successful, False otherwise
        """
        try:
            decoded = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], 
                                options={"verify_exp": False})
            jti = decoded.get('jti')
            if jti:
                self._token_blacklist.add(jti)
                return True
        except jwt.InvalidTokenError:
            pass
        return False
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """
        Use refresh token to get new access token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Tuple of (new_access_token, new_refresh_token) or None if invalid
        """
        payload = self.verify_token(refresh_token, token_type='refresh')
        if not payload:
            return None
        
        # Create new tokens
        new_access = self.create_access_token(
            user_id=payload.user_id,
            username=payload.username,
            email=payload.email,
            role=payload.role.value
        )
        
        # Optionally rotate refresh token
        new_refresh = self.create_refresh_token(
            user_id=payload.user_id,
            username=payload.username
        )
        
        # Revoke old refresh token
        self.revoke_token(refresh_token)
        
        return (new_access, new_refresh)


def require_auth(jwt_manager: JWTManager, required_roles: Optional[list] = None):
    """
    Decorator to require authentication for routes
    
    Args:
        jwt_manager: JWTManager instance
        required_roles: List of allowed roles (None = any authenticated user)
        
    Returns:
        Decorated function
    """
    if not FLASK_AVAILABLE:
        raise ImportError("Flask is required for route decorators")
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            
            if not auth_header:
                return jsonify({'error': 'Missing Authorization header'}), 401
            
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return jsonify({'error': 'Invalid Authorization header format'}), 401
            
            token = parts[1]
            payload = jwt_manager.verify_token(token, token_type='access')
            
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            # Check role requirements
            if required_roles and payload.role.value not in required_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Store user info in Flask's g object
            g.current_user = {
                'user_id': payload.user_id,
                'username': payload.username,
                'email': payload.email,
                'role': payload.role.value
            }
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Password hashing utilities
def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hash a password using PBKDF2-HMAC-SHA256
    
    Args:
        password: Plain text password
        salt: Optional salt (generated if not provided)
        
    Returns:
        Tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(32)
    
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # iterations
    )
    
    return hashed.hex(), salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        password: Plain text password to verify
        hashed_password: Stored hash
        salt: Salt used for hashing
        
    Returns:
        True if password matches, False otherwise
    """
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, hashed_password)


# Example usage and Flask integration
if __name__ == "__main__":
    # Demo usage
    manager = JWTManager()
    
    # Create tokens
    access_token = manager.create_access_token(
        user_id="123",
        username="testuser",
        email="test@example.com",
        role="user"
    )
    
    refresh_token = manager.create_refresh_token(
        user_id="123",
        username="testuser"
    )
    
    print(f"Access Token: {access_token[:50]}...")
    print(f"Refresh Token: {refresh_token[:50]}...")
    
    # Verify token
    payload = manager.verify_token(access_token)
    if payload:
        print(f"✓ Token valid for user: {payload.username} ({payload.role.value})")
    
    # Test password hashing
    pwd = "SecurePassword123!"
    hashed, salt = hash_password(pwd)
    print(f"✓ Password hashed successfully")
    
    # Verify password
    is_valid = verify_password(pwd, hashed, salt)
    print(f"✓ Password verification: {is_valid}")
    
    # Test wrong password
    is_invalid = verify_password("WrongPassword", hashed, salt)
    print(f"✓ Wrong password rejected: {not is_invalid}")
