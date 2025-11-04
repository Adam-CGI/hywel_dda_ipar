"""
WSGI entry point for Hywel Dda IPAR Document Miner.
This file is used by Gunicorn in production.
"""
import sys
import os

# Get the directory containing this wsgi.py file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Ensure current directory is at the front of sys.path
if current_dir in sys.path:
    sys.path.remove(current_dir)
sys.path.insert(0, current_dir)

# Debugging output for Azure
print(f"WSGI current directory: {current_dir}", flush=True)
print(f"Directory exists: {os.path.exists(current_dir)}", flush=True)
print(f"Directory contents: {os.listdir(current_dir)[:10] if os.path.exists(current_dir) else 'N/A'}", flush=True)

# Check if app package exists
app_path = os.path.join(current_dir, 'app')
print(f"App path: {app_path}", flush=True)
print(f"App exists: {os.path.exists(app_path)}", flush=True)
print(f"App is directory: {os.path.isdir(app_path)}", flush=True)
if os.path.exists(app_path):
    print(f"App contents: {os.listdir(app_path)[:10]}", flush=True)
    app_init = os.path.join(app_path, '__init__.py')
    print(f"App __init__.py exists: {os.path.exists(app_init)}", flush=True)

print(f"sys.path[0]: {sys.path[0]}", flush=True)

from app import create_app

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    app.run()
