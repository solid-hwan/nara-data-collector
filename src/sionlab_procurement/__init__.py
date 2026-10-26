"""Independent SIONLAB procurement package."""
__version__ = '0.5.0'
from .client import Client
from .service import Procurement

__all__ = ['Client', 'Procurement', '__version__']
