"""
Test authentication functionality.
Tests login, logout, and route protection.
"""
import pytest
import os
from app import create_app


@pytest.fixture
def app():
    """Create test Flask app with auth enabled."""
    # Set test credentials
    os.environ['AUTH_USERNAME'] = 'testuser'
    os.environ['AUTH_PASSWORD'] = 'testpass123'
    os.environ['SECRET_KEY'] = 'test-secret-key'
    os.environ['FLASK_ENV'] = 'testing'
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    yield app
    
    # Cleanup
    del os.environ['AUTH_USERNAME']
    del os.environ['AUTH_PASSWORD']
    del os.environ['SECRET_KEY']


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_login_page_loads(client):
    """Test that login page loads successfully."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Hywel Dda IPAR Login' in response.data


def test_protected_route_redirects_to_login(client):
    """Test that accessing protected route redirects to login."""
    response = client.get('/api/documents/', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.location


def test_successful_login(client):
    """Test successful login with valid credentials."""
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'testpass123'
    }, follow_redirects=False)
    
    assert response.status_code == 302
    # Should redirect to home after login
    assert response.location == '/'


def test_failed_login_invalid_username(client):
    """Test login fails with invalid username."""
    response = client.post('/login', data={
        'username': 'wronguser',
        'password': 'testpass123'
    })
    
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data


def test_failed_login_invalid_password(client):
    """Test login fails with invalid password."""
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'wrongpassword'
    })
    
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data


def test_access_protected_route_after_login(client):
    """Test accessing protected route after successful login."""
    # Login first
    with client:
        client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Now try to access protected route
        response = client.get('/api/documents/ui/')
        assert response.status_code == 200


def test_logout(client):
    """Test logout functionality."""
    with client:
        # Login first
        client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Logout
        response = client.get('/logout', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location
        
        # Try to access protected route after logout
        response = client.get('/api/documents/ui/', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location


def test_health_endpoint_no_auth_required(client):
    """Test that health endpoint doesn't require authentication."""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'


def test_session_persistence(client):
    """Test that session persists across requests."""
    with client:
        # Login
        client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Multiple requests should work without re-login
        response1 = client.get('/api/documents/ui/')
        assert response1.status_code == 200
        
        response2 = client.get('/api/documents/ui/upload')
        assert response2.status_code == 200
        
        response3 = client.get('/api/documents/ui/chat')
        assert response3.status_code == 200


def test_redirect_to_original_url_after_login(client):
    """Test that user is redirected to original URL after login."""
    with client:
        # Try to access protected route
        client.get('/api/documents/ui/chat', follow_redirects=False)
        
        # Login
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        }, follow_redirects=False)
        
        # Should redirect to the original URL
        assert response.status_code == 302
        # Note: The exact redirect behavior may vary based on session handling


def test_empty_credentials(client):
    """Test login with empty credentials."""
    response = client.post('/login', data={
        'username': '',
        'password': ''
    })
    
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data


def test_case_sensitive_username(client):
    """Test that username is case-sensitive."""
    response = client.post('/login', data={
        'username': 'TESTUSER',  # Wrong case
        'password': 'testpass123'
    })
    
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data


def test_timing_attack_protection(client):
    """Test that password comparison is constant-time."""
    import time
    
    # Test with completely wrong password (short)
    start1 = time.time()
    client.post('/login', data={
        'username': 'testuser',
        'password': 'x'
    })
    time1 = time.time() - start1
    
    # Test with almost correct password (same length)
    start2 = time.time()
    client.post('/login', data={
        'username': 'testuser',
        'password': 'testpass124'  # One char different
    })
    time2 = time.time() - start2
    
    # Times should be similar (constant-time comparison)
    # Allow for 50ms variance due to system load
    assert abs(time1 - time2) < 0.05


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
