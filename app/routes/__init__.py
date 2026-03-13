"""
Router modules for API endpoints.
"""

from . import health
from . import process
from . import templates
from . import sftp
from . import proxy
from . import web

__all__ = ["health", "process", "templates", "sftp", "proxy", "web"]
