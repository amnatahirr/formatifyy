"""Smoke check that pytest-benchmark is wired correctly."""
from __future__ import annotations

import pytest


@pytest.mark.performance
def test_benchmark_smoke(benchmark):
    """Trivial benchmark — run with: pytest -m performance --benchmark-enable"""

    def _add():
        return sum(range(1000))

    result = benchmark(_add)
    assert result == 499500
