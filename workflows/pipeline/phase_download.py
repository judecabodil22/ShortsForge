"""Phase modules — thin re-exports from cogitator for a single import surface.

Canonical orchestration lives in workflows.pipeline.pipeline_runner.
Phase implementations still reside in cogitator.py; these modules make
imports stable as the monolith is split further.
"""
from workflows.cogitator import phase_download  # noqa: F401
