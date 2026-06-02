"""Backward-compatible import alias for conversation persistence."""

from app.conversation import db as _db
import sys as _sys

_sys.modules[__name__] = _db
