"""Verify the bundled experiment using only local files and Python's standard library."""
from pathlib import Path

from export_beam import verify


if __name__ == "__main__":
    verify(Path(__file__).resolve().parents[1] / "beam-free-20261017")
