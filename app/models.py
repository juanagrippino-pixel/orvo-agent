"""Backward-compatible import alias for conversation model wiring."""

from app.conversation import models as _models
import sys as _sys

_sys.modules[__name__] = _models
