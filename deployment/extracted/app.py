import sys
import os

# Add root to path so we can import the real app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import app as application
app = application
