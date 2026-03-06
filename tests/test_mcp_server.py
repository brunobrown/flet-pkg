"""Tests for the flet-pkg MCP server."""

from __future__ import annotations

import pytest

mcp_mod = pytest.importorskip("mcp")  # noqa: F841 — skip all tests if mcp not installed

from pathlib import Path  # noqa: E402

from flet_pkg.mcp._serializers import to_dict  # noqa: E402
from flet_pkg.mcp.server import (  # noqa: E402
    mcp,
    tool_derive_names,
    tool_map_dart_type,
    tool_run_pipeline,
    tool_scaffold,
)

FIXTURES = Path(__file__).parent / "fixtures"
ONESIGNAL_FIXTURE = FIXTURES / "onesignal_flutter"


# ---------------------------------------------------------------------------
# _serializers.to_dict
# ---------------------------------------------------------------------------


class TestToDict:
    def test_dataclass(self):
        from flet_pkg.core.validators import DerivedNames

        obj = DerivedNames("flet-foo", "flet_foo", "Foo", "foo")
        result = to_dict(obj)
        assert result == {
            "project_name": "flet-foo",
            "package_name": "flet_foo",
            "control_name": "Foo",
            "control_name_snake": "foo",
        }

    def test_path(self):
        assert to_dict(Path("/tmp/foo")) == "/tmp/foo"

    def test_enum(self):
        from flet_pkg.core.ai.models import GapKind

        assert to_dict(GapKind.MISSING_METHOD) == "missing_method"

    def test_tuple(self):
        assert to_dict(("a", "b")) == ["a", "b"]

    def test_nested_list(self):
        assert to_dict([Path("/a"), Path("/b")]) == ["/a", "/b"]

    def test_dict_values(self):
        assert to_dict({"k": Path("/v")}) == {"k": "/v"}

    def test_primitive(self):
        assert to_dict(42) == 42
        assert to_dict("hello") == "hello"
        assert to_dict(None) is None


# ---------------------------------------------------------------------------
# Tool 1: derive_names
# ---------------------------------------------------------------------------


class TestDeriveNames:
    def test_valid_package(self):
        result = tool_derive_names("onesignal_flutter")
        assert result["project_name"] == "flet-onesignal"
        assert result["package_name"] == "flet_onesignal"
        assert result["control_name"] == "Onesignal"
        assert result["control_name_snake"] == "onesignal"

    def test_invalid_package(self):
        with pytest.raises(ValueError, match="Invalid flutter_package"):
            tool_derive_names("Invalid-Name")


# ---------------------------------------------------------------------------
# Tool 2: map_dart_type
# ---------------------------------------------------------------------------


class TestMapDartType:
    def test_standard(self):
        result = tool_map_dart_type("Future<String?>")
        assert result["python_type"] == "str | None"
        assert result["skipped"] is False

    def test_flet_aware(self):
        result = tool_map_dart_type("Alignment", flet_aware=True)
        assert result["python_type"] == "ft.Alignment"
        assert result["skipped"] is False

    def test_flet_skipped(self):
        result = tool_map_dart_type("Key", flet_aware=True)
        assert result["python_type"] == "SKIPPED"
        assert result["skipped"] is True


# ---------------------------------------------------------------------------
# Tool 5: scaffold
# ---------------------------------------------------------------------------


class TestScaffold:
    def test_scaffold_service(self, tmp_path):
        result = tool_scaffold(
            template_name="service",
            flutter_package="battery_plus",
            project_name="flet-battery",
            package_name="flet_battery",
            control_name="Battery",
            description="Test battery extension",
            output_dir=str(tmp_path),
        )
        project_dir = Path(result["project_dir"])
        assert project_dir.exists()
        assert len(result["files"]) > 0
        # Check key files exist
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "src" / "flet_battery" / "__init__.py").exists()

    def test_scaffold_duplicate_raises(self, tmp_path):
        kwargs = dict(
            template_name="service",
            flutter_package="battery_plus",
            project_name="flet-battery",
            package_name="flet_battery",
            control_name="Battery",
            output_dir=str(tmp_path),
        )
        tool_scaffold(**kwargs)
        with pytest.raises(FileExistsError):
            tool_scaffold(**kwargs)


# ---------------------------------------------------------------------------
# Tool 6: run_pipeline (local fixture)
# ---------------------------------------------------------------------------


class TestRunPipeline:
    def test_run_pipeline_local(self, tmp_path):
        # First scaffold
        tool_scaffold(
            template_name="service",
            flutter_package="onesignal_flutter",
            project_name="flet-onesignal",
            package_name="flet_onesignal",
            control_name="OneSignal",
            output_dir=str(tmp_path),
        )

        project_dir = tmp_path / "flet-onesignal"
        result = tool_run_pipeline(
            flutter_package="onesignal_flutter",
            control_name="OneSignal",
            extension_type="service",
            project_dir=str(project_dir),
            package_name="flet_onesignal",
            control_name_snake="one_signal",
            local_package_path=str(ONESIGNAL_FIXTURE),
        )
        assert len(result["files_generated"]) > 0
        assert result["plan_summary"]["control_name"] == "OneSignal"
        assert result["plan_summary"]["n_methods"] > 0


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class TestResources:
    def test_type_map_resource(self):
        from flet_pkg.mcp.server import resource_type_map

        result = resource_type_map()
        assert "String" in result["standard"]
        assert result["standard"]["String"] == "str"
        assert "Alignment" in result["flet_aware"]
        assert "Key" in result["skipped"]

    def test_templates_resource(self):
        from flet_pkg.mcp.server import resource_templates

        result = resource_templates()
        assert "service" in result["templates"]
        assert "ui_control" in result["templates"]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_scaffold_service_prompt(self):
        from flet_pkg.mcp.server import scaffold_service

        result = scaffold_service("battery_plus")
        assert "battery_plus" in result
        assert "service" in result

    def test_scaffold_ui_control_prompt(self):
        from flet_pkg.mcp.server import scaffold_ui_control

        result = scaffold_ui_control("flutter_slidable")
        assert "flutter_slidable" in result
        assert "ui_control" in result

    def test_analyze_package_prompt(self):
        from flet_pkg.mcp.server import analyze_package

        result = analyze_package("battery_plus", "service")
        assert "battery_plus" in result
        assert "service" in result


# ---------------------------------------------------------------------------
# Server registration
# ---------------------------------------------------------------------------


class TestServerRegistration:
    def test_server_name(self):
        assert mcp.name == "flet-pkg"

    def test_tools_registered(self):
        tool_manager = mcp._tool_manager
        tool_names = list(tool_manager._tools.keys())
        assert "tool_derive_names" in tool_names
        assert "tool_map_dart_type" in tool_names
        assert "tool_fetch_metadata" in tool_names
        assert "tool_detect_extension_type" in tool_names
        assert "tool_scaffold" in tool_names
        assert "tool_run_pipeline" in tool_names
        assert "tool_analyze_gaps" in tool_names
