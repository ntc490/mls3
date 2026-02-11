"""
Version utilities for MLS3
Gets version from VERSION file (semver) and git hash
"""
import subprocess
from pathlib import Path


def get_version() -> str:
    """
    Get application version.

    Format:
    - If git available: "v{semver} ({git-hash})"
    - If git not available: "v{semver}"
    - If no VERSION file: "unknown"

    Returns:
        Version string
    """
    # Get semver from VERSION file
    version_file = Path(__file__).parent.parent / 'VERSION'
    semver = None
    if version_file.exists():
        try:
            semver = version_file.read_text().strip()
        except Exception:
            pass

    if not semver:
        return "unknown"

    # Try to get git hash
    git_hash = None
    try:
        # Get short hash (7 characters)
        result = subprocess.run(
            ['git', 'rev-parse', '--short=7', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=1,
            cwd=Path(__file__).parent.parent
        )

        if result.returncode == 0:
            git_hash = result.stdout.strip()

            # Check if there are uncommitted changes
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=1,
                cwd=Path(__file__).parent.parent
            )

            if status_result.returncode == 0 and status_result.stdout.strip():
                # Uncommitted changes present
                git_hash = f"{git_hash}-dirty"

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Git not available or command failed
        pass

    # Format version string
    if git_hash:
        return f"v{semver} ({git_hash})"
    else:
        return f"v{semver}"
