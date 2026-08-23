"""
Storage module for data persistence.
"""

from importlib import import_module

_EXPORTS = {
    "DatabaseStorage": (".database_storage", "DatabaseStorage"),
    "FileStorage": (".file_storage", "FileStorage"),
    "CacheStorage": (".cache_storage", "CacheStorage"),
}


def __getattr__(name):
    """Load storage backends only when requested.

    The legacy SQLite backend has an optional ``aiosqlite`` dependency.  It
    must not prevent the production cache backend from importing when that
    optional adapter is not installed.
    """
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value

__all__ = [
    'DatabaseStorage',
    'FileStorage',
    'CacheStorage'
]
