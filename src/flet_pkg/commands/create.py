from pathlib import Path
from typing import Optional

import typer

from flet_pkg.core.prompts import ask, ask_choice
from flet_pkg.core.scaffolder import Scaffolder
from flet_pkg.core.validators import (
    derive_names,
    validate_control_name,
    validate_flutter_package,
    validate_package_name,
    validate_project_name,
)
from flet_pkg.ui.console import console
from flet_pkg.ui.panels import error_panel, header_panel, info_panel
from flet_pkg.ui.tree import print_tree

EXTENSION_TYPES = {
    1: ("service", "Service (no visual interface)"),
    2: ("ui_control", "UI Control (visual widget)"),
}


def create(
    extension_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Extension type: service or ui_control."
    ),
    flutter_package: Optional[str] = typer.Option(
        None, "--flutter-package", "-f", help="Flutter package name from pub.dev."
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory."),
    analyze: bool = typer.Option(
        True,
        "--analyze/--no-analyze",
        help="Analyze Flutter package and generate rich code (default: True).",
    ),
    local_package: Optional[Path] = typer.Option(
        None, "--local-package", "-l", help="Path to a local Flutter package (skip download)."
    ),
) -> None:
    """Create a new Flet extension package."""
    header_panel("Flet Extension Generator", "Create a new Flet extension")

    # Extension type
    if extension_type:
        template_name = extension_type
        if template_name not in ("service", "ui_control"):
            error_panel("Error", f"Invalid type: {template_name}. Use 'service' or 'ui_control'.")
            raise typer.Exit(1)
    else:
        choice = ask_choice("Extension type:", [(k, v[1]) for k, v in EXTENSION_TYPES.items()])
        template_name = EXTENSION_TYPES[choice][0]

    # Flutter package
    if not flutter_package:
        flutter_package = ask(
            "Flutter package name (from pub.dev)",
            validator=validate_flutter_package,
        )

    derived = derive_names(flutter_package)

    # Project name
    project_name = ask(
        "Extension name",
        default=derived.project_name,
        validator=validate_project_name,
    )

    # Package name
    package_name = ask(
        "Python package name",
        default=derived.package_name,
        validator=validate_package_name,
    )

    # Control class name
    control_name = ask(
        "Control class name",
        default=derived.control_name,
        validator=validate_control_name,
    )

    # Description
    description = ask("Description", default="A Flet extension package.")

    # Author
    author = ask("Author", default="")

    context = {
        "project_name": project_name,
        "package_name": package_name,
        "control_name": control_name,
        "control_name_snake": derived.control_name_snake,
        "flutter_package": flutter_package,
        "description": description,
        "author": author,
    }

    output_dir = output or Path.cwd()

    try:
        scaffolder = Scaffolder(template_name, context, output_dir)
        project_dir = scaffolder.generate()
    except FileExistsError as e:
        error_panel("Error", str(e))
        raise typer.Exit(1)
    except Exception as e:
        error_panel("Error", f"Failed to generate project: {e}")
        raise typer.Exit(1)

    # Run analysis pipeline if --analyze
    if analyze:
        console.print()
        console.print("[info]Analyzing Flutter package...[/info]")

        try:
            from flet_pkg.core.pipeline import GenerationPipeline

            pipeline = GenerationPipeline()
            result = pipeline.run(
                flutter_package=flutter_package,
                control_name=control_name,
                extension_type=template_name,
                project_dir=project_dir,
                package_name=package_name,
                description=description,
                local_package=local_package,
                control_name_snake=context["control_name_snake"],
            )

            if result.warnings:
                for warning in result.warnings:
                    console.print(f"  [warning]{warning}[/warning]")

            if result.files_generated:
                console.print(
                    f"\n[success]Auto-generated {len(result.files_generated)} files "
                    f"from {flutter_package} analysis.[/success]"
                )
        except Exception as e:
            console.print(f"  [warning]Analysis skipped: {e}[/warning]")

    print_tree(project_dir)

    console.print()
    info_panel(
        "Next Steps",
        f"cd {project_name}\nuv sync",
    )
