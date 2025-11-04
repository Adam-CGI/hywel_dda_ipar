"""
Flask application entry point for Hywel Dda IPAR Document Miner.
This file is for local development. Production deployments use wsgi.py.
"""
from app import create_app
from app.config import FLASK_ENV, PORT, configure_logging

# Configure logging
logger = configure_logging()

if __name__ == '__main__':
    app = create_app()
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=(FLASK_ENV == 'development'))
