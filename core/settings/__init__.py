import os

from core.load_env import load_project_env

# Project-root .env before DJANGO_ENV / settings selection (OS env wins).
load_project_env()

env = os.getenv('DJANGO_ENV', 'prod').lower()
if env == 'prod':
    from .prod import *  # noqa
else:
    from .local import *  # noqa
