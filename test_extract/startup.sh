#!/bin/bash
# Azure App Service startup script

echo "Starting Hywel Dda IPAR Document Miner"
exec gunicorn --bind=0.0.0.0:8000 --workers=2 --timeout=120 wsgi:app