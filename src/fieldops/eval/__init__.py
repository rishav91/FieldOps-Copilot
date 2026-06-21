"""Offline evaluation harnesses (EVAL-SPEC). Phase 1: dedup."""
from .metrics import cohen_kappa, precision_recall_f1

__all__ = ["precision_recall_f1", "cohen_kappa"]
