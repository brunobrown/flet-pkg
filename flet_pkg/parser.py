# import re
# from pathlib import Path
# from pprint import pprint
# from typing import Dict, List, Optional, Any, LiteralString
#
#
# def parse_dart_package(package_path: Path) -> dict[str | Any, dict[
#     str, LiteralString | None | list[dict[str, str | bool | list[str] | LiteralString | None | Any]] | str]]:
#     """
#     Parses Dart files to extract public classes and methods that could be exposed in the Python wrapper.
#     Improved version with better parsing and more complete metadata extraction.
#
#     Args:
#         package_path: Path to the extracted Flutter package
#
#     Returns:
#         Dictionary with class names as keys and list of methods (with full signatures) as values
#         Example:
#         {
#             "UrlLauncher": [
#                 {
#                     "name": "launch",
#                     "return_type": "Future<bool>",
#                     "params": ["String url", "bool? useSafariVC"],
#                     "docstring": "Opens the specified URL..."
#                 }
#             ]
#         }
#     """
#     lib_dir = package_path / "lib"
#     if not lib_dir.exists():
#         raise FileNotFoundError(f"lib/ directory not found in {package_path}")
#
#     api_info = {}
#
#     for dart_file in lib_dir.rglob("*.dart"):
#         with open(dart_file, "r", encoding="utf-8") as file:
#             content = file.read()
#
#             # Improved class detection with inheritance and mixins
#             class_matches = re.finditer(
#                 r'(?:@[^\n]+\n)*'  # annotations
#                 r'class\s+(\w+)'    # class name
#                 r'(?:\s+extends\s+\w+)?'  # inheritance
#                 r'(?:\s+with\s+[\w\s,]+)?'  # mixins
#                 r'(?:\s+implements\s+[\w\s,]+)?'  # interfaces
#                 r'\s*{',
#                 content
#             )
#
#             for match in class_matches:
#                 class_name = match.group(1)
#                 if class_name.startswith('_'):
#                     continue
#
#                 # Extract class documentation
#                 doc_match = re.search(r'/\*\*(.*?)\*/', content[:match.start()], re.DOTALL)
#                 class_doc = doc_match.group(1).strip() if doc_match else None
#
#                 # Extract class block with nested braces handling
#                 class_block = extract_code_block(content[match.end()-1:])
#                 if not class_block:
#                     continue
#
#                 methods = []
#
#                 # Method parsing (including getters/setters)
#                 method_matches = re.finditer(
#                     r'(?:@[^\n]+\n)*'  # annotations
#                     r'(?:static\s+)?'  # static modifier
#                     r'(?:Future<.*?>|Future|void|String|bool|int|double|dynamic|\w+)\s+'  # return type
#                     r'(get\s+|set\s+|)(\w+)'  # method name (or getter/setter)
#                     r'\s*\(([^)]*)\)'  # parameters
#                     r'(?:\s*=>\s*[^;]+;)?',  # arrow function
#                     class_block
#                 )
#
#                 for m in method_matches:
#                     is_getter = bool(m.group(1).strip() == 'get')
#                     is_setter = bool(m.group(1).strip() == 'set')
#                     method_name = m.group(2)
#
#                     if method_name.startswith('_'):
#                         continue
#
#                     # Extract method documentation
#                     method_doc_match = re.search(r'/\*\*(.*?)\*/', content[:m.start()], re.DOTALL)
#                     method_doc = method_doc_match.group(1).strip() if method_doc_match else None
#
#                     # Process parameters
#                     params = []
#                     if m.group(3):  # has parameters
#                         for param in split_params(m.group(3)):
#                             param = param.strip()
#                             if param:
#                                 params.append(param)
#
#                     methods.append({
#                         "name": method_name,
#                         "return_type": m.group(1) if not is_setter else "void",
#                         "params": params,
#                         "docstring": method_doc,
#                         "is_getter": is_getter,
#                         "is_setter": is_setter
#                     })
#
#                 if methods:
#                     api_info[class_name] = {
#                         "methods": methods,
#                         "docstring": class_doc,
#                         "source_file": str(dart_file.relative_to(lib_dir))
#                     }
#
#     return api_info
#
#
# def extract_code_block(content: str) -> Optional[str]:
#     """Helper to extract code block with proper brace matching."""
#     brace_count = 1
#     end_pos = 1
#
#     for i, c in enumerate(content[1:], 1):
#         if c == '{':
#             brace_count += 1
#         elif c == '}':
#             brace_count -= 1
#             if brace_count == 0:
#                 end_pos = i
#                 break
#
#     return content[1:end_pos] if brace_count == 0 else None
#
#
# def split_params(param_str: str) -> List[str]:
#     """Splits parameter list handling complex types and default values."""
#     params = []
#     current = []
#     paren_level = 0
#
#     for char in param_str:
#         if char == ',' and paren_level == 0:
#             params.append(''.join(current).strip())
#             current = []
#         else:
#             if char == '(':
#                 paren_level += 1
#             elif char == ')':
#                 paren_level -= 1
#             current.append(char)
#
#     if current:
#         params.append(''.join(current).strip())
#
#     return params
#
#
# if __name__ == "__main__":
#     api = parse_dart_package(Path("package/flutter"))
#     pprint(api)


