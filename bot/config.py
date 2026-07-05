"""Backward-compatible shim — use core.config in new code."""

from core.config import Settings, settings

__all__ = ["Settings", "settings"]
