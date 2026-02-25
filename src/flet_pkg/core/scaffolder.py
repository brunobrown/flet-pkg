import os
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from flet_pkg.ui.console import console

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")


class Scaffolder:
    def __init__(self, template_name: str, context: dict, output_dir: Path | None = None):
        self.template_path = TEMPLATE_DIR / template_name
        if not self.template_path.is_dir():
            raise FileNotFoundError(f"Template '{template_name}' not found at {self.template_path}")

        self.context = context
        self.output_dir = output_dir or Path.cwd()

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_path)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )

    def _resolve_name(self, name: str) -> str:
        return VARIABLE_RE.sub(lambda m: str(self.context.get(m.group(1), m.group(0))), name)

    def generate(self) -> Path:
        project_name = self.context.get("project_name", "output")
        project_dir = self.output_dir / project_name
        if project_dir.exists():
            raise FileExistsError(f"Directory already exists: {project_dir}")

        with console.status("[info]Generating project files...[/info]", spinner="dots"):
            self._walk_and_render(self.output_dir)

        return project_dir

    def _walk_and_render(self, project_dir: Path) -> None:
        for dirpath, dirnames, filenames in os.walk(self.template_path):
            rel_dir = Path(dirpath).relative_to(self.template_path)
            resolved_dir = (
                Path(*[self._resolve_name(p) for p in rel_dir.parts]) if rel_dir.parts else Path()
            )
            target_dir = project_dir / resolved_dir
            target_dir.mkdir(parents=True, exist_ok=True)

            # Skip hidden directories
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            for filename in filenames:
                if filename == "template.yaml":
                    continue

                src_file = Path(dirpath) / filename
                resolved_name = self._resolve_name(filename)

                if resolved_name.endswith(".jinja"):
                    resolved_name = resolved_name[: -len(".jinja")]
                    rel_template = str(Path(dirpath).relative_to(self.template_path) / filename)
                    template = self.env.get_template(rel_template.replace(os.sep, "/"))
                    content = template.render(self.context)
                    (target_dir / resolved_name).write_text(content, encoding="utf-8")
                else:
                    shutil.copy2(src_file, target_dir / resolved_name)
