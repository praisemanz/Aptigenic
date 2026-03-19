import sys
import os

# Resolve the project root (one level up from /api/)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

# Set template and static paths before importing app
os.environ.setdefault('APP_ROOT', ROOT_DIR)

from app import app

app.template_folder = os.path.join(ROOT_DIR, 'templates')
app.static_folder = os.path.join(ROOT_DIR, 'static')
