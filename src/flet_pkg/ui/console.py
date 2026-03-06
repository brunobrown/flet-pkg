from rich.console import Console
from rich.theme import Theme

theme = Theme(
    {
        "success": "bold green",
        "error": "bold red",
        "info": "bold cyan",
        "highlight": "bold magenta",
        "muted": "dim",
        "warning": "bold yellow",
    }
)

console = Console(theme=theme)
