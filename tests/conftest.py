from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"


@pytest.fixture(scope="session")
def synth_dir() -> Path:
    return SYNTHETIC


@pytest.fixture(scope="session")
def rfp_files(synth_dir) -> dict[str, Path]:
    return {p.name: p for p in sorted((synth_dir / "rfps").iterdir())}


@pytest.fixture(scope="session")
def gold(synth_dir) -> dict[str, dict]:
    from rfpx.synth.generate import load_gold

    return load_gold(synth_dir / "gold")
