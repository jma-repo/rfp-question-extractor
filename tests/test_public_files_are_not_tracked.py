import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs a git checkout")
def test_downloaded_public_files_are_never_tracked_or_staged():
    """Real RFPs belong to their issuers: they live in data/public/, which is git-ignored, and never in a commit."""
    tracked = subprocess.run(["git", "ls-files", "--", "data/public"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert tracked.strip() == ""
    probe = subprocess.run(["git", "check-ignore", "-q", "data/public/anything.pdf"], cwd=ROOT)
    assert probe.returncode == 0, "data/public/ must stay in .gitignore"
