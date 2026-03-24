"""
Security Tests for JWT Authentication and HTTPS
Tests token generation, validation, refresh, revocation, password hashing, and role-based access
"""

import unittest
import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auth.jwt_auth import (
    JWTManager, 
    UserRole, 
    hash_password, 
    verify_password,
    TokenPayload
)


class TestJWTAuth(unittest.TestCase):
    """Test suite for JWT authentication module"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.jwt_manager = JWTManager(
            secret_key="test_secret_key_for_unit_testing_only",
            access_token_minutes=5,
            refresh_token_days=1
        )
        self.test_user = {
            'user_id': 'test_123',
            'username': 'testuser',
            'email': 'test@example.com',
            'role': 'user'
        }
    
    def test_create_access_token(self):
        """Test access token creation"""
        token = self.jwt_manager.create_access_token(**self.test_user)
        
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 50)  # JWT should be reasonably long
    
    def test_create_refresh_token(self):
        """Test refresh token creation"""
        token = self.jwt_manager.create_refresh_token(
            user_id=self.test_user['user_id'],
            username=self.test_user['username']
        )
        
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
    
    def test_verify_valid_access_token(self):
        """Test verification of valid access token"""
        token = self.jwt_manager.create_access_token(**self.test_user)
        payload = self.jwt_manager.verify_token(token, token_type='access')
        
        self.assertIsNotNone(payload)
        self.assertEqual(payload.user_id, self.test_user['user_id'])
        self.assertEqual(payload.username, self.test_user['username'])
        self.assertEqual(payload.email, self.test_user['email'])
        self.assertEqual(payload.role, UserRole.USER)
    
    def test_verify_valid_refresh_token(self):
        """Test verification of valid refresh token"""
        token = self.jwt_manager.create_refresh_token(
            user_id=self.test_user['user_id'],
            username=self.test_user['username']
        )
        payload = self.jwt_manager.verify_token(token, token_type='refresh')
        
        self.assertIsNotNone(payload)
        self.assertEqual(payload.user_id, self.test_user['user_id'])
        self.assertEqual(payload.username, self.test_user['username'])
    
    def test_verify_wrong_token_type(self):
        """Test that access token cannot be used as refresh token"""
        access_token = self.jwt_manager.create_access_token(**self.test_user)
        payload = self.jwt_manager.verify_token(access_token, token_type='refresh')
        
        self.assertIsNone(payload)
    
    def test_expired_token(self):
        """Test expired token detection"""
        # Create manager with very short token lifetime
        short_manager = JWTManager(
            secret_key="test_secret",
            access_token_minutes=-1  # Already expired
        )
        
        token = short_manager.create_access_token(**self.test_user)
        payload = short_manager.verify_token(token, token_type='access')
        
        self.assertIsNone(payload)
    
    def test_token_revocation(self):
        """Test token revocation"""
        token = self.jwt_manager.create_access_token(**self.test_user)
        
        # Verify token is valid initially
        payload = self.jwt_manager.verify_token(token, token_type='access')
        self.assertIsNotNone(payload)
        
        # Revoke token
        result = self.jwt_manager.revoke_token(token)
        self.assertTrue(result)
        
        # Verify token is now invalid
        payload = self.jwt_manager.verify_token(token, token_type='access')
        self.assertIsNone(payload)
    
    def test_token_refresh(self):
        """Test token refresh flow"""
        refresh_token = self.jwt_manager.create_refresh_token(
            user_id=self.test_user['user_id'],
            username=self.test_user['username']
        )
        
        # Refresh tokens
        result = self.jwt_manager.refresh_access_token(refresh_token)
        
        self.assertIsNotNone(result)
        new_access, new_refresh = result
        
        self.assertIsInstance(new_access, str)
        self.assertIsInstance(new_refresh, str)
        self.assertNotEqual(new_access, new_refresh)
        
        # Verify old refresh token is revoked
        payload = self.jwt_manager.verify_token(refresh_token, token_type='refresh')
        self.assertIsNone(payload)
    
    def test_invalid_token(self):
        """Test invalid token handling"""
        invalid_tokens = [
            '',
            'not_a_jwt',
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid',
            'Bearer fake_token',
            None
        ]
        
        for token in invalid_tokens:
            if token is None:
                continue
            payload = self.jwt_manager.verify_token(token, token_type='access')
            self.assertIsNone(payload, f"Token '{token}' should be invalid")
    
    def test_token_contains_correct_claims(self):
        """Test that token contains all required claims"""
        token = self.jwt_manager.create_access_token(**self.test_user)
        payload = self.jwt_manager.verify_token(token, token_type='access')
        
        self.assertIsNotNone(payload)
        self.assertEqual(payload.user_id, self.test_user['user_id'])
        self.assertEqual(payload.username, self.test_user['username'])
        self.assertEqual(payload.email, self.test_user['email'])
        self.assertEqual(payload.role, UserRole.USER)
        self.assertIsNotNone(payload.exp)
        self.assertIsNotNone(payload.iat)
        self.assertIsNotNone(payload.jti)
    
    def test_different_users_have_different_tokens(self):
        """Test that different users get different tokens"""
        user1 = self.jwt_manager.create_access_token(
            user_id='user1',
            username='user1',
            email='user1@example.com',
            role='user'
        )
        
        user2 = self.jwt_manager.create_access_token(
            user_id='user2',
            username='user2',
            email='user2@example.com',
            role='admin'
        )
        
        self.assertNotEqual(user1, user2)
        
        # Verify payloads are different
        payload1 = self.jwt_manager.verify_token(user1, token_type='access')
        payload2 = self.jwt_manager.verify_token(user2, token_type='access')
        
        self.assertNotEqual(payload1.user_id, payload2.user_id)
        self.assertNotEqual(payload1.role, payload2.role)


class TestPasswordHashing(unittest.TestCase):
    """Test suite for password hashing functions"""
    
    def test_hash_password_returns_hash_and_salt(self):
        """Test that hash_password returns both hash and salt"""
        password = "SecurePassword123!"
        hashed, salt = hash_password(password)
        
        self.assertIsNotNone(hashed)
        self.assertIsNotNone(salt)
        self.assertIsInstance(hashed, str)
        self.assertIsInstance(salt, str)
        self.assertGreater(len(hashed), 60)  # SHA256 hex is 64 chars
        self.assertGreater(len(salt), 30)  # Our salt is 64 hex chars
    
    def test_same_password_different_salts(self):
        """Test that same password gets different hashes with different salts"""
        password = "SamePassword123!"
        
        hashed1, salt1 = hash_password(password)
        hashed2, salt2 = hash_password(password)
        
        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(hashed1, hashed2)
    
    def test_verify_correct_password(self):
        """Test verifying correct password"""
        password = "CorrectPassword123!"
        hashed, salt = hash_password(password)
        
        is_valid = verify_password(password, hashed, salt)
        self.assertTrue(is_valid)
    
    def test_verify_incorrect_password(self):
        """Test verifying incorrect password"""
        password = "CorrectPassword123!"
        wrong_password = "WrongPassword456!"
        hashed, salt = hash_password(password)
        
        is_valid = verify_password(wrong_password, hashed, salt)
        self.assertFalse(is_valid)
    
    def test_verify_with_tampered_hash(self):
        """Test verifying with tampered hash"""
        password = "Password123!"
        hashed, salt = hash_password(password)
        
        # Tamper with hash
        tampered_hash = 'a' + hashed[1:]
        
        is_valid = verify_password(password, tampered_hash, salt)
        self.assertFalse(is_valid)
    
    def test_password_case_sensitivity(self):
        """Test that password verification is case-sensitive"""
        password = "Password123!"
        hashed, salt = hash_password(password)
        
        # Different case
        is_valid_lower = verify_password("password123!", hashed, salt)
        is_valid_upper = verify_password("PASSWORD123!", hashed, salt)
        
        self.assertFalse(is_valid_lower)
        self.assertFalse(is_valid_upper)
    
    def test_special_characters_in_password(self):
        """Test passwords with special characters"""
        passwords = [
            "P@ssw0rd!",
            "Test#$%^&*()",
            "Unicode™Password123",
            "Spaces In Password 123!",
            "Quotes\"And'Apostrophes123!"
        ]
        
        for password in passwords:
            hashed, salt = hash_password(password)
            is_valid = verify_password(password, hashed, salt)
            self.assertTrue(is_valid, f"Failed for password: {password}")
    
    def test_long_password(self):
        """Test very long password"""
        password = "A" * 1000 + "123!"
        hashed, salt = hash_password(password)
        is_valid = verify_password(password, hashed, salt)
        
        self.assertTrue(is_valid)


class TestUserRole(unittest.TestCase):
    """Test user role enumeration"""
    
    def test_user_roles_exist(self):
        """Test that all expected roles exist"""
        self.assertEqual(UserRole.GUEST.value, 'guest')
        self.assertEqual(UserRole.USER.value, 'user')
        self.assertEqual(UserRole.ADMIN.value, 'admin')
        self.assertEqual(UserRole.SUPERADMIN.value, 'superadmin')
    
    def test_role_hierarchy(self):
        """Test role values"""
        roles = [role.value for role in UserRole]
        self.assertIn('guest', roles)
        self.assertIn('user', roles)
        self.assertIn('admin', roles)
        self.assertIn('superadmin', roles)


class TestSecurityBestPractices(unittest.TestCase):
    """Test security best practices implementation"""
    
    def test_timing_attack_resistance(self):
        """Test that password verification uses constant-time comparison"""
        password = "SecurePassword123!"
        hashed, salt = hash_password(password)
        
        # Measure time for correct password
        import time
        start = time.time()
        for _ in range(100):
            verify_password(password, hashed, salt)
        correct_time = time.time() - start
        
        # Measure time for wrong password
        start = time.time()
        for _ in range(100):
            verify_password("WrongPassword456!", hashed, salt)
        wrong_time = time.time() - start
        
        # Times should be similar (within 50% tolerance)
        # This is a basic check; proper timing attack tests need more sophisticated approach
        ratio = max(correct_time, wrong_time) / min(correct_time, wrong_time)
        self.assertLess(ratio, 2.0, "Possible timing vulnerability detected")
    
    def test_secret_key_generation(self):
        """Test auto-generated secret key is sufficiently random"""
        manager1 = JWTManager(secret_key=None)
        manager2 = JWTManager(secret_key=None)
        
        # Keys should be different
        self.assertNotEqual(manager1.secret_key, manager2.secret_key)
        
        # Keys should be long enough
        self.assertGreaterEqual(len(manager1.secret_key), 32)
        self.assertGreaterEqual(len(manager2.secret_key), 32)


def run_tests():
    """Run all security tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestJWTAuth))
    suite.addTests(loader.loadTestsFromTestCase(TestPasswordHashing))
    suite.addTests(loader.loadTestsFromTestCase(TestUserRole))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityBestPractices))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
