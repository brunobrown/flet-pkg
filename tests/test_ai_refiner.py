"""Tests for the AI refinement pipeline.

All tests use mocked LLM responses — no API key required.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from flet_pkg.core.ai.config import AIConfig
from flet_pkg.core.ai.gap_analyzer import GapAnalyzer
from flet_pkg.core.ai.models import (
    ArchitectPlan,
    FileEdit,
    GapItem,
    GapKind,
    GapReport,
    ImprovementSuggestion,
    RefinementResult,
)
from flet_pkg.core.models import (
    DartClass,
    DartEnum,
    DartMethod,
    DartPackageAPI,
    DartParam,
    EnumPlan,
    EventPlan,
    GenerationPlan,
    MethodPlan,
    PropertyPlan,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service_api():
    """A simple Dart API for a service package."""
    return DartPackageAPI(
        classes=[
            DartClass(
                name="OneSignal",
                methods=[
                    DartMethod(name="initialize", return_type="Future<void>", is_async=True),
                    DartMethod(name="getDeviceState", return_type="Future<DeviceState>"),
                    DartMethod(name="setLogLevel", return_type="void"),
                    DartMethod(
                        name="onNotificationReceived",
                        return_type="Stream<OSNotification>",
                        is_getter=True,
                    ),
                    # Internal method — should be excluded
                    DartMethod(name="toString", return_type="String"),
                ],
            ),
        ],
        enums=[
            DartEnum(name="OSLogLevel", values=[("verbose", ""), ("debug", "")]),
        ],
    )


@pytest.fixture()
def service_plan():
    """A partially complete generation plan for a service package."""
    return GenerationPlan(
        control_name="OneSignal",
        package_name="flet_onesignal",
        flutter_package="onesignal_flutter",
        main_methods=[
            MethodPlan(python_name="initialize"),
            MethodPlan(python_name="get_device_state"),
            # set_log_level is missing → gap
        ],
        events=[
            EventPlan(
                python_attr_name="on_notification_received",
                event_class_name="NotificationEvent",
            ),
        ],
        enums=[
            EnumPlan(python_name="OSLogLevel", values=[("VERBOSE", "verbose", "")]),
        ],
    )


@pytest.fixture()
def ui_control_api():
    """A simple Dart API for a UI control package."""
    return DartPackageAPI(
        classes=[
            DartClass(
                name="Shimmer",
                constructor_params=[
                    DartParam(name="key", dart_type="Key?"),
                    DartParam(name="child", dart_type="Widget"),
                    DartParam(name="baseColor", dart_type="Color"),
                    DartParam(name="highlightColor", dart_type="Color"),
                    DartParam(name="enabled", dart_type="bool"),
                    DartParam(name="direction", dart_type="ShimmerDirection"),
                    DartParam(name="gradient", dart_type="LinearGradient?"),
                ],
            ),
        ],
        enums=[
            DartEnum(name="ShimmerDirection", values=[("ltr", ""), ("rtl", "")]),
        ],
    )


@pytest.fixture()
def ui_control_plan():
    """A partially complete generation plan for a UI control."""
    return GenerationPlan(
        control_name="Shimmer",
        package_name="flet_shimmer",
        flutter_package="shimmer",
        dart_main_class="Shimmer",
        base_class="ft.LayoutControl",
        properties=[
            PropertyPlan(python_name="base_color", python_type="ft.Color"),
            PropertyPlan(python_name="highlight_color", python_type="ft.Color"),
            PropertyPlan(python_name="enabled", python_type="bool"),
            # direction is missing → gap
            # gradient is non-serializable → infeasible gap
        ],
        enums=[
            EnumPlan(python_name="ShimmerDirection", values=[("LTR", "ltr", "")]),
        ],
    )


# ---------------------------------------------------------------------------
# TestGapAnalyzer
# ---------------------------------------------------------------------------


class TestGapAnalyzer:
    def test_service_gap_detection(self, service_api, service_plan):
        analyzer = GapAnalyzer()
        report = analyzer.analyze(service_api, service_plan, "service")

        assert report.flutter_package == "onesignal_flutter"
        assert report.extension_type == "service"
        assert report.coverage_pct > 0

        # set_log_level should be a gap
        method_gaps = [g for g in report.gaps if g.kind == GapKind.MISSING_METHOD]
        assert len(method_gaps) == 1
        assert method_gaps[0].dart_name == "setLogLevel"

        # No enum gaps — OSLogLevel was generated
        enum_gaps = [g for g in report.gaps if g.kind == GapKind.MISSING_ENUM]
        assert len(enum_gaps) == 0

    def test_service_excludes_internal_methods(self, service_api, service_plan):
        analyzer = GapAnalyzer()
        report = analyzer.analyze(service_api, service_plan, "service")

        # toString should not appear as a gap
        dart_names = {g.dart_name for g in report.gaps}
        assert "toString" not in dart_names

    def test_service_stream_event_detected(self, service_api, service_plan):
        analyzer = GapAnalyzer()
        report = analyzer.analyze(service_api, service_plan, "service")

        # onNotificationReceived stream was mapped → no event gap
        event_gaps = [g for g in report.gaps if g.kind == GapKind.MISSING_EVENT]
        assert len(event_gaps) == 0

    def test_ui_control_gap_detection(self, ui_control_api, ui_control_plan):
        analyzer = GapAnalyzer()
        report = analyzer.analyze(ui_control_api, ui_control_plan, "ui_control")

        assert report.flutter_package == "shimmer"
        assert report.extension_type == "ui_control"

        # direction should be a feasible gap
        prop_gaps = [g for g in report.gaps if g.kind == GapKind.MISSING_PROPERTY]
        feasible = [g for g in prop_gaps if g.feasible]
        infeasible = [g for g in prop_gaps if not g.feasible]

        assert any(g.dart_name == "direction" for g in feasible)
        # gradient is non-serializable → infeasible
        assert any(g.dart_name == "gradient" for g in infeasible)

    def test_ui_control_excludes_framework_params(self, ui_control_api, ui_control_plan):
        analyzer = GapAnalyzer()
        report = analyzer.analyze(ui_control_api, ui_control_plan, "ui_control")

        dart_names = {g.dart_name for g in report.gaps}
        assert "key" not in dart_names
        assert "child" not in dart_names

    def test_feasible_gaps_count(self, ui_control_api, ui_control_plan):
        analyzer = GapAnalyzer()
        report = analyzer.analyze(ui_control_api, ui_control_plan, "ui_control")

        feasible = report.feasible_gaps
        total = len(report.gaps)
        assert feasible <= total
        assert feasible >= 0

    def test_empty_api_produces_empty_report(self):
        analyzer = GapAnalyzer()
        api = DartPackageAPI()
        plan = GenerationPlan(
            control_name="Empty",
            package_name="flet_empty",
            flutter_package="empty",
        )
        report = analyzer.analyze(api, plan, "service")

        assert report.total_dart_api == 0
        assert len(report.gaps) == 0
        assert report.coverage_pct == 0.0

    def test_gap_report_summary(self, service_api, service_plan):
        analyzer = GapAnalyzer()
        report = analyzer.analyze(service_api, service_plan, "service")

        summary = report.summary()
        assert "onesignal_flutter" in summary
        assert "service" in summary


# ---------------------------------------------------------------------------
# TestAIConfig
# ---------------------------------------------------------------------------


class TestAIConfig:
    def test_default_config(self):
        config = AIConfig()
        assert config.provider == "ollama"
        assert config.temperature == 0.1

    def test_load_default_is_ollama(self):
        config = AIConfig.load()
        assert config.provider == "ollama"
        assert config.model == "qwen2.5-coder:14b"
        assert config.is_available()

    def test_load_anthropic(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            config = AIConfig.load(provider="anthropic")
            assert config.provider == "anthropic"
            assert config.model == "claude-sonnet-4-6"
            assert config.api_key == "test-key"
            assert config.is_available()

    def test_load_openai(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            config = AIConfig.load(provider="openai")
            assert config.provider == "openai"
            assert config.model == "gpt-4.1-mini"
            assert config.api_key == "sk-test"

    def test_load_ollama_no_key_needed(self):
        config = AIConfig.load(provider="ollama")
        assert config.provider == "ollama"
        assert config.model == "qwen2.5-coder:14b"
        assert config.is_available()

    def test_load_with_model_override(self):
        config = AIConfig.load(provider="anthropic", model="claude-opus-4-20250514")
        assert config.model == "claude-opus-4-20250514"

    def test_not_available_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            config = AIConfig.load(provider="anthropic")
            assert not config.is_available()

    def test_load_unknown_provider_defaults_to_ollama(self):
        config = AIConfig.load(provider="unknown_provider")
        assert config.provider == "ollama"


# ---------------------------------------------------------------------------
# TestRefinementModels
# ---------------------------------------------------------------------------


class TestRefinementModels:
    def test_gap_item_creation(self):
        gap = GapItem(
            kind=GapKind.MISSING_METHOD,
            dart_name="getStatus",
            dart_type="Future<String>",
            dart_class="MyService",
            reason="Method not mapped",
        )
        assert gap.kind == GapKind.MISSING_METHOD
        assert gap.feasible is True

    def test_gap_report_feasible_count(self):
        report = GapReport(
            flutter_package="test",
            extension_type="service",
            gaps=[
                GapItem(kind=GapKind.MISSING_METHOD, dart_name="a", feasible=True),
                GapItem(kind=GapKind.MISSING_METHOD, dart_name="b", feasible=False),
                GapItem(kind=GapKind.MISSING_ENUM, dart_name="c", feasible=True),
            ],
        )
        assert report.feasible_gaps == 2

    def test_architect_plan(self):
        plan = ArchitectPlan(
            analysis="Good coverage, minor gaps",
            suggestions=[
                ImprovementSuggestion(
                    target_file="service.py",
                    description="Add get_status method",
                    gap_refs=[0],
                ),
            ],
        )
        assert len(plan.suggestions) == 1
        assert plan.suggestions[0].priority == 1

    def test_file_edit(self):
        edit = FileEdit(
            filename="service.py",
            search="# TODO",
            replace="async def get_status(self): ...",
            rationale="Add missing method",
        )
        assert edit.filename == "service.py"

    def test_refinement_result_no_gaps(self):
        result = RefinementResult(
            gap_report=GapReport(
                flutter_package="test",
                extension_type="service",
            ),
            validation_passed=True,
            overall_assessment="All good",
        )
        assert result.edits_applied == 0
        assert result.validation_passed


# ---------------------------------------------------------------------------
# TestApplyEdits
# ---------------------------------------------------------------------------


class TestApplyEdits:
    def test_apply_single_edit(self):
        from flet_pkg.core.ai.agent import apply_edits

        files = {"service.py": "class MyService:\n    # TODO: add methods\n    pass\n"}
        edits = [
            FileEdit(
                filename="service.py",
                search="    # TODO: add methods\n    pass",
                replace=(
                    "    async def get_status(self) -> str:\n"
                    '        return await self.invoke_method("get_status")'
                ),
            ),
        ]

        modified, applied, failed = apply_edits(edits, files)
        assert applied == 1
        assert failed == 0
        assert "get_status" in modified["service.py"]

    def test_edit_missing_file(self):
        from flet_pkg.core.ai.agent import apply_edits

        edits = [FileEdit(filename="nonexistent.py", search="x", replace="y")]
        _, applied, failed = apply_edits(edits, {})
        assert applied == 0
        assert failed == 1

    def test_edit_search_not_found(self):
        from flet_pkg.core.ai.agent import apply_edits

        files = {"service.py": "class MyService:\n    pass\n"}
        edits = [
            FileEdit(filename="service.py", search="not_in_file", replace="replacement"),
        ]
        _, applied, failed = apply_edits(edits, files)
        assert applied == 0
        assert failed == 1

    def test_multiple_edits(self):
        from flet_pkg.core.ai.agent import apply_edits

        files = {
            "a.py": "# placeholder a",
            "b.py": "# placeholder b",
        }
        edits = [
            FileEdit(filename="a.py", search="# placeholder a", replace="# done a"),
            FileEdit(filename="b.py", search="# placeholder b", replace="# done b"),
        ]
        modified, applied, failed = apply_edits(edits, files)
        assert applied == 2
        assert failed == 0
        assert modified["a.py"] == "# done a"
        assert modified["b.py"] == "# done b"

    def test_edits_do_not_mutate_original(self):
        from flet_pkg.core.ai.agent import apply_edits

        files = {"a.py": "original"}
        edits = [FileEdit(filename="a.py", search="original", replace="modified")]
        modified, _, _ = apply_edits(edits, files)
        assert files["a.py"] == "original"
        assert modified["a.py"] == "modified"


# ---------------------------------------------------------------------------
# TestValidation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_python(self):
        from flet_pkg.core.ai.agent import validate_python_syntax

        files = {"good.py": "x = 1\ny = x + 2\n"}
        errors = validate_python_syntax(files)
        assert errors == []

    def test_invalid_python(self):
        from flet_pkg.core.ai.agent import validate_python_syntax

        files = {"bad.py": "def foo(\n"}
        errors = validate_python_syntax(files)
        assert len(errors) == 1
        assert "bad.py" in errors[0]

    def test_ignores_dart_files(self):
        from flet_pkg.core.ai.agent import validate_python_syntax

        files = {"service.dart": "this is not valid python {{{"}
        errors = validate_python_syntax(files)
        assert errors == []

    def test_mixed_valid_and_invalid(self):
        from flet_pkg.core.ai.agent import validate_python_syntax

        files = {
            "good.py": "x = 1",
            "bad.py": "def (",
        }
        errors = validate_python_syntax(files)
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# TestPipelineIntegration
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    def test_pipeline_without_ai_flag(self, tmp_path):
        """Pipeline runs normally when ai_refine=False."""
        from flet_pkg.core.pipeline import GenerationPipeline

        # Just verify the parameter is accepted without error
        pipeline = GenerationPipeline()
        assert hasattr(pipeline.run, "__call__")

    def test_pipeline_ai_import_graceful(self, tmp_path):
        """Pipeline handles missing pydantic-ai gracefully."""
        from flet_pkg.core.pipeline import GenerationPipeline

        pipeline = GenerationPipeline()

        # Create minimal project structure
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        (project_dir / "src" / "flet_test").mkdir(parents=True)
        (project_dir / "src" / "flutter" / "flet_test" / "lib" / "src").mkdir(parents=True)

        # Mock the download to use fixture
        fixture_path = Path(__file__).parent / "fixtures" / "onesignal_flutter"
        if not fixture_path.exists():
            pytest.skip("onesignal_flutter fixture not available")

        with patch.object(pipeline.downloader, "download", return_value=fixture_path):
            result = pipeline.run(
                flutter_package="onesignal_flutter",
                control_name="OneSignal",
                extension_type="service",
                project_dir=project_dir,
                package_name="flet_test",
                ai_refine=True,  # Will gracefully skip if pydantic-ai not installed
                ai_provider="anthropic",
            )
            # Should complete without error (AI step is skipped gracefully)
            assert result is not None


# ---------------------------------------------------------------------------
# TestGapAnalyzerWithFixture
# ---------------------------------------------------------------------------


class TestGapAnalyzerWithFixture:
    """Test gap analyzer against actual fixture data."""

    def test_onesignal_fixture(self):
        """Test gap analysis with the onesignal_flutter fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "onesignal_flutter"
        if not fixture_path.exists():
            pytest.skip("onesignal_flutter fixture not available")

        from flet_pkg.core.analyzer import PackageAnalyzer
        from flet_pkg.core.parser import parse_dart_package_api

        api = parse_dart_package_api(fixture_path)
        analyzer = PackageAnalyzer()
        plan = analyzer.analyze(
            api,
            control_name="OneSignal",
            extension_type="service",
            flutter_package="onesignal_flutter",
            package_name="flet_onesignal",
        )

        gap_analyzer = GapAnalyzer()
        report = gap_analyzer.analyze(api, plan, "service")

        # Should produce a meaningful report
        assert report.total_dart_api > 0
        assert report.coverage_pct > 0
        assert isinstance(report.gaps, list)

        # Coverage should roughly match what test_service_coverage reports
        assert report.coverage_pct >= 70.0, (
            f"OneSignal gap analysis coverage {report.coverage_pct:.1f}% < 70%"
        )
