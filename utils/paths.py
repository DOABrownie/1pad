from pathlib import Path


def project_root() -> Path:
    """
    Returns the root directory for the project.
    Assumes this file is under <root>/utils/paths.py.
    """
    return Path(__file__).resolve().parents[1]


def logs_dir() -> Path:
    path = project_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_dir() -> Path:
    path = project_root() / "reports" / "backtest_reports"
    path.mkdir(parents=True, exist_ok=True)
    return path
