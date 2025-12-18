"""API module.

This module provides lazy imports to avoid unnecessary dependencies.
"""

# Lazy import to avoid sqlalchemy dependency when only importing subpackages
_router = None

def __getattr__(name):
    """Lazy attribute access for router."""
    global _router
    if name == "router":
        if _router is None:
            from .main_routes import router as main_router
            _router = main_router
        return _router
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
