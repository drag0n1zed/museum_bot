"""
Museum Bot Package

A Python package for the Museum Guide Robot application.
"""

__version__ = "1.0.0"

# Import the main entry point function
from .app import start_museum_bot

# Make the main entry point available at package level
__all__ = ["start_museum_bot", "__version__"]
