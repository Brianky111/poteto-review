#!/usr/bin/env python3
"""Cross-host installer, verifier, and uninstaller for poteto-review."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

SKILL_NAME = "poteto-review"
SKILL_VERSION = "1.0.0"
MANAGED_MARKER = ".poteto-review-managed.json"
DEFAULT_SOURCE = Path(__file__).resolve().parent.parent

SKILL_MAX_BYTES = 6500
REF_MAX_BYTES = 12000

COPY_FILES = ("SKILL.md", "README.md")
COPY_DIRS = ("agents", "references", "scripts")
IGNORE_NAMES = {"__pycache__", ".pytest_cache", ".git", ".DS_Store", MANAGED_MARKER}

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def preset_targets() -> dict[str, Path]:
    home = Path.home()
    return {
        "claude": home / ".claude" / "skills",
        "cursor": home / ".cursor" / "skills",
        "codex": home / ".codex" / "skills",
        "agents": home / ".agents" / "skills",
        "pi": home / ".pi" / "agent" / "skills",
    }


def _lf_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _extract_relative_links(md_text: str) -> list[str]:
    links: list[str] = []
    in_fence = False
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in MD_LINK_RE.finditer(line):
            target = match.group(1).strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:", "file://")):
                continue
            target_no_anchor = target.split("#", 1)[0]
            if target_no_anchor:
                links.append(target_no_anchor)
    return links


def verify_installed_copy(skill_dir: Path) -> tuple[int, list[str]]:
    """Verify the installed poteto-review directory structure, budgets, and links."""
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return 0, [f"missing {skill_md}"]

    raw_skill = _lf_bytes(skill_md)
    if len(raw_skill) > SKILL_MAX_BYTES:
        errors.append(f"SKILL.md exceeds {SKILL_MAX_BYTES} bytes ({len(raw_skill)})")
    skill_text = raw_skill.decode("utf-8", errors="replace")
    fm = FRONTMATTER_RE.match(skill_text)
    if not fm:
        errors.append("SKILL.md missing YAML frontmatter")
    else:
        body = fm.group(1)
        if not re.search(r"(?m)^name:\s*poteto-review\s*$", body):
            errors.append("SKILL.md frontmatter missing 'name: poteto-review'")
        if not re.search(r"(?m)^description:\s*\S+", body):
            errors.append("SKILL.md frontmatter missing 'description'")

    ref_dir = skill_dir / "references"
    ref_files = sorted(ref_dir.glob("*.md")) if ref_dir.is_dir() else []
    expected_refs = {"01-review-rubric-and-modes.md", "02-case-anchors-and-boundaries.md"}
    found_ref_names = {p.name for p in ref_files}
    for missing in sorted(expected_refs - found_ref_names):
        errors.append(f"missing reference file: references/{missing}")
    for rf in ref_files:
        rbytes = len(_lf_bytes(rf))
        if rbytes > REF_MAX_BYTES:
            errors.append(f"references/{rf.name} exceeds {REF_MAX_BYTES} bytes ({rbytes})")

    for req in ("scripts/poteto_audit.py", "agents/openai.yaml", "README.md"):
        if not (skill_dir / req).is_file():
            errors.append(f"missing required file: {req}")

    md_to_check = [skill_md, *(p for p in [skill_dir / "README.md"] if p.is_file()), *ref_files]
    skill_root_res = skill_dir.resolve()
    for md_path in md_to_check:
        md_text = _lf_bytes(md_path).decode("utf-8", errors="replace")
        for link in _extract_relative_links(md_text):
            resolved = (md_path.parent / link).resolve()
            if not resolved.is_relative_to(skill_root_res) or not resolved.exists():
                errors.append(f"broken relative link in {md_path.relative_to(skill_dir).as_posix()}: {link}")

    return len(ref_files), errors


def _ignore_copy(_src: str, names: list[str]) -> set[str]:
    return {n for n in names if n in IGNORE_NAMES or n.endswith((".pyc", ".pyo"))}


def _copy_skill_tree(source: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for fname in COPY_FILES:
        src_file = source / fname
        if src_file.is_file():
            shutil.copy2(src_file, dest_dir / fname)
    for dname in COPY_DIRS:
        src_subdir = source / dname
        if src_subdir.is_dir():
            shutil.copytree(src_subdir, dest_dir / dname, ignore=_ignore_copy)
    marker = dest_dir / MANAGED_MARKER
    marker.write_text(
        json.dumps({"skill": SKILL_NAME, "version": SKILL_VERSION, "source": source.as_posix()}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def resolve_targets(target_arg: str, dest_arg: str | None) -> list[tuple[str, Path]]:
    presets = preset_targets()
    if target_arg == "custom":
        if not dest_arg:
            raise ValueError("--dest is required when --target custom")
        return [("custom", Path(dest_arg).expanduser().resolve())]
    if dest_arg:
        raise ValueError("--dest is only valid with --target custom")
    if target_arg == "all":
        return [(name, presets[name]) for name in ("claude", "cursor", "codex", "agents", "pi")]
    return [(target_arg, presets[target_arg])]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install, verify, or uninstall poteto-review across agent hosts.")
    parser.add_argument(
        "--target",
        choices=("claude", "cursor", "codex", "agents", "pi", "all", "custom"),
        default="all",
        help="Target host skills directory (default: all).",
    )
    parser.add_argument("--dest", help="Custom skills root directory when --target custom is used.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Source repository root (default: this repo).")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without modifying disk.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing unmanaged directory.")
    parser.add_argument("--uninstall", action="store_true", help="Remove managed poteto-review installation.")
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    try:
        targets = resolve_targets(args.target, args.dest)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.uninstall:
        for label, skills_root in targets:
            dest_dir = skills_root / SKILL_NAME
            if not dest_dir.exists():
                print(f"SKIP    [{label}] not installed at {dest_dir}")
                continue
            if not (dest_dir / MANAGED_MARKER).is_file() and not args.force:
                print(f"ERROR   [{label}] refusing to remove unmanaged directory without --force: {dest_dir}", file=sys.stderr)
                return 1
            prefix = "DRY-RUN" if args.dry_run else "OK     "
            print(f"{prefix} [{label}] uninstall {SKILL_NAME} <- {dest_dir}")
            if not args.dry_run:
                shutil.rmtree(dest_dir)
        return 0

    src_refs, src_errors = verify_installed_copy(source)
    if src_errors:
        for err in src_errors:
            print(f"ERROR   [source] {err}", file=sys.stderr)
        return 1

    for label, skills_root in targets:
        dest_dir = skills_root / SKILL_NAME
        if dest_dir.exists() and not (dest_dir / MANAGED_MARKER).is_file() and not args.force:
            print(
                f"ERROR   [{label}] unmanaged collision at {dest_dir}; pass --force to overwrite",
                file=sys.stderr,
            )
            return 1

    for label, skills_root in targets:
        dest_dir = skills_root / SKILL_NAME
        if args.dry_run:
            print(f"DRY-RUN [{label}] install {SKILL_NAME} -> {dest_dir}")
            continue
        _copy_skill_tree(source, dest_dir)
        print(f"OK      [{label}] install {SKILL_NAME} -> {dest_dir}")
        ref_count, ver_errors = verify_installed_copy(dest_dir)
        if ver_errors:
            for err in ver_errors:
                print(f"ERROR   [{label}] {err}", file=sys.stderr)
            return 1
        print(f"VERIFY  [{label}] {ref_count} reference file(s), 0 error(s)")
    if args.dry_run:
        print(f"VERIFY  [source] {src_refs} reference file(s), 0 error(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
