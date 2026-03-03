from unittest.mock import patch

from typer.testing import CliRunner

from flet_pkg import __version__
from flet_pkg.main import app

runner = CliRunner()


def _no_registry_check(project_name: str) -> None:
    """Stub that skips the PyPI/GitHub check during tests."""


class TestCLI:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "create" in result.output

    def test_create_help(self):
        result = runner.invoke(app, ["create", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output
        assert "--flutter-package" in result.output

    def test_create_invalid_type(self):
        result = runner.invoke(app, ["create", "--type", "invalid"])
        assert result.exit_code == 1

    @patch("flet_pkg.commands.create._check_existing_packages", _no_registry_check)
    def test_create_service_non_interactive(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "create",
                "--type",
                "service",
                "--flutter-package",
                "onesignal_flutter",
                "--output",
                str(tmp_path),
                "--no-ai-refine",
            ],
            input="flet-onesignal\nflet_onesignal\nOneSignal\nA test\nAuthor\ny\n",
        )
        assert result.exit_code == 0
        assert (tmp_path / "flet-onesignal").is_dir()
        assert (tmp_path / "flet-onesignal" / "pyproject.toml").is_file()

    @patch("flet_pkg.commands.create._check_existing_packages", _no_registry_check)
    def test_create_ui_control_non_interactive(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "create",
                "--type",
                "ui_control",
                "--flutter-package",
                "flutter_spinkit",
                "--output",
                str(tmp_path),
                "--no-ai-refine",
            ],
            input="flet-spinkit\nflet_spinkit\nSpinkit\nA widget\nAuthor\ny\n",
        )
        assert result.exit_code == 0
        assert (tmp_path / "flet-spinkit").is_dir()
        control = tmp_path / "flet-spinkit" / "src" / "flet_spinkit" / "spinkit.py"
        assert control.is_file()
        assert "LayoutControl" in control.read_text()
