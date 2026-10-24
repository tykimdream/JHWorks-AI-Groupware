"""Credential handling checks use synthetic data and never call a provider."""

import contextlib
import io
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import store_openai_key


class KeyEntryTests(unittest.TestCase):
    def run_entry(
        self, destination: Path, key: str, *, tty: bool = True
    ) -> tuple[int, str]:
        output = io.StringIO()
        with (
            patch.object(store_openai_key, "DESTINATION", destination),
            patch("sys.stdin.isatty", return_value=tty),
            patch("getpass.getpass", return_value=key),
            contextlib.redirect_stdout(output),
        ):
            result = store_openai_key.main()
        self.assertNotIn(key, output.getvalue())
        return result, output.getvalue()

    def test_private_file_and_disabled_ai(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            key = "sk-synthetic_test_value_not_a_real_key"
            result, _ = self.run_entry(target, key)
            self.assertEqual(result, 0)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(
                target.read_text(),
                f"JHWORKS_OPENAI_API_KEY={key}\nJHWORKS_AI_ENABLED=false\n",
            )

    def test_existing_settings_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            target.write_text("original")
            result, _ = self.run_entry(target, "sk-synthetic_test_value_not_a_real_key")
            self.assertEqual(result, 1)
            self.assertEqual(target.read_text(), "original")

    def test_symlink_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            other = Path(folder) / "other"
            target.symlink_to(other)
            result, _ = self.run_entry(target, "sk-synthetic_test_value_not_a_real_key")
            self.assertEqual(result, 1)
            self.assertFalse(other.exists())

    def test_pipe_and_multiline_values_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            for key, tty in [
                ("sk-synthetic_test_value_not_a_real_key", False),
                ("sk-synthetic_test_value\nJHWORKS_AI_ENABLED=true", True),
            ]:
                result, _ = self.run_entry(target, key, tty=tty)
                self.assertEqual(result, 1)
                self.assertFalse(target.exists())

    def test_non_echo_input_failure_never_saves(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".env"
            with (
                patch.object(store_openai_key, "DESTINATION", target),
                patch("sys.stdin.isatty", return_value=True),
                patch(
                    "getpass.getpass",
                    side_effect=store_openai_key.getpass.GetPassWarning,
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(store_openai_key.main(), 1)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
