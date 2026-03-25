"""
Flask Authentication Routes
Login, logout, register, token refresh, and user management endpoints
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
import os
import re
from .jwt_auth import JWTManager, hash_password, verify_password, UserRole

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Initialize JWT Manager
jwt_manager = JWTManager(
    secret_key=os.getenv('SECRET_KEY'),
    access_token_minutes=int(os.getenv('ACCESS_TOKEN_MINUTES', 15)),
    refresh_token_days=int(os.getenv('REFRESH_TOKEN_DAYS', 7))
)

# In-memory user store (replace with database in production)
# Structure: {email: {id, username, email, password_hash, salt, role, created_at}}
users_db = {}


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> tuple:
    """
    Validate password strength
    Returns: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user
    
    Expected JSON:
    {
        "username": "string",
        "email": "string",
        "password": "string"
    }
    
    Returns:
    {
        "message": "User registered successfully",
        "user": {
            "id": "string",
            "username": "string",
            "email": "string",
            "role": "user"
        }
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    # Validation
    if not username or len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    # Check if user exists
    if email in users_db:
        return jsonify({'error': 'User with this email already exists'}), 409
    
    # Create user
    user_id = f"user_{len(users_db) + 1:04d}"
    password_hash, salt = hash_password(password)
    
    users_db[email] = {
        'id': user_id,
        'username': username,
        'email': email,
        'password_hash': password_hash,
        'salt': salt,
        'role': 'user',
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    return jsonify({
        'message': 'User registered successfully',
        'user': {
            'id': user_id,
            'username': username,
            'email': email,
            'role': 'user'
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login user
    
    Expected JSON:
    {
        "email": "string",
        "password": "string"
    }
    
    Returns:
    {
        "access_token": "string",
        "refresh_token": "string",
        "user": {
            "id": "string",
            "username": "string",
            "email": "string",
            "role": "string"
        }
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    # Find user
    user = users_db.get(email)
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Verify password
    if not verify_password(password, user['password_hash'], user['salt']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate tokens
    access_token = jwt_manager.create_access_token(
        user_id=user['id'],
        username=user['username'],
        email=user['email'],
        role=user['role']
    )
    
    refresh_token = jwt_manager.create_refresh_token(
        user_id=user['id'],
        username=user['username']
    )
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role']
        }
    })


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh access token using refresh token
    
    Expected JSON:
    {
        "refresh_token": "string"
    }
    
    Returns:
    {
        "access_token": "string",
        "refresh_token": "string"
    }
    """
    data = request.get_json()
    
    if not data or 'refresh_token' not in data:
        return jsonify({'error': 'Refresh token required'}), 400
    
    refresh_token = data['refresh_token']
    result = jwt_manager.refresh_access_token(refresh_token)
    
    if not result:
        return jsonify({'error': 'Invalid or expired refresh token'}), 401
    
    new_access, new_refresh = result
    
    return jsonify({
        'access_token': new_access,
        'refresh_token': new_refresh
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout user (revoke tokens)
    
    Expected JSON (optional):
    {
        "access_token": "string",
        "refresh_token": "string"
    }
    
    If tokens not provided, uses Authorization header for access token
    """
    data = request.get_json() or {}
    
    # Revoke access token
    access_token = data.get('access_token')
    if not access_token:
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                access_token = parts[1]
    
    if access_token:
        jwt_manager.revoke_token(access_token)
    
    # Revoke refresh token if provided
    refresh_token = data.get('refresh_token')
    if refresh_token:
        jwt_manager.revoke_token(refresh_token)
    
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """
    Get current authenticated user info
    
    Requires: Authorization: Bearer <token>
    
    Returns:
    {
        "user": {
            "id": "string",
            "username": "string",
            "email": "string",
            "role": "string"
        }
    }
    """
    from .jwt_auth import require_auth
    
    # Manual auth check since decorator would redirect
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
    
    return jsonify({
        'user': {
            'id': payload.user_id,
            'username': payload.username,
            'email': payload.email,
            'role': payload.role.value
        }
    })


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """
    Change user password
    
    Requires: Authorization: Bearer <token>
    
    Expected JSON:
    {
        "current_password": "string",
        "new_password": "string"
    }
    """
    from .jwt_auth import require_auth
    
    # Auth check
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
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password required'}), 400
    
    # Find user
    user = users_db.get(payload.email)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Verify current password
    if not verify_password(current_password, user['password_hash'], user['salt']):
        return jsonify({'error': 'Invalid current password'}), 401
    
    # Validate new password
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    # Update password
    new_hash, new_salt = hash_password(new_password)
    user['password_hash'] = new_hash
    user['salt'] = new_salt
    
    # Revoke all tokens for security
    # In production, you'd want to blacklist all user's tokens
    
    return jsonify({'message': 'Password changed successfully'})


# Admin-only route example
@auth_bp.route('/users', methods=['GET'])
def list_users():
    """
    List all users (admin only)
    
    Requires: Authorization: Bearer <token> with admin role
    """
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
    
    # Check admin role
    if payload.role.value not in ['admin', 'superadmin']:
        return jsonify({'error': 'Admin access required'}), 403
    
    # Return user list (without sensitive data)
    user_list = []
    for email, user in users_db.items():
        user_list.append({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
            'created_at': user['created_at']
        })
    
    return jsonify({'users': user_list})


if __name__ == "__main__":
    # Test the module
    print("JWT Auth Module loaded successfully")
    print(f"Users registered: {len(users_db)}")
