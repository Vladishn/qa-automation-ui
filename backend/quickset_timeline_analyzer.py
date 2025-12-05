"""Compatibility shim for legacy imports.

The analyzer implementation now lives in ``app.quickset_timeline_analyzer``.
Re-export everything so external callers that import
``backend.quickset_timeline_analyzer`` keep working.
"""

from app.quickset_timeline_analyzer import *  # type: ignore  # noqa: F401,F403
