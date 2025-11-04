"""
WSGI entry point for Hywel Dda IPAR Document Miner.
This file is used by Gunicorn in production.
"""
import sys
import os

# Get the directory containing this wsgi.py file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add current directory to Python path (for local and Azure deployments)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Also check if we're in Azure and add the extracted app path
# Azure extracts to /tmp/<hash>/ and we need that in the path
if 'WEBSITE_SITE_NAME' in os.environ and current_dir.startswith('/tmp/'):
    sys.path.insert(0, current_dir)
    print(f"Azure deployment detected. Added {current_dir} to Python path", flush=True)

print(f"Python path: {sys.path[:3]}", flush=True)
print(f"Current directory: {current_dir}", flush=True)
print(f"Directory contents: {os.listdir(current_dir)}", flush=True)

from app import create_app

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    app.run()
