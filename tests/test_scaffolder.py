import pytest

from flet_pkg.core.scaffolder import Scaffolder


@pytest.fixture
def service_context():
    return {
        "project_name": "flet-test",
        "package_name": "flet_test",
        "control_name": "TestControl",
        "control_name_snake": "test_control",
        "flutter_package": "test_flutter",
        "description": "A test extension",
        "author": "Test Author",
    }


class TestScaffolder:
    def test_generates_project(self, tmp_path, service_context):
        scaffolder = Scaffolder("service", service_context, tmp_path)
        project_dir = scaffolder.generate()

        assert project_dir.exists()
        assert project_dir.name == "flet-test"

    def test_generates_pyproject(self, tmp_path, service_context):
        scaffolder = Scaffolder("service", service_context, tmp_path)
        project_dir = scaffolder.generate()

        pyproject = project_dir / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert 'name = "flet-test"' in content

    def test_generates_python_control(self, tmp_path, service_context):
        scaffolder = Scaffolder("service", service_context, tmp_path)
        project_dir = scaffolder.generate()

        control_file = project_dir / "src" / "flet_test" / "test_control.py"
        assert control_file.exists()
        content = control_file.read_text()
        assert "class TestControl(ft.Service)" in content
        assert '@ft.control("TestControl")' in content

    def test_generates_dart_extension(self, tmp_path, service_context):
        scaffolder = Scaffolder("service", service_context, tmp_path)
        project_dir = scaffolder.generate()

        ext_file = project_dir / "src" / "flutter" / "flet_test" / "lib" / "src" / "extension.dart"
        assert ext_file.exists()
        content = ext_file.read_text()
        assert "createService" in content
        assert '"TestControl"' in content

    def test_generates_dart_service(self, tmp_path, service_context):
        scaffolder = Scaffolder("service", service_context, tmp_path)
        project_dir = scaffolder.generate()

        svc_file = (
            project_dir
            / "src"
            / "flutter"
            / "flet_test"
            / "lib"
            / "src"
            / "test_control_service.dart"
        )
        assert svc_file.exists()
        content = svc_file.read_text()
        assert "TestControlService" in content

    def test_ui_control_template(self, tmp_path):
        context = {
            "project_name": "flet-mywidget",
            "package_name": "flet_mywidget",
            "control_name": "MyWidget",
            "control_name_snake": "my_widget",
            "flutter_package": "my_widget_flutter",
            "description": "A widget extension",
            "author": "Test",
        }
        scaffolder = Scaffolder("ui_control", context, tmp_path)
        project_dir = scaffolder.generate()

        control_file = project_dir / "src" / "flet_mywidget" / "my_widget.py"
        assert control_file.exists()
        content = control_file.read_text()
        assert "ft.LayoutControl" in content

        ext_file = (
            project_dir / "src" / "flutter" / "flet_mywidget" / "lib" / "src" / "extension.dart"
        )
        content = ext_file.read_text()
        assert "createWidget" in content

    def test_raises_on_existing_dir(self, tmp_path, service_context):
        (tmp_path / "flet-test").mkdir()
        scaffolder = Scaffolder("service", service_context, tmp_path)
        with pytest.raises(FileExistsError):
            scaffolder.generate()

    def test_raises_on_invalid_template(self, tmp_path, service_context):
        with pytest.raises(FileNotFoundError):
            Scaffolder("nonexistent", service_context, tmp_path)

    def test_resolves_variable_in_paths(self, tmp_path, service_context):
        scaffolder = Scaffolder("service", service_context, tmp_path)
        project_dir = scaffolder.generate()

        # Check that variable-named directories are resolved
        assert (project_dir / "src" / "flet_test").is_dir()
        assert (project_dir / "src" / "flutter" / "flet_test").is_dir()

    def test_template_yaml_excluded(self, tmp_path, service_context):
        scaffolder = Scaffolder("service", service_context, tmp_path)
        project_dir = scaffolder.generate()

        # template.yaml should not appear in output
        for p in project_dir.rglob("template.yaml"):
            pytest.fail(f"template.yaml found in output at {p}")
