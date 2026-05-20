#!/usr/bin/env python3
"""Heuristic C++ coding-convention checker for pull requests.

The source convention file contains both strict rules and human-review
guidelines. This script enforces the rules that can be checked reliably enough
without compiling the project or requiring a full C++ parser.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
HEADER_EXTENSIONS = {".h", ".hh", ".hpp", ".hxx"}
IGNORED_DIRS = {".git", ".github", "build", "cmake-build-debug", "cmake-build-release"}

SNAKE_CASE_FILE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*\.(?:c|cc|cpp|cxx|h|hh|hpp|hxx)$")
UPPER_CASE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")
PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
CAMEL_CASE_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")
MEMBER_RE = re.compile(r"^(?:m|s)_[a-z][A-Za-z0-9]*$")
BOOL_PREFIX_RE = re.compile(r"^(?:is|has|can|should)[A-Z][A-Za-z0-9]*$")

CLASS_RE = re.compile(r"\b(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)")
ENUM_RE = re.compile(r"\benum\s+(?!class\b)([A-Za-z_][A-Za-z0-9_]*)?")
FUNCTION_RE = re.compile(
    r"^\s*(?:virtual\s+|static\s+|inline\s+|constexpr\s+|consteval\s+|explicit\s+)*"
    r"(?:[\w:<>,~*&\s]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:final\s*)?(?:\{|;|\{\s*\})?\s*$"
)
CONST_RE = re.compile(r"\b(?:const|constexpr)\s+[\w:<>,~*&\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\b")
BOOL_RE = re.compile(r"\bbool\s+([A-Za-z_][A-Za-z0-9_]*)\b")
MACRO_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b")
TYPEDEF_RE = re.compile(r"\btypedef\b")
USING_NAMESPACE_STD_RE = re.compile(r"\busing\s+namespace\s+std\s*;")
NULL_RE = re.compile(r"\bNULL\b")
IF_FOR_WHILE_WITHOUT_BRACE_RE = re.compile(r"^\s*(?:if|for|while)\s*\(.+\)\s*(?!\{|;)\S+")
MAGIC_NUMBER_RE = re.compile(r"(?<![\w.])(?!(?:0|1|2)\b)\d+(?:\.\d+)?(?:f)?\b")


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str


def iter_cpp_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        for name in names:
            path = Path(current_root) / name
            if path.suffix.lower() in CPP_EXTENSIONS:
                files.append(path)
    return sorted(files)


def strip_line_comment(line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string and line[index : index + 2] == "//":
            return line[:index]
    return line


def is_comment_or_preprocessor(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("#")


def add(violations: list[Violation], path: Path, line_number: int, message: str) -> None:
    violations.append(Violation(path=path, line=line_number, message=message))


def check_header_guard(path: Path, lines: list[str], violations: list[Violation]) -> None:
    if path.suffix.lower() not in HEADER_EXTENSIONS:
        return

    meaningful = [line.strip() for line in lines if line.strip() and not line.strip().startswith("//")]
    has_pragma_once = any(line == "#pragma once" for line in meaningful[:10])
    has_header_guard = any(line.startswith("#ifndef ") for line in meaningful[:5]) and any(
        line.startswith("#define ") for line in meaningful[:8]
    )
    if not has_pragma_once and not has_header_guard:
        add(violations, path, 1, "Header files must use #pragma once or an include guard.")


def check_switch_default(path: Path, lines: list[str], violations: list[Violation]) -> None:
    in_switch = False
    brace_depth = 0
    switch_start = 0
    has_default = False

    for line_number, line in enumerate(lines, start=1):
        code = strip_line_comment(line)
        if not in_switch and re.search(r"\bswitch\s*\(", code):
            in_switch = True
            switch_start = line_number
            has_default = False
            brace_depth = code.count("{") - code.count("}")
            continue

        if in_switch:
            if re.search(r"^\s*default\s*:", code):
                has_default = True
            brace_depth += code.count("{") - code.count("}")
            if brace_depth <= 0 and "}" in code:
                if not has_default:
                    add(violations, path, switch_start, "Switch statements must have a default case.")
                in_switch = False


def check_file(path: Path, root: Path) -> list[Violation]:
    violations: list[Violation] = []
    relative_path = path.relative_to(root)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if not SNAKE_CASE_FILE_RE.match(path.name):
        add(violations, relative_path, 1, "C++ file names must use snake_case.")

    check_header_guard(relative_path, lines, violations)
    check_switch_default(relative_path, lines, violations)

    for line_number, raw_line in enumerate(lines, start=1):
        code = strip_line_comment(raw_line)
        stripped = code.strip()

        if "\t" in raw_line:
            add(violations, relative_path, line_number, "Use 4 spaces for indentation; tabs are not allowed.")

        if "NULL" in code and NULL_RE.search(code):
            add(violations, relative_path, line_number, "Use nullptr instead of NULL.")

        if TYPEDEF_RE.search(code):
            add(violations, relative_path, line_number, "Use using instead of typedef.")

        if USING_NAMESPACE_STD_RE.search(code):
            add(violations, relative_path, line_number, "Avoid using namespace std.")

        macro_match = MACRO_RE.search(code)
        if macro_match and not UPPER_CASE_RE.match(macro_match.group(1)):
            add(violations, relative_path, line_number, "Macro names must use UPPER_CASE.")

        enum_match = ENUM_RE.search(code)
        if enum_match:
            add(violations, relative_path, line_number, "Use enum class instead of plain enum.")

        class_match = CLASS_RE.search(code)
        if class_match and not PASCAL_CASE_RE.match(class_match.group(1)):
            add(violations, relative_path, line_number, "Class and struct names must use PascalCase.")

        for const_match in CONST_RE.finditer(code):
            const_name = const_match.group(1)
            next_char_match = re.search(r"\S", code[const_match.end() :])
            next_char = next_char_match.group(0) if next_char_match else ""
            if next_char in {",", ")"}:
                continue
            if const_name not in {"auto"} and not UPPER_CASE_RE.match(const_name):
                add(violations, relative_path, line_number, "Constants must use UPPER_CASE.")

        for bool_name in BOOL_RE.findall(code):
            if not BOOL_PREFIX_RE.match(bool_name):
                add(violations, relative_path, line_number, "Boolean variables must start with is, has, can, or should.")

        function_match = FUNCTION_RE.match(code)
        if function_match:
            name = function_match.group(1)
            if name not in {"main"} and "::" not in name and not name.startswith("operator") and not CAMEL_CASE_RE.match(name):
                add(violations, relative_path, line_number, "Function names must use camelCase.")

        if IF_FOR_WHILE_WITHOUT_BRACE_RE.match(code):
            add(violations, relative_path, line_number, "Always use braces for if, for, and while statements.")

        if not is_comment_or_preprocessor(code):
            statement_count = stripped.count(";")
            if statement_count > 1:
                add(violations, relative_path, line_number, "Use one statement per line.")

            if MAGIC_NUMBER_RE.search(code) and not re.search(r"\b(?:const|constexpr|case)\b", code):
                add(violations, relative_path, line_number, "Avoid magic numbers; use named constants.")

        member_match = re.search(r"^\s*(?:static\s+)?(?:[\w:<>,~*&]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*(?:[=;{])", code)
        if member_match and re.match(r"\s*(?:private|protected|public)\s*:", code) is None:
            name = member_match.group(1)
            if (name.startswith("m_") or name.startswith("s_")) and not MEMBER_RE.match(name):
                add(violations, relative_path, line_number, "Member variables should use m_ or s_ followed by camelCase.")

    return violations


def main() -> int:
    root = Path.cwd()
    files = iter_cpp_files(root)
    if not files:
        print("No C++ files found. Convention check skipped.")
        return 0

    violations: list[Violation] = []
    for path in files:
        violations.extend(check_file(path, root))

    if violations:
        print("C++ coding convention violations found:\n")
        for violation in violations:
            print(f"{violation.path}:{violation.line}: {violation.message}")
        print(f"\nTotal violations: {len(violations)}")
        return 1

    print(f"Checked {len(files)} C++ file(s). No convention violations found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
