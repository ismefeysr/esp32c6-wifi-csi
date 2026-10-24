from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def analysis_dir():
    return ROOT / "analysis"


@pytest.fixture(scope="session")
def c6_capture():
    """40 consecutive packets captured from the real csi_recv firmware (host_time;raw_line)."""
    return Path(__file__).parent / "fixtures" / "c6_capture.csv"
