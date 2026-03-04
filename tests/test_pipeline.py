from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from flet_pkg.core.ai.models import GapReport
from flet_pkg.core.pipeline import GenerationPipeline, PipelineResult
from flet_pkg.ui.coverage import print_coverage_score, print_coverage_table

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "onesignal_flutter"


@pytest.fixture
def pipeline():
    return GenerationPipeline()


def _setup_project(tmp_path):
    project_dir = tmp_path / "flet-onesignal"
    project_dir.mkdir()
    (project_dir / "src" / "flet_onesignal").mkdir(parents=True)
    (project_dir / "src" / "flutter" / "flet_onesignal" / "lib" / "src").mkdir(parents=True)
    return project_dir


class TestPipelineWithFixtures:
    """Integration tests using the test fixture Dart files."""

    def test_full_pipeline_with_local_package(self, pipeline, tmp_path):
        """Test the full pipeline using local test fixtures."""
        project_dir = _setup_project(tmp_path)

        result = pipeline.run(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_onesignal",
            description="OneSignal integration",
            local_package=FIXTURE_PATH,
        )

        assert isinstance(result, PipelineResult)
        assert result.project_dir == project_dir
        assert len(result.files_generated) > 0
        assert len(result.warnings) == 0

    def test_generates_python_control(self, pipeline, tmp_path):
        project_dir = _setup_project(tmp_path)

        pipeline.run(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_onesignal",
            local_package=FIXTURE_PATH,
        )

        control_file = project_dir / "src" / "flet_onesignal" / "one_signal.py"
        assert control_file.exists()
        content = control_file.read_text()
        assert "class OneSignal" in content
        assert "ft.Service" in content

    def test_generates_dart_service(self, pipeline, tmp_path):
        project_dir = _setup_project(tmp_path)

        pipeline.run(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_onesignal",
            local_package=FIXTURE_PATH,
        )

        dart_file = (
            project_dir
            / "src"
            / "flutter"
            / "flet_onesignal"
            / "lib"
            / "src"
            / "one_signal_service.dart"
        )
        assert dart_file.exists()
        content = dart_file.read_text()
        assert "OneSignalService" in content
        assert "FletService" in content

    def test_generates_submodules(self, pipeline, tmp_path):
        project_dir = _setup_project(tmp_path)

        pipeline.run(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_onesignal",
            local_package=FIXTURE_PATH,
        )

        # Check that sub-module files were generated
        python_dir = project_dir / "src" / "flet_onesignal"
        py_files = list(python_dir.glob("*.py"))
        py_names = [f.name for f in py_files]
        # Should have at least: one_signal.py, __init__.py, types.py
        assert "one_signal.py" in py_names
        assert "__init__.py" in py_names


class TestPipelineErrors:
    def test_download_failure_warns(self, pipeline, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with patch.object(
            pipeline.downloader,
            "download",
            side_effect=Exception("Network error"),
        ):
            result = pipeline.run(
                flutter_package="bad_package",
                control_name="Bad",
                extension_type="service",
                project_dir=project_dir,
                package_name="flet_bad",
            )

        assert len(result.warnings) > 0
        assert "Download failed" in result.warnings[0]
        assert result.files_generated == []

    def test_empty_package_warns(self, pipeline, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create empty lib directory
        empty_pkg = tmp_path / "empty_flutter"
        (empty_pkg / "lib").mkdir(parents=True)

        result = pipeline.run(
            flutter_package="empty_flutter",
            control_name="Empty",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_empty",
            local_package=empty_pkg,
        )

        assert len(result.warnings) > 0
        assert result.files_generated == []


class TestPipelineCoverage:
    """Tests for coverage score and gap report in pipeline results."""

    def test_pipeline_result_has_coverage(self, pipeline, tmp_path):
        """Coverage percentage and gap_report should be populated after a run."""
        project_dir = _setup_project(tmp_path)

        result = pipeline.run(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_onesignal",
            local_package=FIXTURE_PATH,
        )

        assert result.coverage_pct > 0
        assert result.gap_report is not None
        assert result.gap_report.total_dart_api > 0
        assert result.gap_report.total_generated > 0

    def test_pipeline_verbose_runs_without_error(self, pipeline, tmp_path):
        """Pipeline with verbose=True should complete without exceptions."""
        project_dir = _setup_project(tmp_path)

        result = pipeline.run(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_onesignal",
            local_package=FIXTURE_PATH,
            verbose=True,
        )

        assert len(result.files_generated) > 0
        assert result.coverage_pct > 0

    def test_gap_report_has_category_counts(self, pipeline, tmp_path):
        """Gap report should have per-category counts populated."""
        project_dir = _setup_project(tmp_path)

        result = pipeline.run(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=project_dir,
            package_name="flet_onesignal",
            local_package=FIXTURE_PATH,
        )

        assert result.gap_report is not None
        assert len(result.gap_report.category_counts) > 0
        # At least Methods should be present for a service package
        assert "Methods" in result.gap_report.category_counts


class TestCoverageDisplay:
    """Tests for the coverage UI functions."""

    def test_print_coverage_score_format(self):
        """Coverage score line should include percentage and fraction."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=80)

        with patch("flet_pkg.ui.coverage.console", test_console):
            print_coverage_score(95.2, 40, 42)

        output = buf.getvalue()
        assert "95.2%" in output
        assert "40/42" in output

    def test_print_coverage_score_na_when_zero(self):
        """Score should show N/A when there are no Dart APIs."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=80)

        with patch("flet_pkg.ui.coverage.console", test_console):
            print_coverage_score(0.0, 0, 0)

        output = buf.getvalue()
        assert "N/A" in output

    def test_print_coverage_table_renders(self):
        """Coverage table should render categories and totals."""
        report = GapReport(
            flutter_package="test_pkg",
            extension_type="service",
            total_dart_api=30,
            total_generated=27,
            coverage_pct=90.0,
            category_counts={
                "Methods": (20, 18),
                "Events": (5, 5),
                "Enums": (5, 4),
            },
        )

        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=100)

        with patch("flet_pkg.ui.coverage.console", test_console):
            print_coverage_table(report)

        output = buf.getvalue()
        assert "Methods" in output
        assert "Events" in output
        assert "Enums" in output
        assert "Total" in output

    def test_print_coverage_table_empty_report(self):
        """Table should not render when category_counts is empty."""
        report = GapReport(
            flutter_package="test_pkg",
            extension_type="service",
        )

        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, width=80)

        with patch("flet_pkg.ui.coverage.console", test_console):
            print_coverage_table(report)

        output = buf.getvalue()
        assert output.strip() == ""
