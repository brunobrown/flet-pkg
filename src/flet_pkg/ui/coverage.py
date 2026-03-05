"""Coverage score display and Rich Table breakdown."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from flet_pkg.ui.console import console

if TYPE_CHECKING:
    from flet_pkg.core.ai.models import GapReport


def _progress_bar(pct: float, width: int = 10) -> str:
    """Return a block-char progress bar like ``████████░░``."""
    filled = round(pct / 100 * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _pct_color(pct: float) -> str:
    if pct >= 90:
        return "green"
    if pct >= 70:
        return "yellow"
    return "red"


def print_coverage_score(
    pct: float,
    total_generated: int,
    total_dart_api: int,
    ai_pct: float | None = None,
) -> None:
    """Always-visible one-line coverage score, with optional AI comparison."""
    if total_dart_api == 0:
        console.print("  [info]Coverage: N/A (no Dart API found)[/info]")
        return

    color = _pct_color(pct)

    if ai_pct is not None and ai_pct > pct:
        ai_color = _pct_color(ai_pct)
        delta = ai_pct - pct
        console.print(
            f"  [{color}]Coverage: {pct:.1f}%[/{color}] "
            f"[dim]->[/dim] [{ai_color}]{ai_pct:.1f}%[/{ai_color}] "
            f"[dim](+{delta:.1f}% with AI)[/dim] "
            f"({total_generated}/{total_dart_api} features mapped)"
        )
    else:
        console.print(
            f"  [{color}]Coverage: {pct:.1f}%[/{color}] "
            f"({total_generated}/{total_dart_api} features mapped)"
        )


def print_coverage_table(report: GapReport) -> None:
    """Verbose Rich Table showing per-category breakdown."""
    if not report.category_counts:
        return

    table = Table(
        title="Coverage Breakdown",
        show_header=True,
        header_style="bold",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("Category", style="cyan", min_width=12)
    table.add_column("Dart API", justify="right", min_width=8)
    table.add_column("Mapped", justify="right", min_width=7)
    table.add_column("Coverage", min_width=16)

    for cat, (dart_api, mapped) in report.category_counts.items():
        pct = (mapped / dart_api * 100) if dart_api > 0 else 100.0
        bar = _progress_bar(pct)
        table.add_row(cat, str(dart_api), str(mapped), f"{bar} {pct:.0f}%")

    # Total row
    table.add_section()
    total_pct = report.coverage_pct
    bar = _progress_bar(total_pct)
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{report.total_dart_api}[/bold]",
        f"[bold]{report.total_generated}[/bold]",
        f"[bold]{bar} {total_pct:.0f}%[/bold]",
    )

    console.print()
    console.print(table)
