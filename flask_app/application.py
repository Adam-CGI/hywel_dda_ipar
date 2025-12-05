"""
Main WSGI application entry point for Azure App Service.
This file must be named 'application.py' or 'app.py' for Azure auto-detection.
Adds path shims for local test execution when run outside package context.
"""
import logging
import os
import sys
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from functools import wraps

# Ensure current directory is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Import config from current directory
from config import FLASK_ENV, PORT, configure_logging, BRAND_NAME, BRAND_TAGLINE

# Import blueprints from subdirectories
from routes.documents import documents_bp

# Configure logging
logger = configure_logging()


def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        if not session.get('is_admin'):
            return render_template('error.html', 
                error="Access Denied", 
                message="You do not have permission to access this page."), 403
        return f(*args, **kwargs)
    return decorated_function


def create_app():
    """Create and configure Flask application."""
    # Templates and static files are in the same directory structure
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    # Configuration
    app.config['ENV'] = FLASK_ENV
    app.config['DEBUG'] = FLASK_ENV == 'development'
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SESSION_COOKIE_SECURE'] = FLASK_ENV == 'production'  # HTTPS only in production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Production settings
    if FLASK_ENV == 'production':
        app.config['PROPAGATE_EXCEPTIONS'] = True
        app.logger.disabled = False
        app.logger.setLevel(logging.INFO)
    
    # Register blueprints
    app.register_blueprint(documents_bp)

    # Register pages blueprint (About & future static informational pages)
    try:
        from routes.pages import pages_bp
        app.register_blueprint(pages_bp)
    except Exception as e:
        logger.warning(f"Pages blueprint not registered: {e}")
    
    # Register admin blueprint
    try:
        from routes.admin import admin_bp
        app.register_blueprint(admin_bp)
    except Exception as e:
        logger.warning(f"Admin blueprint not registered: {e}")
    
    # Initialize Cosmos service for auth
    cosmos_service = None
    try:
        from services.cosmos_service import CosmosService
        cosmos_service = CosmosService()
        logger.info("CosmosService initialized for authentication")
    except Exception as e:
        logger.error(f"Failed to initialize CosmosService: {e}")
    
    # Apply authentication to all routes except public endpoints
    @app.before_request
    def require_authentication():
        """Require authentication for all routes except public endpoints."""
        # Public endpoints (no auth required)
        public_endpoints = ['/health', '/ready', '/login', '/static']
        
        # Skip auth for public endpoints
        if any(request.path.startswith(endpoint) for endpoint in public_endpoints):
            return None
        
        # Require login for all other endpoints
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
    
    # Login route
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Handle user login via Cosmos DB."""
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if not cosmos_service:
                logger.error("CosmosService not available for authentication")
                return render_template('login.html', error='Authentication service unavailable')
            
            # Verify user against Cosmos DB
            user = cosmos_service.verify_user(username, password)
            
            if user:
                session['logged_in'] = True
                session['username'] = user['username']
                session['user_id'] = user['id']
                session['is_admin'] = user.get('is_admin', False)
                
                logger.info(f"User '{username}' logged in (admin={user.get('is_admin', False)})")
                
                # Redirect to the page they were trying to access, or home
                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                return redirect('/')
            else:
                return render_template('login.html', error='Invalid username or password')
        
        # If already logged in, redirect to home
        if session.get('logged_in'):
            return redirect('/')
        
        return render_template('login.html')
    
    # Logout route
    @app.route('/logout', methods=['GET', 'POST'])
    def logout():
        """Handle user logout."""
        session.clear()
        return redirect(url_for('login'))

    # Inject branding into all templates
    @app.context_processor
    def inject_brand():
        return {
            'brand_name': BRAND_NAME,
            'brand_tagline': BRAND_TAGLINE
        }
    
    # Health check endpoint (required for Azure App Service health probes)
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for Azure App Service."""
        return jsonify({
            'status': 'healthy',
            'service': 'hdipar-document-miner',
            'environment': FLASK_ENV,
            'version': '1.0.0'
        }), 200
    
    # Readiness probe endpoint
    @app.route('/ready', methods=['GET'])
    def readiness_check():
        """Readiness check - verifies critical dependencies."""
        checks = {
            'storage': bool(os.getenv('AZURE_STORAGE_CONNSTR')),
            'search': bool(os.getenv('AZURE_SEARCH_ENDPOINT')),
            'openai': bool(os.getenv('AZURE_OPENAI_ENDPOINT')),
            'cosmos': bool(os.getenv('COSMOS_ENDPOINT')),
        }
        all_ready = all(checks.values())
        status_code = 200 if all_ready else 503
        return jsonify({
            'ready': all_ready,
            'checks': checks
        }), status_code
    
    # Root endpoint - redirect to chat UI (new default)
    @app.route('/', methods=['GET'])
    def root():
        """Root endpoint - redirect to chat interface."""
        return redirect('/api/documents/ui/chat')
    
    # Document UI routes (redirect to blueprint UI routes)
    @app.route('/documents', methods=['GET'])
    def documents_ui():
        """Redirect to document list UI."""
        return redirect('/api/documents/ui/')
    
    @app.route('/documents/<doc_id>', methods=['GET'])
    def document_detail_ui(doc_id):
        """Redirect to document detail UI."""
        return redirect(f'/api/documents/ui/{doc_id}')
    
    @app.route('/documents/upload', methods=['GET'])
    def upload_ui():
        """Redirect to upload UI."""
        return redirect('/api/documents/ui/upload')
    
    # Chat UI route (backward compatibility)
    @app.route('/chat', methods=['GET'])
    def chat_ui():
        """Redirect to chat UI for backward compatibility."""
        return redirect('/api/documents/ui/chat')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500
    
    logger.info(f"Flask app created in {FLASK_ENV} mode")
    return app


# Create the Flask application instance
# Azure App Service looks for 'app' or 'application' variable
app = create_app()
application = app  # Alias for compatibility

if __name__ == '__main__':
    # This runs only for local development
    # Azure App Service will use gunicorn via startup.txt
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=(FLASK_ENV == 'development')
    )
