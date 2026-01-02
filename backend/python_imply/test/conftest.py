import sys
import os

# Ensure repository backend root and python_imply package are on sys.path
HERE = os.path.dirname(__file__)
PYTHON_IMPLY = os.path.abspath(os.path.join(HERE, ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

if PYTHON_IMPLY not in sys.path:
    sys.path.insert(0, PYTHON_IMPLY)
