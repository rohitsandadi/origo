"""Local deterministic importers for Origo traces and failure specs."""

from origo.importers.local_json import load_failure_yaml, load_trace_json

__all__ = ["load_failure_yaml", "load_trace_json"]
