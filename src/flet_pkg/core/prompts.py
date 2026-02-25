from typing import Callable

from rich.prompt import Prompt

from flet_pkg.ui.console import console


def ask(
    prompt: str,
    default: str = "",
    validator: Callable[[str], str | None] | None = None,
) -> str:
    while True:
        value = Prompt.ask(f"[info]?[/info] {prompt}", default=default or None, console=console)
        if value is None:
            value = ""
        value = value.strip()
        if validator:
            error = validator(value)
            if error:
                console.print(f"  [error]{error}[/error]")
                continue
        if not value and not default:
            console.print("  [error]This field is required.[/error]")
            continue
        return value


def ask_choice(prompt: str, choices: list[tuple[int, str]]) -> int:
    console.print(f"\n[info]?[/info] {prompt}")
    for num, label in choices:
        console.print(f"  [highlight]{num}[/highlight] - {label}")
    while True:
        value = Prompt.ask("  Choice", console=console)
        try:
            choice = int(value)
            valid = [c[0] for c in choices]
            if choice in valid:
                return choice
        except ValueError:
            pass
        console.print(
            f"  [error]Please enter one of: {', '.join(str(c[0]) for c in choices)}[/error]"
        )