import re
import keyword
from pathlib import Path
from pprint import pprint
from typing import Dict, List, Optional, Any, LiteralString


def parse_dart_package(package_path: Path) -> dict[str | Any, dict[
    str, LiteralString | None | list[dict[str, str | bool | list[str] | LiteralString | None | Any]] | str]]:
    """
    Parses Dart files to extract public classes and methods that could be exposed in the Python wrapper.
    Improved version with better parsing and more complete metadata extraction.

    Args:
        package_path: Path to the extracted Flutter package

    Returns:
        Dictionary with class names as keys and method info (docstrings, params, etc.)
    """
    lib_dir = package_path / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)

    api_info = {}

    for dart_file in lib_dir.rglob("*.dart"):
        with open(dart_file, "r", encoding="utf-8") as file:
            content = file.read()

            class_matches = re.finditer(
                r'(?:@[^\n]+\n)*'             # optional annotations
                r'class\s+(\w+)'                     # class name
                r'(?:\s+extends\s+\w+)?'             # optional extends
                r'(?:\s+with\s+[\w\s,]+)?'           # optional mixins
                r'(?:\s+implements\s+[\w\s,]+)?'     # optional interfaces
                r'\s*{',
                content
            )

            for match in class_matches:
                class_name = match.group(1)
                if class_name.startswith('_'):
                    continue

                doc_match = re.search(r'/\*\*(.*?)\*/', content[:match.start()], re.DOTALL)
                class_doc = doc_match.group(1).strip() if doc_match else None

                class_block = extract_code_block(content[match.end()-1:])
                if not class_block:
                    continue

                methods = []
                seen_method_names = set()
                method_matches = re.finditer(
                    r'(?:@[^\n]+\n)*'                         # optional annotations
                    r'(?:static\s+)?'                                # optional static
                    r'(?:Future<.*?>|Future|void|String|bool|int|double|dynamic|\w+)\s+'
                    r'(get\s+|set\s+|)(\w+)'                         # method name
                    r'\s*\(([^)]*)\)',                               # parameters
                    class_block
                )

                for m in method_matches:
                    is_getter = m.group(1).strip() == 'get'
                    is_setter = m.group(1).strip() == 'set'
                    method_name = m.group(2)

                    if method_name in seen_method_names:
                        continue
                    seen_method_names.add(method_name)

                    if method_name.startswith('_') or method_name == class_name or not method_name.isidentifier():
                        continue
                    if keyword.iskeyword(method_name):
                        method_name += "_"

                    method_doc_match = re.search(r'/\*\*(.*?)\*/', content[:m.start()], re.DOTALL)
                    method_doc = method_doc_match.group(1).strip() if method_doc_match else None

                    params = []
                    if m.group(3):
                        for param in split_params(m.group(3)):
                            param = param.strip()
                            param = re.sub(r'\s*=\s*[^,]+', '', param)
                            param = param.replace('??', '').replace('||', '').strip()
                            if param and param.split(' ')[-1].isidentifier():
                                params.append(param)

                    methods.append({
                        "name": method_name,
                        "return_type": m.group(1) if not is_setter else "void",
                        "params": params,
                        "docstring": method_doc,
                        "is_getter": is_getter,
                        "is_setter": is_setter
                    })

                if methods:
                    api_info[class_name] = {
                        "methods": methods,
                        "docstring": class_doc,
                        "source_file": str(dart_file.relative_to(lib_dir))
                    }

    return api_info


def extract_code_block(content: str) -> Optional[str]:
    brace_count = 1
    end_pos = 1
    for i, c in enumerate(content[1:], 1):
        if c == '{':
            brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0:
                end_pos = i
                break
    return content[1:end_pos] if brace_count == 0 else None


def split_params(param_str: str) -> List[str]:
    params = []
    current = []
    paren_level = 0
    for char in param_str:
        if char == ',' and paren_level == 0:
            params.append(''.join(current).strip())
            current = []
        else:
            if char == '(':
                paren_level += 1
            elif char == ')':
                paren_level -= 1
            current.append(char)
    if current:
        params.append(''.join(current).strip())
    return params


if __name__ == "__main__":
    api = parse_dart_package(Path("package/flutter"))
    pprint(api)

