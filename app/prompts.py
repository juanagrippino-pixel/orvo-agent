"""Backward-compatible import alias for conversation prompts."""

from app.conversation import prompts as _prompts
import sys as _sys

_sys.modules[__name__] = _prompts
