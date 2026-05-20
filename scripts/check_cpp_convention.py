#!/usr/bin/env python3
"""Heuristic C++ coding-convention checker for pull requests.

The source convention file contains both strict rules and human-review
guidelines. This script enforces the rules that can be checked reliably enough
without compiling the project or requiring a full C++ parser.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher
from dataclasses import dataclass
from pathlib import Path


CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx"}
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
MAGIC_NUMBER_RE = re.compile(r"(?<![\w.])(?!(?:0|1|2)\b)\d+(?:\.\d+)?(?:f)?\b")
POINTER_STYLE_RE = re.compile(
    r"(?:\b[A-Za-z_][\w:<>]*\s+\*+\s*[A-Za-z_][\w]*|\b[A-Za-z_][\w:<>]*\s*\*+\s+[A-Za-z_][\w]*|\([A-Za-z_][\w:<>]*\s+\*\))"
)


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


def normalize_cpp_tokens(lines: list[str]) -> str:
    return re.sub(r"\s+", "", "".join(strip_line_comment(line) for line in lines))


def is_short_inline_function_style_difference(original: list[str], formatted: list[str]) -> bool:
    original_non_empty = [line for line in original if line.strip()]
    formatted_non_empty = [line for line in formatted if line.strip()]
    if not original_non_empty or not formatted_non_empty:
        return False

    one_side_is_single_line = len(original_non_empty) == 1 or len(formatted_non_empty) == 1
    other_side_is_multi_line = len(original_non_empty) > 1 or len(formatted_non_empty) > 1
    if not one_side_is_single_line or not other_side_is_multi_line:
        return False

    original_text = "\n".join(original_non_empty)
    formatted_text = "\n".join(formatted_non_empty)
    if "{" not in original_text or "}" not in original_text or "{" not in formatted_text or "}" not in formatted_text:
        return False

    if original_text.count("{") != formatted_text.count("{") or original_text.count("}") != formatted_text.count("}"):
        return False

    original_indent = re.match(r"\s*", original_non_empty[0]).group(0)
    formatted_indent = re.match(r"\s*", formatted_non_empty[0]).group(0)
    if original_indent != formatted_indent:
        return False

    return normalize_cpp_tokens(original_non_empty) == normalize_cpp_tokens(formatted_non_empty)


def is_pointer_style_difference(original: list[str], formatted: list[str]) -> bool:
    if len(original) != 1 or len(formatted) != 1:
        return False
    original_line = strip_line_comment(original[0])
    formatted_line = strip_line_comment(formatted[0])
    if not POINTER_STYLE_RE.search(original_line) and not POINTER_STYLE_RE.search(formatted_line):
        return False
    return normalize_cpp_tokens([original_line]) == normalize_cpp_tokens([formatted_line])


def report_format_difference(
    violations: list[Violation],
    path: Path,
    start_line: int,
    original: list[str],
    formatted: list[str],
) -> None:
    if is_short_inline_function_style_difference(original, formatted):
        return
    if is_pointer_style_difference(original, formatted):
        return

    max_lines = max(len(original), len(formatted))
    for offset in range(max_lines):
        line_number = start_line + offset
        current_line = original[offset] if offset < len(original) else "<missing line>"
        expected_line = formatted[offset] if offset < len(formatted) else "<extra line should be removed>"
        if current_line == expected_line:
            continue
        if "\t" in current_line:
            add(
                violations,
                path,
                line_number,
                "Formatting differs from .clang-format: tab found; expected spaces only.",
            )
            continue
        add(
            violations,
            path,
            line_number,
            f"Formatting differs from .clang-format. Expected: {expected_line!r}",
        )


def check_clang_format(path: Path, root: Path, violations: list[Violation]) -> None:
    relative_path = path.relative_to(root)
    clang_format = shutil.which("clang-format")
    if clang_format is None:
        add(
            violations,
            relative_path,
            1,
            "clang-format is required to check .clang-format compliance, but it was not found in PATH.",
        )
        return

    result = subprocess.run(
        [clang_format, "--style=file", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "clang-format failed."
        add(violations, relative_path, 1, f"clang-format error: {message}")
        return

    original_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    formatted_lines = result.stdout.splitlines()

    matcher = SequenceMatcher(None, original_lines, formatted_lines, autojunk=False)
    for tag, original_start, original_end, formatted_start, formatted_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        report_format_difference(
            violations,
            relative_path,
            original_start + 1,
            original_lines[original_start:original_end],
            formatted_lines[formatted_start:formatted_end],
        )


def parse_compiler_line(line: str) -> tuple[int | None, str]:
    match = re.search(r":(\d+):(?:\d+:)?\s*(?:fatal\s+)?(?:error|warning):\s*(.+)$", line)
    if not match:
        return None, line.strip()
    return int(match.group(1)), match.group(2).strip()


def check_cpp_syntax(path: Path, root: Path, violations: list[Violation]) -> None:
    if path.suffix.lower() not in SOURCE_EXTENSIONS:
        return

    relative_path = path.relative_to(root)
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        add(
            violations,
            relative_path,
            1,
            "C++ compiler is required for syntax checks, but neither g++ nor clang++ was found in PATH.",
        )
        return

    result = subprocess.run(
        [compiler, "-std=c++17", "-fsyntax-only", "-Wall", "-Wextra", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return

    reported = False
    for line in result.stderr.splitlines():
        if ": error:" not in line and ": fatal error:" not in line:
            continue
        line_number, message = parse_compiler_line(line)
        add(violations, relative_path, line_number or 1, f"C++ syntax error: {message}")
        reported = True

    if not reported:
        message = result.stderr.strip() or result.stdout.strip() or "Compiler syntax check failed."
        add(violations, relative_path, 1, f"C++ syntax error: {message}")


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


def check_control_statement_braces(path: Path, lines: list[str], violations: list[Violation]) -> None:
    for line_number, raw_line in enumerate(lines, start=1):
        code = strip_line_comment(raw_line)
        if not re.match(r"^\s*(?:if|for|while)\s*\(.+\)", code):
            continue
        stripped = code.strip()
        if stripped.endswith(";") or "{" in stripped:
            continue

        next_code = ""
        for next_line in lines[line_number:]:
            next_code = strip_line_comment(next_line).strip()
            if next_code:
                break

        if next_code != "{":
            add(
                violations,
                path,
                line_number,
                "Always use braces for if, for, and while statements; put '{' on the same line or the next non-empty line.",
            )


def check_file(path: Path, root: Path) -> list[Violation]:
    violations: list[Violation] = []
    relative_path = path.relative_to(root)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    check_clang_format(path, root, violations)
    check_cpp_syntax(path, root, violations)

    if not SNAKE_CASE_FILE_RE.match(path.name):
        add(violations, relative_path, 1, "C++ file names must use snake_case.")

    check_header_guard(relative_path, lines, violations)
    check_switch_default(relative_path, lines, violations)
    check_control_statement_braces(relative_path, lines, violations)
    class_names = {match.group(1) for line in lines for match in CLASS_RE.finditer(strip_line_comment(line))}

    for line_number, raw_line in enumerate(lines, start=1):
        code = strip_line_comment(raw_line)
        stripped = code.strip()

        if "\t" in raw_line:
            add(violations, relative_path, line_number, "Tab indentation found; use 4 spaces instead.")

        if "NULL" in code and NULL_RE.search(code):
            add(violations, relative_path, line_number, "NULL found; use nullptr instead.")

        if TYPEDEF_RE.search(code):
            add(violations, relative_path, line_number, "Use using instead of typedef.")

        if USING_NAMESPACE_STD_RE.search(code):
            add(violations, relative_path, line_number, "Avoid using namespace std.")

        macro_match = MACRO_RE.search(code)
        if macro_match and not UPPER_CASE_RE.match(macro_match.group(1)):
            macro_name = macro_match.group(1)
            add(violations, relative_path, line_number, f"Macro '{macro_name}' must use UPPER_CASE.")

        enum_match = ENUM_RE.search(code)
        if enum_match:
            enum_name = enum_match.group(1) or "<anonymous>"
            add(violations, relative_path, line_number, f"Enum '{enum_name}' must use enum class instead of plain enum.")

        class_match = CLASS_RE.search(code)
        if class_match and not PASCAL_CASE_RE.match(class_match.group(1)):
            class_name = class_match.group(1)
            add(violations, relative_path, line_number, f"Class/struct '{class_name}' must use PascalCase.")

        for const_match in CONST_RE.finditer(code):
            const_name = const_match.group(1)
            next_char_match = re.search(r"\S", code[const_match.end() :])
            next_char = next_char_match.group(0) if next_char_match else ""
            if next_char in {",", ")"}:
                continue
            if const_name not in {"auto"} and not UPPER_CASE_RE.match(const_name):
                add(violations, relative_path, line_number, f"Constant '{const_name}' must use UPPER_CASE.")

        for bool_name in BOOL_RE.findall(code):
            if not BOOL_PREFIX_RE.match(bool_name):
                add(
                    violations,
                    relative_path,
                    line_number,
                    f"Boolean variable '{bool_name}' must start with is, has, can, or should.",
                )

        function_match = FUNCTION_RE.match(code)
        if function_match:
            name = function_match.group(1)
            if (
                name not in {"main"}
                and name not in class_names
                and "::" not in name
                and not name.startswith("operator")
                and not CAMEL_CASE_RE.match(name)
            ):
                add(violations, relative_path, line_number, f"Function '{name}' must use camelCase.")

        if not is_comment_or_preprocessor(code):
            statement_count = stripped.count(";")
            if statement_count > 1:
                add(violations, relative_path, line_number, "Use one statement per line.")

            magic_number_match = MAGIC_NUMBER_RE.search(code)
            if magic_number_match and not re.search(r"\b(?:const|constexpr|case)\b", code):
                add(
                    violations,
                    relative_path,
                    line_number,
                    f"Magic number '{magic_number_match.group(0)}' found; use a named constant.",
                )

        member_match = re.search(r"^\s*(?:static\s+)?(?:[\w:<>,~*&]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*(?:[=;{])", code)
        if member_match and re.match(r"\s*(?:private|protected|public)\s*:", code) is None:
            name = member_match.group(1)
            if (name.startswith("m_") or name.startswith("s_")) and not MEMBER_RE.match(name):
                add(
                    violations,
                    relative_path,
                    line_number,
                    f"Member variable '{name}' should use m_ or s_ followed by camelCase.",
                )

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
