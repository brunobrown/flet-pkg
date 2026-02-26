from pathlib import Path
from typing import Optional

import typer

from flet_pkg.core.prompts import ask, ask_choice, ask_confirm
from flet_pkg.core.registry_checker import (
    RegistryMatch,
    check_flet_packages,
    check_github,
    check_pypi,
)
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
    1: ("auto", "Auto-detect (recommended)"),
    2: ("service", "Service (no visual interface)"),
    3: ("ui_control", "UI Control (visual widget)"),
}


def create(
    extension_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Extension type: auto, service or ui_control."
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
        if template_name not in ("auto", "service", "ui_control"):
            error_panel(
                "Error",
                f"Invalid type: {template_name}. Use 'auto', 'service' or 'ui_control'.",
            )
            raise typer.Exit(1)
    else:
        choice = ask_choice("Extension type:", [(k, v[1]) for k, v in EXTENSION_TYPES.items()])
        template_name = EXTENSION_TYPES[choice][0]

    # When auto-detect is selected we need the Flutter package name first
    # so we can download and inspect it.
    if template_name == "auto" and not flutter_package:
        flutter_package = ask(
            "Flutter package name (from pub.dev)",
            validator=validate_flutter_package,
        )

    if template_name == "auto":
        assert flutter_package is not None
        template_name = _auto_detect_type(flutter_package, local_package)

    # Flutter package (ask if not yet provided)
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

    # Check PyPI / GitHub for existing packages
    _check_existing_packages(project_name)

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


def _auto_detect_type(
    flutter_package: str,
    local_package: Path | None = None,
) -> str:
    """Download (or locate) the Flutter package and detect extension type.

    Returns ``"ui_control"`` or ``"service"``.  Falls back to a manual
    choice prompt if the download or detection fails.
    """
    from flet_pkg.core.downloader import PubDevDownloader
    from flet_pkg.core.parser import detect_extension_type

    try:
        if local_package:
            package_path = local_package
        else:
            downloader = PubDevDownloader()
            package_path = downloader.download(flutter_package)

        detected = detect_extension_type(package_path)
        label = (
            "UI Control (visual widget)"
            if detected == "ui_control"
            else "Service (no visual interface)"
        )
        console.print(f"\n  [success]Detected: {label}[/success]\n")
        return detected
    except Exception as e:
        console.print(f"\n  [warning]Auto-detect failed ({e}). Please choose manually:[/warning]")
        manual_choices = [
            (1, "Service (no visual interface)"),
            (2, "UI Control (visual widget)"),
        ]
        choice = ask_choice("Extension type:", manual_choices)
        return "service" if choice == 1 else "ui_control"


def _check_existing_packages(project_name: str) -> None:
    """Check PyPI and GitHub for existing packages with the same name.

    Shows warnings and asks for confirmation when matches are found.
    Silently continues on network errors.
    """
    matches: list[RegistryMatch] = []

    with console.status("[info]Checking PyPI, GitHub and Flet SDK...[/info]"):
        pypi_match = check_pypi(project_name)
        if pypi_match:
            matches.append(pypi_match)

        flet_match = check_flet_packages(project_name)
        if flet_match:
            matches.append(flet_match)

        gh_matches = check_github(project_name)
        matches.extend(gh_matches)

    if not matches:
        return

    console.print(f"\n  [warning]Found existing packages matching '{project_name}':[/warning]")
    for m in matches:
        desc = f" — {m.description}" if m.description else ""
        console.print(f"    [highlight]{m.source}[/highlight]: {m.name}{desc}")
        console.print(f"           {m.url}")

    console.print()
    if not ask_confirm("Continue anyway?"):
        raise typer.Exit(0)
