import typer

from flet_pkg import __app_name__, __version__
from flet_pkg.commands.create import create

app = typer.Typer(
    name=__app_name__,
    help="CLI tool to scaffold Flet extension packages.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

app.command()(create)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    pass
