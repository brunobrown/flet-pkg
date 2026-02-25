from rich.panel import Panel

from flet_pkg.ui.console import console


def header_panel(title: str, subtitle: str = "") -> None:
    content = f"[info]{subtitle}[/info]" if subtitle else ""
    console.print(
        Panel(content, title=f"[highlight]{title}[/highlight]", border_style="bright_blue")
    )


def success_panel(title: str, content: str) -> None:
    console.print(Panel(content, title=f"[success]{title}[/success]", border_style="green"))


def error_panel(title: str, content: str) -> None:
    console.print(Panel(content, title=f"[error]{title}[/error]", border_style="red"))


def info_panel(title: str, content: str) -> None:
    console.print(Panel(content, title=f"[info]{title}[/info]", border_style="cyan"))
