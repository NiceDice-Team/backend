"""Test-infrastructure reporting for NiceDice backend QA."""

from .core import COMMENT_MARKER, aggregate_reports, render_pr_summary, validate_report

__all__ = ["COMMENT_MARKER", "aggregate_reports", "render_pr_summary", "validate_report"]
