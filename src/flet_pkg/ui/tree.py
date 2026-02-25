from pathlib import Path

from rich.panel import Panel
from rich.tree import Tree

from flet_pkg.ui.console import console


def build_tree(root_path: Path, label: str | None = None) -> Tree:
    tree = Tree(f"[highlight]{label or root_path.name}/[/highlight]")
    _walk(root_path, tree)
    return tree


def _walk(path: Path, tree: Tree) -> None:
    entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            branch = tree.add(f"[info]{entry.name}/[/info]")
            _walk(entry, branch)
        else:
            tree.add(f"[muted]{entry.name}[/muted]")


def print_tree(root_path: Path, title: str = "Generated Project") -> None:
    tree = build_tree(root_path)
    console.print()
    console.print(Panel(tree, title=f"[success]{title}[/success]", border_style="green"))
