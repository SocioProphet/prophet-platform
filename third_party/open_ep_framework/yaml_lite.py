from __future__ import annotations


def _strip_inline_comment(line: str) -> str:
    in_quote = False
    quote_char = ""
    for idx, char in enumerate(line):
        if char in {"'", '"'}:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
        if char == "#" and not in_quote:
            return line[:idx].rstrip()
    return line.rstrip()


def _scalar(value: str):
    value = value.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if value in {"null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def parse_yaml_lite(text: str) -> dict:
    """Parse the restricted YAML subset used by TRUST_SURFACE.yaml.

    Supported constructs:
    - nested mappings via indentation
    - arrays using '- item'
    - block strings using 'key: >'
    - booleans and plain/string scalars

    This is intentionally not a general YAML parser. It exists so this repo can
    validate its trust-surface fixture without adding a runtime dependency.
    """
    raw_lines = text.splitlines()
    root: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, root)]
    pending_key: dict[int, str] = {}
    idx = 0

    while idx < len(raw_lines):
        raw = raw_lines[idx]
        if not raw.strip() or raw.lstrip().startswith("#"):
            idx += 1
            continue

        line = _strip_inline_comment(raw)
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"list item without list parent: {raw}")
            parent.append(_scalar(stripped[2:]))
            idx += 1
            continue

        if ":" not in stripped:
            raise ValueError(f"unsupported YAML line: {raw}")

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"mapping entry without mapping parent: {raw}")

        if value == ">":
            block_lines: list[str] = []
            idx += 1
            while idx < len(raw_lines):
                block_raw = raw_lines[idx]
                if not block_raw.strip():
                    block_lines.append("")
                    idx += 1
                    continue
                block_indent = len(block_raw) - len(block_raw.lstrip(" "))
                if block_indent <= indent:
                    break
                block_lines.append(block_raw.strip())
                idx += 1
            parent[key] = "\n".join(block_lines).strip()
            continue

        if value:
            parent[key] = _scalar(value)
            idx += 1
            continue

        # Determine whether the upcoming nested value is a list or mapping.
        next_idx = idx + 1
        while next_idx < len(raw_lines) and (not raw_lines[next_idx].strip() or raw_lines[next_idx].lstrip().startswith("#")):
            next_idx += 1
        if next_idx < len(raw_lines) and raw_lines[next_idx].strip().startswith("- "):
            child: dict | list = []
        else:
            child = {}
        parent[key] = child
        stack.append((indent, child))
        pending_key[indent] = key
        idx += 1

    return root
