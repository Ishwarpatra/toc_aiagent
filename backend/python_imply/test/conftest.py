import sys
import os

# Ensure python_imply package is on sys.path
# Only add PYTHON_IMPLY - do NOT add BACKEND_ROOT to avoid package collision
HERE = os.path.dirname(__file__)
PYTHON_IMPLY = os.path.abspath(os.path.join(HERE, ".."))

if PYTHON_IMPLY not in sys.path:
    sys.path.insert(0, PYTHON_IMPLY)
