"""
Flask application entry point for Hywel Dda IPAR Document Miner.
"""
import logging
import os
from flask import Flask, jsonify, redirect
from app.config import FLASK_ENV, PORT, configure_logging
from app.routes.documents import documents_bp

# Configure logging
logger = configure_logging()


def create_app():
    """Create and configure Flask application."""
    # Get the absolute path to the app package directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(app_dir, 'app', 'templates')
    
    app = Flask(__name__, template_folder=template_dir)
    
    # Configuration
    app.config['ENV'] = FLASK_ENV
    app.config['DEBUG'] = FLASK_ENV == 'development'
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
    
    # Register blueprints
    app.register_blueprint(documents_bp)
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'service': 'hdipar-document-miner',
            'environment': FLASK_ENV
        }), 200
    
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


if __name__ == '__main__':
    app = create_app()
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=(FLASK_ENV == 'development'))
