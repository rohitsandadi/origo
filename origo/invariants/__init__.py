"""Invariant and validation-check support."""

from origo.invariants.checker import run_builtin_checks
from origo.invariants.models import CheckResult

__all__ = ["CheckResult", "run_builtin_checks"]
