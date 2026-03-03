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
    # -- Package options --
    extension_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Extension type: [cyan]auto[/cyan], [cyan]service[/cyan] or [cyan]ui_control[/cyan].",
        rich_help_panel="Package Options",
    ),
    flutter_package: Optional[str] = typer.Option(
        None,
        "--flutter-package",
        "-f",
        help="Flutter package name from [link=https://pub.dev]pub.dev[/link].",
        rich_help_panel="Package Options",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for the generated project.",
        rich_help_panel="Package Options",
    ),
    local_package: Optional[Path] = typer.Option(
        None,
        "--local-package",
        "-l",
        help="Path to a local Flutter package (skips pub.dev download).",
        rich_help_panel="Package Options",
    ),
    # -- Code generation options --
    analyze: bool = typer.Option(
        True,
        "--analyze/--no-analyze",
        help=(
            "Analyze the Flutter package and auto-generate Python controls, "
            "type mappings, and Dart bridge code."
        ),
        rich_help_panel="Code Generation",
    ),
    console_module: Optional[bool] = typer.Option(
        None,
        "--console/--no-console",
        help="Include a debug console module for development logging.",
        rich_help_panel="Code Generation",
    ),
    # -- AI refinement options --
    ai_refine: Optional[bool] = typer.Option(
        None,
        "--ai-refine/--no-ai-refine",
        help=(
            "Run AI-powered refinement on generated code. "
            "An LLM analyzes coverage gaps and applies structured edits "
            "using the Architect/Editor pattern. "
            "Install: [cyan]uv add flet-pkg\\[ai][/cyan]. "
            "Set the API key for your provider (e.g. ANTHROPIC_API_KEY). "
            "In interactive mode, you will be prompted if pydantic-ai is installed."
        ),
        rich_help_panel="AI Refinement",
    ),
    ai_provider: Optional[str] = typer.Option(
        None,
        "--ai-provider",
        help=(
            "AI provider: "
            "[cyan]ollama[/cyan] (local, free — no API key), "
            "[cyan]anthropic[/cyan] (Claude), "
            "[cyan]openai[/cyan] (GPT), or "
            "[cyan]google[/cyan] (Gemini). "
            "Cloud providers need an API key via env var: "
            "ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY. "
            "[dim]\\[default: ollama][/dim]"
        ),
        rich_help_panel="AI Refinement",
    ),
    ai_model: Optional[str] = typer.Option(
        None,
        "--ai-model",
        help=(
            "Override the default model for the selected provider. "
            "Defaults: anthropic=[dim]claude-sonnet-4-6[/dim], "
            "openai=[dim]gpt-4.1-mini[/dim], "
            "google=[dim]gemini-2.5-flash[/dim], "
            "ollama=[dim]qwen2.5-coder[/dim]."
        ),
        rich_help_panel="AI Refinement",
    ),
) -> None:
    """[bold]Create a new Flet extension package.[/bold]

    Scaffolds a complete project structure and optionally analyzes the Flutter
    package to auto-generate Python controls, Dart bridge code, type mappings,
    event handlers, and enum definitions.

    [dim]AI refinement (--ai-refine) uses an LLM to detect and fill coverage
    gaps that the deterministic pipeline missed. Requires the \\[ai] extra:[/dim]

    [green]$[/green] uv add flet-pkg\\[ai]
    [green]$[/green] ollama pull qwen2.5-coder              [dim]# free, local[/dim]
    [green]$[/green] flet-pkg create -f shimmer --ai-refine  [dim]# uses Ollama[/dim]

    [dim]Or use a cloud provider (requires API key):[/dim]

    [green]$[/green] export ANTHROPIC_API_KEY=sk-...
    [green]$[/green] flet-pkg create -f shimmer --ai-refine --ai-provider anthropic

    [dim]Run without flags for interactive mode, or pass flags for CI/scripting.[/dim]
    """
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

    # Debug console module
    if console_module is None:
        console_module = ask_confirm("Include debug console module?", default=True)

    # AI refinement
    if ai_refine is None and analyze:
        ai_refine = _ask_ai_refine()
        if ai_refine and ai_provider is None:
            ai_provider = _ask_ai_provider()
    if ai_refine is None:
        ai_refine = False

    context = {
        "project_name": project_name,
        "package_name": package_name,
        "control_name": control_name,
        "control_name_snake": derived.control_name_snake,
        "flutter_package": flutter_package,
        "description": description,
        "author": author,
        "include_console": console_module,
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

    # Remove console.py if --no-console
    if not console_module:
        console_file = project_dir / "src" / package_name / "console.py"
        if console_file.exists():
            console_file.unlink()

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
                include_console=console_module,
                ai_refine=ai_refine,
                ai_provider=ai_provider,
                ai_model=ai_model,
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


AI_PROVIDERS = {
    1: ("ollama", "Ollama (local, free — no API key)"),
    2: ("anthropic", "Anthropic (Claude — requires API key)"),
    3: ("openai", "OpenAI (GPT — requires API key)"),
    4: ("google", "Google (Gemini — requires API key)"),
}


def _ask_ai_refine() -> bool:
    """Ask the user whether to enable AI refinement."""
    try:
        import pydantic_ai  # noqa: F401  # ty: ignore[unresolved-import]

        return ask_confirm("Run AI refinement on generated code?", default=False)
    except ImportError:
        return False


def _ask_ai_provider() -> str:
    """Ask the user to choose an AI provider."""
    choice = ask_choice("AI provider:", [(k, v[1]) for k, v in AI_PROVIDERS.items()])
    provider = AI_PROVIDERS[choice][0]

    if provider == "ollama":
        from flet_pkg.core.ai.config import AIConfig

        config = AIConfig.load(provider="ollama")
        console.print(
            f"\n  [info]Ollama uses local models (no API key needed).[/info]\n"
            f"  [dim]Default model: {config.model}[/dim]\n"
            f"  [dim]Make sure Ollama is running: ollama serve[/dim]\n"
            f"  [dim]Pull the model first: ollama pull {config.model}[/dim]"
        )
    else:
        from flet_pkg.core.ai.config import AIConfig

        config = AIConfig.load(provider=provider)
        if not config.is_available():
            import os

            env_var = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(
                provider, "GOOGLE_API_KEY"
            )
            current = os.environ.get(env_var, "")
            if not current:
                console.print(
                    f"\n  [warning]No {env_var} found. "
                    f"Set it before running or AI will be skipped.[/warning]"
                )

    return provider
