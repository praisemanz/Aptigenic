import sys
import os

# Add the project root to the path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app

# Vercel serverless handler
app.config['PREFERRED_URL_SCHEME'] = 'https'
