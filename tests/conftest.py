import sys
import os
import pytest

# Add the src directory to the Python path so that tests can import the application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))) 