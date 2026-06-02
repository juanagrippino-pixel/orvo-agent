"""Backward-compatible import alias for the conversation graph."""

from app.conversation import graph as _graph
import sys as _sys

_sys.modules[__name__] = _graph
