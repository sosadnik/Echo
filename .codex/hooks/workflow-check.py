#!/usr/bin/env python3
"""Validate the repository-local agent workflow plan state machine."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


STATES = ("implementation", "verification", "completed")
PLAN_NAME = re.compile(r"^(\d{2,})_.+\.md$")
CHECKBOX = re.compile(r"^\s*-\s*(?:\[([ xX])\]|`\[([ xX])\]`)", re.MULTILINE)
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--next-plan-number", action="store_true")
    return parser.parse_args()


def plan_files(root: Path) -> list[tuple[str, Path]]:
    plans = root / "docs" / "02_plans"
    return [
        (state, path)
        for state in STATES
        for path in sorted((plans / state).glob("*.md"))
        if path.name != "README.md"
    ]


def numbered_paths(root: Path) -> list[Path]:
    paths = [path for _, path in plan_files(root)]
    archive = root / "docs" / "99_archive"
    paths.extend(path for path in archive.glob("*.md") if PLAN_NAME.fullmatch(path.name))
    return paths


def section(text: str, title_prefix: str) -> str:
    matches = list(SECTION.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1).lower().startswith(title_prefix.lower()):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            return text[match.end() : end]
    return ""


def checks(text: str) -> list[bool]:
    return [
        (match.group(1) or match.group(2)).lower() == "x"
        for match in CHECKBOX.finditer(text)
    ]


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    plans_root = root / "docs" / "02_plans"
    legacy = plans_root / "active"
    if legacy.exists():
        errors.append("legacy directory docs/02_plans/active exists; migrate it to implementation")
    if plans_root.exists():
        for path in sorted(plans_root.iterdir()):
            if path.is_dir() and path.name not in STATES and path.name != "active":
                errors.append(f"unsupported plan state directory: {path.relative_to(root)}")
            if path.is_file() and path.suffix == ".md" and path.name != "README.md":
                errors.append(f"plan must be placed in a lifecycle directory: {path.relative_to(root)}")

    by_number: dict[int, list[Path]] = defaultdict(list)
    for path in numbered_paths(root):
        match = PLAN_NAME.fullmatch(path.name)
        if match:
            by_number[int(match.group(1))].append(path)
    for state, path in plan_files(root):
        match = PLAN_NAME.fullmatch(path.name)
        if not match:
            errors.append(f"{path.relative_to(root)}: expected filename NN_slug.md")
            continue
        text = path.read_text(encoding="utf-8")
        implementation = checks(section(text, "Implementacja")) + checks(
            section(text, "Strumienie niezależne")
        )
        if not implementation:
            implementation = checks(text.split("## Weryfikacja końcowa", 1)[0])
        verification = checks(section(text, "Weryfikacja końcowa"))
        all_checks = checks(text)

        if not implementation:
            errors.append(f"{path.relative_to(root)}: missing implementation checklist")
        if not verification:
            errors.append(f"{path.relative_to(root)}: missing final verification checklist")
        if state in {"verification", "completed"} and implementation and not all(implementation):
            errors.append(f"{path.relative_to(root)}: implementation is incomplete for state {state}")
        if state == "completed":
            if all_checks and not all(all_checks):
                errors.append(f"{path.relative_to(root)}: completed plan has unchecked items")
            result = section(text, "Wynik weryfikacji").strip()
            evidence = re.sub(r"<!--.*?-->", "", result, flags=re.DOTALL).strip()
            if not evidence or "Nie przeprowadzono" in evidence:
                errors.append(f"{path.relative_to(root)}: completed plan lacks verification evidence")
            if "zablokowany" in section(text, "Status operacyjny").lower():
                errors.append(f"{path.relative_to(root)}: blocked plan cannot be completed")

    for number, paths in sorted(by_number.items()):
        if len(paths) > 1:
            rendered = ", ".join(str(path.relative_to(root)) for path in paths)
            errors.append(f"duplicate plan number {number:02d}: {rendered}")
    return errors


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    files = plan_files(root)
    if args.next_plan_number:
        numbers = [
            int(match.group(1))
            for path in numbered_paths(root)
            if (match := PLAN_NAME.fullmatch(path.name))
        ]
        print(f"{max(numbers, default=0) + 1:02d}")
        return 0

    errors = validate(root)
    if errors:
        print("Workflow validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Workflow validation passed ({len(files)} plan(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
