"""
Authentication middleware for Flask application.
Provides basic authentication using username/password.
"""
import os
from functools import wraps
from flask import request, session, redirect, render_template_string
import hmac

# Get credentials from environment variables
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'changeme')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

# Simple login page template
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Hywel Dda IPAR</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-md w-96">
        <h1 class="text-2xl font-bold mb-6 text-center text-blue-600">Hywel Dda IPAR Login</h1>
        {% if error %}
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {{ error }}
        </div>
        {% endif %}
        <form method="POST" action="/login" class="space-y-4">
            <div>
                <label for="username" class="block text-sm font-medium text-gray-700 mb-1">Username</label>
                <input type="text" id="username" name="username" required
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
            </div>
            <div>
                <label for="password" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input type="password" id="password" name="password" required
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
            </div>
            <button type="submit" 
                    class="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 transition duration-200">
                Login
            </button>
        </form>
        <p class="text-xs text-gray-500 text-center mt-4">
            Hywel Dda University Health Board - IPAR Document Miner
        </p>
    </div>
</body>
</html>
"""


def check_auth(username, password):
    """
    Check if username/password combination is valid.
    Uses constant-time comparison to prevent timing attacks.
    """
    username_valid = hmac.compare_digest(username, AUTH_USERNAME)
    password_valid = hmac.compare_digest(password, AUTH_PASSWORD)
    return username_valid and password_valid


def requires_auth(f):
    """
    Decorator to require authentication for a route.
    Checks session for authentication status.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if user is authenticated via session
        if not session.get('authenticated'):
            # Save the original URL to redirect after login
            session['next_url'] = request.url
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def init_auth(app):
    """
    Initialize authentication for the Flask app.
    Adds login/logout routes and configures session.
    """
    # Set secret key for session management
    app.secret_key = SECRET_KEY
    
    # Configure session to be secure in production
    app.config['SESSION_COOKIE_SECURE'] = app.config['ENV'] == 'production'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login route."""
        if request.method == 'POST':
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            
            if check_auth(username, password):
                session['authenticated'] = True
                session['username'] = username
                
                # Redirect to the original URL or home
                next_url = session.pop('next_url', '/')
                return redirect(next_url)
            else:
                return render_template_string(LOGIN_TEMPLATE, error='Invalid username or password')
        
        # GET request - show login form
        return render_template_string(LOGIN_TEMPLATE, error=None)
    
    @app.route('/logout', methods=['GET', 'POST'])
    def logout():
        """Logout route."""
        session.clear()
        return redirect('/login')
    
    return app
