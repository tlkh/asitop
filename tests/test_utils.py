import os
import pathlib
import tempfile
import unittest
from unittest import mock

from asitop.utils import cleanup_powermetrics_files, get_powermetrics_path


class UtilsTests(unittest.TestCase):
    def test_get_powermetrics_path_uses_per_user_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(get_powermetrics_path("123", base_dir=tmpdir))
            self.assertEqual(path.parent, pathlib.Path(tmpdir) / f"asitop-{os.getuid()}")
            self.assertEqual(path.name, "powermetrics-123.plist")

    def test_cleanup_powermetrics_files_ignores_missing_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(get_powermetrics_path("123", base_dir=tmpdir))
            path.write_text("x")

            real_remove = os.remove

            def flaky_remove(target):
                real_remove(target)
                raise FileNotFoundError(target)

            with mock.patch("asitop.utils.os.remove", side_effect=flaky_remove):
                cleanup_powermetrics_files(base_dir=tmpdir)

            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
