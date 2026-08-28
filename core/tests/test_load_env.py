import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from core.load_env import PROJECT_ROOT, load_project_env


class LoadProjectEnvTests(SimpleTestCase):
    def test_project_root_contains_manage_py(self):
        self.assertTrue((PROJECT_ROOT / 'manage.py').is_file())

    def test_missing_env_file_is_noop(self):
        with patch('core.load_env.PROJECT_ROOT', Path(tempfile.mkdtemp())):
            self.assertFalse(load_project_env())

    def test_loads_value_when_os_env_unset(self):
        key = 'BEFOOD_TEST_ENV_BOOTSTRAP'
        os.environ.pop(key, None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env').write_text(f'{key}=from-dotenv\n', encoding='utf-8')
            with patch('core.load_env.PROJECT_ROOT', root):
                self.assertTrue(load_project_env())
            self.assertEqual(os.environ.get(key), 'from-dotenv')
            os.environ.pop(key, None)

    def test_os_environment_wins_over_dotenv(self):
        key = 'BEFOOD_TEST_ENV_OVERRIDE'
        os.environ[key] = 'from-os'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env').write_text(f'{key}=from-dotenv\n', encoding='utf-8')
            with patch('core.load_env.PROJECT_ROOT', root):
                load_project_env()
            self.assertEqual(os.environ.get(key), 'from-os')
            os.environ.pop(key, None)


if __name__ == '__main__':
    unittest.main()
