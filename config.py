# Compatibility shim: expose flask_app.config as top-level 'config'
from flask_app.config import *  # noqa: F401,F403
