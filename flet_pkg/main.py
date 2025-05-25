import re
from pathlib import Path
from pprint import pprint
from typing import Dict, Any
from flet_pkg.downloader import download_package_from_pubdev
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


def generate_python_flet_wrapper(package_name: str, api_info: Dict[str, Any], output_dir: Path) -> None:
    """
    Generates Python wrapper code from parsed Dart API info using Jinja2 templates.
    Enhanced version with better error handling and file naming.

    Args:
        package_name: Name of the package (used for naming and imports)
        api_info: Dictionary with parsed class and method info from Dart source
        output_dir: Path where the wrapper files will be saved

    Raises:
        ValueError: If api_info has invalid structure
        FileNotFoundError: If template directory is missing
        TemplateNotFound: If template file is missing
    """

    # Validate api_info structure
    if not isinstance(api_info, dict) or not all(
            isinstance(cls_data, dict) and 'methods' in cls_data
            for cls_data in api_info.values()
    ):
        raise ValueError("Invalid api_info structure")

    # Setup templates
    template_dir = Path(__file__).parent / "templates"
    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found at {template_dir}")

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        keep_trailing_newline=True,
        extensions=["jinja2.ext.do"]
    )

    try:
        template = env.get_template("wrapper_python_flet.py.j2")
    except TemplateNotFound:
        raise TemplateNotFound(
            f"Wrapper template not found in {template_dir}. "
            "Expected file: wrapper_python_flet.py.j2"
        )

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate wrapper for each class
    for class_name, class_data in api_info.items():
        # Sanitize filename
        safe_class_name = re.sub(r'[^a-zA-Z0-9_]', '_', class_name)
        filename = f"{package_name.lower()}_{safe_class_name.lower()}.py"
        output_path = output_dir / filename

        # Add snake_case name to each method
        for method in class_data.get("methods", []):
            method["py_name"] = _camel_to_snake(method["name"])

        try:
            wrapper_code = template.render(
                package_name=package_name,
                class_name=class_name,
                safe_class_name=safe_class_name,
                class_doc=class_data.get("docstring", ""),
                methods=class_data.get("methods", []),
                source_file=class_data.get("source_file", "")
            )

            # Write to file with atomic write pattern
            temp_path = output_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(wrapper_code)
            temp_path.replace(output_path)

            print(f"✅ Generated: {output_path}")

        except Exception as e:
            print(f"❌ Failed to generate wrapper for {class_name}: {str(e)}")
            continue


def generate_dart_flutter_wrapper(api_info: Dict[str, Any], package_name: str, widget_class_name: str, output_dir: Path) -> None:
    template_dir = Path(__file__).parent / "templates"
    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found at {template_dir}")

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        keep_trailing_newline=True
    )

    try:
        template = env.get_template("wrapper_dart_flutter.dart.j2")
    except TemplateNotFound:
        raise TemplateNotFound("Template wrapper_dart_flutter.dart.j2 not found")

    all_methods = set()
    for class_data in api_info.values():
        for method in class_data.get("methods", []):
            all_methods.add(method["name"])

    content = template.render(methods=sorted(all_methods), package_name=package_name, widget_class_name=widget_class_name)

    main_dart_path = output_dir / "lib" / f"flet_{package_name}.dart"
    main_dart_path.parent.mkdir(parents=True, exist_ok=True)
    with open(main_dart_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Generated: {main_dart_path}")


def _camel_to_snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


if __name__ == "__main__":
    from flet_pkg.parser import parse_dart_package

    package_name = "onesignal_flutter"
    widget_class_name = "OnesignalFlutter"
    python_output_dir = Path("python_wrappers")
    dart_output_dir = Path("dart_wrappers")
    dart_package_path = Path("package/flutter")

    # First download the package
    download_package_from_pubdev(package_name, dart_package_path)

    # Then parse the Dart package
    api_info = parse_dart_package(dart_package_path)
    pprint(api_info)

    # Then generate python_wrappers and dart_wrappers
    generate_python_flet_wrapper(package_name, api_info, python_output_dir)

    # Then generate main.dart
    generate_dart_flutter_wrapper(api_info, package_name, widget_class_name, dart_output_dir)
