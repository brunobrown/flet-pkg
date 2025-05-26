import re
import keyword
from pathlib import Path
from typing import Dict, Any, List, Optional


# Métodos irrelevantes para a API pública
UI_METHODS = {
    "build", "create", "initState", "dispose",
    "debugFillProperties", "didChangeDependencies",
    "didUpdateWidget", "setState", "toString", "noSuchMethod",
    "lifecycleInit", "MethodChannel",
    "jsonRepresentation", "convertToJsonString",
    "if", "if_", "that", "and_", "setupDefault",
    "createState", "fromJson", "toJson", "toJsonString", "jsonEncode",
    "instance", "callback", "refuseInCallingOnInvitationReceived"
}

LIFECYCLE_METHODS = {
    "onLoad", "onMount", "onRemove", "onChildrenChanged", "onGameResize",
    "update", "render", "dispose", "renderDebugMode", "renderTree", "updateTree"
}

# Sufixos ou palavras-chave para classes irrelevantes
UI_CLASS_SUFFIXES = (
    "Widget", "Control", "State", "Delegate", "Event", "Data", "Result",
    "Notification", "Manager", "View", "Page", "Overlay", "Config", "Protocol",
    "Private", "Impl", "Guard", "Foreground", "Background", "Internal", "Instance", "Plugins", "Button", "ServiceAPIPrivateImpl"
)

def camel_to_snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def camel_to_lower(name: str) -> str:
    return name[0].lower() + name[1:] if name else name

def should_skip_class(class_name: str, docstring: str = "") -> bool:
    return (
        class_name.startswith('_')
        or class_name.endswith(UI_CLASS_SUFFIXES)
        or any(suffix in class_name for suffix in UI_CLASS_SUFFIXES)
        or "nodoc" in docstring.lower()
        or "internal" in docstring.lower()
    )

def should_skip_method(method_name: str, docstring: str = "") -> bool:
    return (
        method_name in UI_METHODS
        or method_name in LIFECYCLE_METHODS
        or method_name.startswith('_')
        or method_name.startswith('on')
        or "nodoc" in docstring.lower()
        or not method_name.isidentifier()
        or method_name[0].isupper()
    )

def parse_dart_package(package_path: Path, strict: bool = False) -> Dict[str, Any]:
    lib_dir = package_path / "lib"
    if not lib_dir.exists():
        raise FileNotFoundError(f"Directory {lib_dir} does not exist.")

    api_info = {}

    for dart_file in lib_dir.rglob("*.dart"):
        with open(dart_file, "r", encoding="utf-8") as file:
            content = file.read()

            class_matches = re.finditer(
                pattern=r'(?:@[^\n]*\n)*'
                r'class\s+(\w+)'
                r'(?:\s+extends\s+\w+)?'
                r'(?:\s+with\s+[\w\s,]+)?'
                r'(?:\s+implements\s+[\w\s,]+)?'
                r'\s*{',
                string=content
            )

            for match in class_matches:
                class_name = match.group(1)

                doc_match = re.search(r'(///.*?$|/\*\*(.*?)\*/)', content[:match.start()], re.DOTALL | re.MULTILINE)
                class_doc = clean_docstring(doc_match) if doc_match else ""

                if should_skip_class(class_name, class_doc):
                    continue

                class_block = extract_code_block(content[match.end()-1:])
                if not class_block:
                    continue

                methods = []
                seen_method_names = set()

                method_matches = re.finditer(
                    pattern=r'(?:@[^\n]*\n)*'
                    r'(?:static\s+)?'
                    r'(?:Future<.*?>|Future|void|String|bool|int|double|dynamic|Map<.*?>|List<.*?>|\w+)\s+'
                    r'(get\s+|set\s+|)?(\w+)'
                    r'\s*\(([^)]*)\)',
                    string=class_block
                )

                for m in method_matches:
                    is_getter = m.group(1) == 'get'
                    is_setter = m.group(1) == 'set'
                    method_name = m.group(2)

                    method_doc_match = re.search(r'(///.*?$|/\*\*(.*?)\*/)', content[:m.start()], re.DOTALL | re.MULTILINE)
                    method_doc = clean_docstring(method_doc_match) if method_doc_match else ""

                    if (
                        method_name in seen_method_names
                        or should_skip_method(method_name, method_doc)
                    ):
                        continue
                    seen_method_names.add(method_name)

                    if keyword.iskeyword(method_name):
                        method_name += "_"

                    params = []
                    if m.group(3):
                        for param in split_params(m.group(3)):
                            param = re.sub(r'\s*=\s*[^,]+', '', param).strip()
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

                filtered_methods = [
                    m for m in methods if not should_skip_method(m['name'], m['docstring'] or "")
                ]

                if strict and len(filtered_methods) < 2:
                    continue

                if filtered_methods:
                    api_info[class_name] = {
                        "methods": filtered_methods,
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

def clean_docstring(match) -> Optional[str]:
    if not match:
        return None
    doc = match.group(1) or match.group(2) or ''
    doc = re.sub(r'///+', '', doc)
    doc = re.sub(r'/\*\*|\*/', '', doc)
    doc = doc.strip().replace('\n', ' ').replace('  ', ' ')
    return doc


if __name__ == "__main__":
    from pprint import pprint
    api = parse_dart_package(Path("package/flutter"))
    pprint(api)