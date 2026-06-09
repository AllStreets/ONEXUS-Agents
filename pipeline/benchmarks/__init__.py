"""Benchmark scrapers package.

Importing this package auto-registers every concrete scraper subclass
via the BenchmarkScraper.__init_subclass__ hook. Add new scrapers by
creating pipeline/benchmarks/<name>.py and importing it here.
"""

from pipeline.benchmarks import swe_bench  # noqa: F401

__all__ = ["swe_bench"]
