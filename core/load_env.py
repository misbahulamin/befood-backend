"""Load project-root .env into the process environment.

Uses python-dotenv as a bootstrap only. Typed settings still use python-decouple
``config()``. OS / systemd variables win (override=False).
"""

from pathlib import Path

from dotenv import load_dotenv

# core/load_env.py -> project root (directory containing manage.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_project_env() -> bool:
    """
    Load ``<project-root>/.env`` if present.

    Returns True when dotenv reported that a file was loaded.
    Does not override variables already set in the OS environment.
    Missing .env is a no-op (True for EC2 with systemd-only config).
    """
    env_path = PROJECT_ROOT / '.env'
    if not env_path.is_file():
        return False
    return bool(load_dotenv(env_path, override=False))
