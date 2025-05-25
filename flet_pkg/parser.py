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
    "jsonRepresentation", "convertToJsonString"
}

# Sufixos de classes irrelevantes
UI_CLASS_SUFFIXES = (
    "Widget", "Control", "State", "Delegate",
    "Event", "Data", "Result", "Notification"
)

def camel_to_snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def camel_to_lower(name: str) -> str:
    return name[0].lower() + name[1:] if name else name

def should_skip_class(class_name: str) -> bool:
    return (
        class_name.startswith('_')
        or class_name.endswith(UI_CLASS_SUFFIXES)
    )

def should_skip_method(method_name: str) -> bool:
    return (
        method_name in UI_METHODS
        or method_name.startswith('_')
        or not method_name.isidentifier()
        or method_name[0].isupper()  # provável construtor ou enum
    )

def parse_dart_package(package_path: Path) -> Dict[str, Any]:
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
                if should_skip_class(class_name):
                    continue

                doc_match = re.search(r'/\*\*(.*?)\*/', content[:match.start()], re.DOTALL)
                class_doc = doc_match.group(1).strip() if doc_match else None

                class_block = extract_code_block(content[match.end()-1:])
                if not class_block:
                    continue

                methods = []
                seen_method_names = set()

                method_matches = re.finditer(
                    pattern=r'(?:@[^\n]*\n)*'  # captura anotações acima do método
                    r'(?:static\s+)?'  # captura static opcional
                    r'(?:Future<.*?>|Future|void|String|bool|int|double|dynamic|\w+)\s+'  # tipo de retorno
                    r'(get\s+|set\s+|)?(\w+)'  # getter/setter opcional + nome
                    r'\s*\(([^)]*)\)',  # parâmetros
                    string=class_block
                )

                for m in method_matches:
                    is_getter = m.group(1) == 'get'
                    is_setter = m.group(1) == 'set'
                    method_name = m.group(2)

                    if (
                        method_name in seen_method_names
                        or should_skip_method(method_name)
                    ):
                        continue
                    seen_method_names.add(method_name)

                    if keyword.iskeyword(method_name):
                        method_name += "_"

                    method_doc_match = re.search(r'/\*\*(.*?)\*/', content[:m.start()], re.DOTALL)
                    method_doc = method_doc_match.group(1).strip() if method_doc_match else None

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
                    m for m in methods if not should_skip_method(m['name'])
                ]

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


if __name__ == "__main__":
    from pprint import pprint
    api = parse_dart_package(Path("package/flutter"))
    pprint(api)