"""Typer CLI application for flet-pkg.

Registers the ``create`` command and provides a ``--version`` callback.
"""

import typer

from flet_pkg import __app_name__, __version__
from flet_pkg.commands.create import create

app = typer.Typer(
    name=__app_name__,
    help=(
        "[bold]Scaffold Flet extension packages from Flutter packages.[/bold]\n\n"
        "flet-pkg downloads a Flutter package from [link=https://pub.dev]pub.dev[/link], "
        "parses its Dart API, and generates a complete Flet extension with "
        "Python controls, type mappings, event handlers, and Dart bridge code.\n\n"
        "[dim]Extension types:[/dim]\n\n"
        "  [cyan]service[/cyan]      Non-visual extensions "
        "(e.g. shared_preferences, geolocator)\n"
        "  [cyan]ui_control[/cyan]   Visual widget extensions "
        "(e.g. shimmer, flutter_rating_bar)\n\n"
        "[dim]AI refinement (optional):[/dim]\n\n"
        "  Uses the Architect/Editor pattern to analyze coverage gaps and\n"
        "  auto-improve the generated code with LLM-powered edits.\n\n"
        "  [green]$[/green] uv add flet-pkg\\[ai]            [dim]# install AI deps[/dim]\n"
        "  [green]$[/green] ollama pull qwen2.5-coder:14b     [dim]# free, local[/dim]\n"
        "  [green]$[/green] flet-pkg create --ai-refine   [dim]# uses Ollama by default[/dim]\n\n"
        "  Providers: [cyan]ollama[/cyan] (default, free), [cyan]anthropic[/cyan], "
        "[cyan]openai[/cyan], [cyan]google[/cyan]\n\n"
        "[dim]Quick start:[/dim]\n\n"
        "  [green]$[/green] flet-pkg create\n"
        "  [green]$[/green] flet-pkg create -t service -f shared_preferences\n"
        "  [green]$[/green] flet-pkg create -t ui_control -f shimmer --ai-refine"
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
    epilog=(
        "[dim]Docs  :[/dim] https://brunobrown.github.io/flet-pkg\n\n"
        "[dim]Issues:[/dim] https://github.com/brunobrown/flet-pkg/issues"
    ),
)

app.command()(create)


def _version_callback(value: bool) -> None:
    """Print the version string and exit when ``--version`` is passed."""
    if value:
        typer.echo(f"{__app_name__} {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Root callback invoked before any sub-command."""
    pass
