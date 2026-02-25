"""
Generation pipeline orchestrator.

Coordinates the full flow: download → parse → analyze → generate → write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flet_pkg.core.analyzer import PackageAnalyzer
from flet_pkg.core.downloader import PubDevDownloader
from flet_pkg.core.generators import (
    DartServiceGenerator,
    PythonControlGenerator,
    PythonInitGenerator,
    PythonSubModuleGenerator,
    PythonTypesGenerator,
)
from flet_pkg.core.models import GenerationPlan
from flet_pkg.core.parser import parse_dart_package_api
from flet_pkg.ui.console import console


@dataclass
class PipelineResult:
    """Result of a generation pipeline run."""

    project_dir: Path
    plan: GenerationPlan
    files_generated: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class GenerationPipeline:
    """Orchestrates the full code generation pipeline.

    Steps:
    1. Download Flutter package from pub.dev (or use local path)
    2. Parse Dart sources into DartPackageAPI
    3. Analyze API to produce GenerationPlan
    4. Run generators to produce Python + Dart files
    5. Write generated files to project directory (overwriting template stubs)
    """

    def __init__(self):
        self.downloader = PubDevDownloader()
        self.analyzer = PackageAnalyzer()

    def run(
        self,
        flutter_package: str,
        control_name: str,
        extension_type: str,
        project_dir: Path,
        package_name: str,
        description: str = "",
        local_package: Path | None = None,
        control_name_snake: str = "",
    ) -> PipelineResult:
        """Run the full generation pipeline.

        Args:
            flutter_package: Flutter package name (pub.dev).
            control_name: PascalCase control class name.
            extension_type: ``"service"`` or ``"ui_control"``.
            project_dir: Path to the scaffolded project directory.
            package_name: Python package name.
            description: Package description.
            local_package: If set, use this local path instead of downloading.
            control_name_snake: Snake_case name for files (matches template context).

        Returns:
            PipelineResult with generated file list and warnings.
        """
        result = PipelineResult(
            project_dir=project_dir,
            plan=GenerationPlan(
                control_name=control_name,
                package_name=package_name,
            ),
        )

        # Step 1: Get package source
        try:
            if local_package:
                package_path = local_package
                console.print(f"  [info]Using local package:[/info] {package_path}")
            else:
                package_path = self.downloader.download(flutter_package)
                console.print(f"  [success]Downloaded {flutter_package}[/success]")
        except Exception as e:
            result.warnings.append(f"Download failed: {e}")
            console.print(f"  [warning]Download failed: {e}[/warning]")
            return result

        # Step 2: Parse
        try:
            api = parse_dart_package_api(package_path)
            n_classes = len(api.classes)
            n_enums = len(api.enums)
            n_helpers = len(api.helper_classes)
            console.print(
                f"  [success]Parsed {n_classes} classes, {n_enums} enums, "
                f"{n_helpers} helper types[/success]"
            )
        except Exception as e:
            result.warnings.append(f"Parse failed: {e}")
            console.print(f"  [warning]Parse failed: {e}[/warning]")
            return result

        if not api.classes:
            result.warnings.append("No public classes found in package.")
            console.print("  [warning]No public classes found.[/warning]")
            return result

        # Step 3: Analyze
        try:
            plan = self.analyzer.analyze(
                api,
                control_name=control_name,
                extension_type=extension_type,
                flutter_package=flutter_package,
                package_name=package_name,
                description=description,
            )
            # Set control_name_snake from the template context
            plan.control_name_snake = control_name_snake
            result.plan = plan
            n_methods = len(plan.main_methods) + sum(
                len(s.methods) for s in plan.sub_modules
            )
            console.print(
                f"  [success]Analyzed: {n_methods} methods, "
                f"{len(plan.sub_modules)} sub-modules, "
                f"{len(plan.events)} events[/success]"
            )
        except Exception as e:
            result.warnings.append(f"Analysis failed: {e}")
            console.print(f"  [warning]Analysis failed: {e}[/warning]")
            return result

        # Step 4: Generate
        generators = [
            PythonControlGenerator(),
            PythonSubModuleGenerator(),
            PythonTypesGenerator(),
            PythonInitGenerator(),
            DartServiceGenerator(),
        ]

        all_files: dict[str, str] = {}
        for gen in generators:
            try:
                files = gen.generate(plan)
                all_files.update(files)
            except Exception as e:
                result.warnings.append(
                    f"Generator {gen.__class__.__name__} failed: {e}"
                )

        # Step 5: Write files (overwriting template stubs)
        python_pkg_dir = project_dir / "src" / package_name
        dart_src_dir = (
            project_dir / "src" / "flutter" / package_name / "lib" / "src"
        )

        for filename, content in all_files.items():
            if filename.endswith(".dart"):
                target = dart_src_dir / filename
            else:
                target = python_pkg_dir / filename

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            result.files_generated.append(str(target.relative_to(project_dir)))

        # Clean up template stubs that were replaced by generated files
        self._cleanup_stubs(project_dir, package_name, all_files, result)

        console.print(
            f"  [success]Generated {len(result.files_generated)} files[/success]"
        )

        return result

    def _cleanup_stubs(
        self,
        project_dir: Path,
        package_name: str,
        generated_files: dict[str, str],
        result: PipelineResult,
    ) -> None:
        """Remove template stub files that conflict with generated files.

        The template creates stub files like ``onesignal.py`` and
        ``onesignal_service.dart``, but the generators may produce files
        with the same purpose under different names. This method removes
        orphaned stubs to prevent import conflicts.
        """
        python_pkg_dir = project_dir / "src" / package_name
        dart_src_dir = (
            project_dir / "src" / "flutter" / package_name / "lib" / "src"
        )

        generated_py = {f for f in generated_files if f.endswith(".py")}
        generated_dart = {f for f in generated_files if f.endswith(".dart")}

        # Check for conflicting Python stubs
        for py_file in python_pkg_dir.glob("*.py"):
            name = py_file.name
            if name in generated_py or name == "__init__.py":
                continue
            # Check if this is a stub with TODO content (from template)
            try:
                content = py_file.read_text(encoding="utf-8")
                if "TODO" in content or "example_method" in content:
                    py_file.unlink()
            except Exception:
                pass

        # Check for conflicting Dart stubs
        for dart_file in dart_src_dir.glob("*.dart"):
            name = dart_file.name
            if name in generated_dart or name == "extension.dart":
                continue
            try:
                content = dart_file.read_text(encoding="utf-8")
                if "TODO" in content or "example_method" in content:
                    dart_file.unlink()
            except Exception:
                pass
