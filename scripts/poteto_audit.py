#!/usr/bin/env python3
"""Read-only deterministic audit radar for Poteto Review.

Collects signals across the Inverted Trust Pyramid (code smells, verification
surface, test smells, and prose/skill bloat) for a whole repo or a git diff.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", "coverage",
    ".next", ".venv", "venv", "__pycache__", "vendor", "archive", ".trash",
}
CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".kt", ".cs", ".cpp", ".c", ".h", ".hpp", ".rb", ".php", ".swift", ".sh",
}
HASH_COMMENT_EXTS = {".py", ".sh", ".rb", ".yaml", ".yml"}
SLASH_COMMENT_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".kt", ".cs", ".cpp", ".c", ".h", ".hpp", ".php", ".swift",
}
GOD_FILE_LINE_THRESHOLD = 500
SERMON_MIN_LINES = 5
PROSE_BLOAT_BYTES = 6500
PROSE_BLOAT_PROHIBITIONS = 8

SUPPRESSION_COMMENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ts-ignore", re.compile(r"@ts-ignore\b")),
    ("ts-expect-error", re.compile(r"@ts-expect-error\b")),
    ("eslint-disable", re.compile(r"\beslint-disable(?:-next-line|-line)?\b")),
    ("biome-ignore", re.compile(r"\bbiome-ignore\b")),
    ("noqa", re.compile(r"#\s*noqa\b")),
    ("type-ignore", re.compile(r"#\s*type:\s*ignore\b")),
    ("nolint", re.compile(r"//\s*nolint\b")),
)
RUST_ALLOW_PATTERN = re.compile(r"#\[allow\(")
ALIBI_KEYWORD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("marker-tag", re.compile(r"\b(?:HACK|FIXME|WORKAROUND|KLUDGE|TEMP)\b")),
    ("do-not-remove", re.compile(r"\bdo\s+not\s+remove\b|\bdon't\s+remove\b", re.I)),
    ("for-now", re.compile(r"\bfine\s+for\s+now\b|\bfor\s+now\b", re.I)),
    ("temporary-fix", re.compile(r"\btemporary\s+fix\b", re.I)),
    ("timing-excuse", re.compile(r"\btiming\s+issue\b|\brace\s+condition\b", re.I)),
)
LICENSE_OR_SHEBANG_HINT = re.compile(
    r"^(?:#!.*|.*\b(?:copyright|spdx-license-identifier|mit license|apache license|all rights reserved)\b.*)$",
    re.I,
)
SYMPTOM_CALL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("setTimeout", re.compile(r"\bsetTimeout\s*\(")),
    ("requestAnimationFrame", re.compile(r"\brequestAnimationFrame\s*\(")),
    ("requestIdleCallback", re.compile(r"\brequestIdleCallback\s*\(")),
    ("time.sleep", re.compile(r"\btime\.sleep\s*\(")),
    ("asyncio.sleep", re.compile(r"\basyncio\.sleep\s*\(")),
)
EMPTY_JS_CATCH = re.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*(?://[^\n]*)?\s*\}")
EMPTY_PY_EXCEPT = re.compile(r"\bexcept\b[^:\n]*:\s*(?:pass|\.\.\.)\s*(?:#[^\n]*)?(?=\n|$)")
MOCK_CALL_RE = re.compile(r"\b(?:jest\.mock|vi\.mock|unittest\.mock|MagicMock|patch)\s*(?:\(|\.)")
SKIP_TEST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("js-skip", re.compile(r"\b(?:it|test|describe)\.skip\b")),
    ("unittest-skip", re.compile(r"@unittest\.skip\b")),
    ("pytest-skip", re.compile(r"@pytest\.mark\.skip\b")),
)
TAUTOLOGY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("toBeDefined", re.compile(r"expect\([^)\n]+\)\.toBeDefined\(\)")),
    ("assertTrue-True", re.compile(r"\bassertTrue\s*\(\s*True\s*\)")),
    ("assert-True", re.compile(r"(?m)^\s*assert\s+True\b")),
)
PROHIBITION_RE = re.compile(r"禁止|严禁|绝不|\bNEVER\b|\bMUST\s+NOT\b|\bDO\s+NOT\b")
TEST_CONFIG_NAMES = {
    "pytest.ini", "vitest.config.ts", "vitest.config.js", "vitest.config.mts",
    "playwright.config.ts", "playwright.config.js", "playwright.config.mts",
    "jest.config.js", "jest.config.ts", "jest.config.mjs",
}


def _rel_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _walk_repo_files(root: Path) -> list[Path]:
    found: list[Path] = []
    root_res = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root_res):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        cur = Path(dirpath)
        for fname in sorted(filenames):
            fpath = cur / fname
            if fpath.is_file():
                found.append(fpath)
    return found


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


def _is_text_file(path: Path) -> bool:
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    return b"\x00" not in raw[:8192]


def collect_target_files(root: Path, diff_base: str | None) -> tuple[list[Path], list[Path], dict]:
    """Return (target_files, all_repo_files, diff_info)."""
    root_res = root.resolve()
    all_repo_files = _walk_repo_files(root_res)
    if diff_base is None:
        return all_repo_files, all_repo_files, {"mode": "repo", "base": None, "files_count": len(all_repo_files)}

    diff_info: dict = {"mode": "diff", "base": diff_base, "files_count": 0, "note": None}
    in_git = _run_git(root_res, ["rev-parse", "--is-inside-work-tree"])
    if in_git.returncode != 0 or in_git.stdout.strip().lower() != "true":
        diff_info["note"] = "not a git repository; 0 diff files scanned"
        return [], all_repo_files, diff_info

    rel_candidates: set[str] = set()
    ref_ok = _run_git(root_res, ["rev-parse", "--verify", diff_base]).returncode == 0
    if ref_ok:
        diff_proc = _run_git(root_res, ["diff", "--name-only", diff_base])
        if diff_proc.returncode == 0:
            rel_candidates.update(ln.strip() for ln in diff_proc.stdout.splitlines() if ln.strip())
        else:
            diff_info["note"] = diff_proc.stderr.strip() or "git diff failed"
    elif diff_base == "HEAD":
        diff_info["note"] = "unborn HEAD; scanned staged and untracked files"
        cached = _run_git(root_res, ["diff", "--cached", "--name-only"])
        if cached.returncode == 0:
            rel_candidates.update(ln.strip() for ln in cached.stdout.splitlines() if ln.strip())
    else:
        diff_info["note"] = f"git ref {diff_base!r} not found"
        return [], all_repo_files, diff_info

    untracked = _run_git(root_res, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode == 0:
        rel_candidates.update(ln.strip() for ln in untracked.stdout.splitlines() if ln.strip())

    target_files: list[Path] = []
    for rel in sorted(rel_candidates):
        cand = (root_res / rel).resolve()
        if not cand.is_relative_to(root_res) or not cand.is_file():
            continue
        if any(part in SKIP_DIRS for part in cand.relative_to(root_res).parts[:-1]):
            continue
        target_files.append(cand)

    diff_info["files_count"] = len(target_files)
    return target_files, all_repo_files, diff_info


def _is_test_file(rel_posix: str) -> bool:
    parts = rel_posix.lower().split("/")
    name = parts[-1]
    if any(p in {"tests", "__tests__", "test"} for p in parts[:-1]):
        return True
    return name.startswith("test_") or ".test." in name or ".spec." in name or Path(name).stem.endswith("_test")


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


def _split_line_quotes_and_comment(line: str, comment_prefix: str) -> tuple[str, str | None]:
    """Return (code_without_string_literals, comment_text_or_none) for a single line."""
    code_chars: list[str] = []
    i, n, quote = 0, len(line), None
    while i < n:
        ch = line[i]
        if quote is not None:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            code_chars.append(" ")
            i += 1
            continue
        if line.startswith(comment_prefix, i):
            return "".join(code_chars), line[i:]
        code_chars.append(ch)
        i += 1
    return "".join(code_chars), None


def _scan_prefixed_lines(lines: list[str], prefix: str) -> tuple[list[tuple[int, str, bool]], str]:
    comments: list[tuple[int, str, bool]] = []
    code_lines: list[str] = []
    for idx, line in enumerate(lines, start=1):
        code_part, ctext = _split_line_quotes_and_comment(line, prefix)
        code_lines.append(code_part)
        if ctext is not None:
            comments.append((idx, ctext, line.lstrip().startswith(prefix)))
    return comments, "\n".join(code_lines)


def _analyze_code_text(text: str, ext: str) -> tuple[list[tuple[int, str, bool]], str]:
    """Extract (line_no, comment_text, is_comment_only_line) and string/comment-masked code."""
    lines = text.splitlines()
    if ext == ".py":
        comments: list[tuple[int, str, bool]] = []
        masked = [list(ln) for ln in lines]
        try:
            for tok_type, tok_str, (srow, scol), (erow, ecol), line_text in tokenize.generate_tokens(
                io.StringIO(text).readline
            ):
                if tok_type == tokenize.COMMENT:
                    comments.append((srow, tok_str, line_text[:scol].strip() == ""))
                    for c in range(scol, min(ecol, len(masked[srow - 1]))):
                        masked[srow - 1][c] = " "
                elif tok_type == tokenize.STRING:
                    for row in range(srow, min(erow, len(masked)) + 1):
                        start_c = scol if row == srow else 0
                        end_c = ecol if row == erow else len(masked[row - 1])
                        for c in range(start_c, min(end_c, len(masked[row - 1]))):
                            masked[row - 1][c] = " "
            return comments, "\n".join("".join(row) for row in masked)
        except (tokenize.TokenError, IndentationError):
            # Incomplete or unclosed Python tokens fall back to single-line lexical scanning.
            return _scan_prefixed_lines(lines, "#")

    prefix = "#" if ext in HASH_COMMENT_EXTS else "//" if ext in SLASH_COMMENT_EXTS else None
    if prefix is None:
        return [], text
    return _scan_prefixed_lines(lines, prefix)


def _flush_sermon_run(rel: str, run: list[tuple[int, str]], out: list[dict]) -> None:
    if len(run) < SERMON_MIN_LINES:
        return
    if run[0][0] == 1 or all(LICENSE_OR_SHEBANG_HINT.match(txt) for _, txt in run):
        return
    out.append({"path": rel, "line": run[0][0], "reason": f"comment-sermon ({len(run)} lines)", "snippet": run[0][1].strip()[:120]})


def _collect_sermon_runs(rel: str, comments: list[tuple[int, str, bool]], out: list[dict]) -> None:
    only = [(ln, txt) for ln, txt, is_only in comments if is_only]
    if not only:
        return
    run = [only[0]]
    for item in only[1:]:
        if item[0] == run[-1][0] + 1:
            run.append(item)
        else:
            _flush_sermon_run(rel, run, out)
            run = [item]
    _flush_sermon_run(rel, run, out)


def scan_code_smells(root: Path, files: list[Path]) -> dict:
    """Scan code files for god files, suppressions, alibi comments, and symptom guards."""
    god_files: list[dict] = []
    suppressions: list[dict] = []
    alibi_comments: list[dict] = []
    symptom_guards: list[dict] = []

    for fpath in files:
        ext = fpath.suffix.lower()
        if ext not in CODE_EXTS or not _is_text_file(fpath):
            continue
        rel = _rel_posix(root, fpath)
        text = _read_text(fpath)
        line_count = len(text.splitlines())
        if line_count > GOD_FILE_LINE_THRESHOLD:
            god_files.append({"path": rel, "lines": line_count})

        comments, masked_code = _analyze_code_text(text, ext)
        for line_no, ctext, _ in comments:
            snippet = ctext.strip()[:120]
            for kind, pat in SUPPRESSION_COMMENT_PATTERNS:
                if pat.search(ctext):
                    suppressions.append({"path": rel, "line": line_no, "kind": kind, "snippet": snippet})
            for reason, pat in ALIBI_KEYWORD_PATTERNS:
                if pat.search(ctext):
                    alibi_comments.append({"path": rel, "line": line_no, "reason": reason, "snippet": snippet})
        _collect_sermon_runs(rel, comments, alibi_comments)

        if ext == ".rs":
            for idx, cline in enumerate(masked_code.splitlines(), start=1):
                if RUST_ALLOW_PATTERN.search(cline):
                    suppressions.append({"path": rel, "line": idx, "kind": "rust-allow", "snippet": cline.strip()[:120]})

        if not _is_test_file(rel):
            for idx, cline in enumerate(masked_code.splitlines(), start=1):
                for kind, pat in SYMPTOM_CALL_PATTERNS:
                    if pat.search(cline):
                        symptom_guards.append({"path": rel, "line": idx, "kind": kind, "snippet": cline.strip()[:120]})
            multiline_rules = []
            if ext in SLASH_COMMENT_EXTS:
                multiline_rules.append(("empty-catch", EMPTY_JS_CATCH))
            if ext == ".py":
                multiline_rules.append(("silent-except", EMPTY_PY_EXCEPT))
            for kind, pat in multiline_rules:
                for m in pat.finditer(masked_code):
                    ln = masked_code[: m.start()].count("\n") + 1
                    symptom_guards.append({"path": rel, "line": ln, "kind": kind, "snippet": " ".join(m.group(0).split())[:120]})

    god_files.sort(key=lambda item: (-item["lines"], item["path"]))
    return {"god_files": god_files, "suppressions": suppressions, "alibi_comments": alibi_comments, "symptom_guards": symptom_guards}


def scan_verification_surface(root: Path, all_repo_files: list[Path], target_files: list[Path]) -> dict:
    """Detect repo verification assets and inspect test files for weak/mock smells."""
    all_rels = [_rel_posix(root, p) for p in all_repo_files]
    repo_tests = [p for p in all_repo_files if _is_test_file(_rel_posix(root, p))]
    target_tests = [p for p in target_files if _is_test_file(_rel_posix(root, p)) and _is_text_file(p)]

    mock_calls, skipped_tests, tautological = 0, [], []
    for tf in target_tests:
        rel = _rel_posix(root, tf)
        _, masked_code = _analyze_code_text(_read_text(tf), tf.suffix.lower())
        for idx, line in enumerate(masked_code.splitlines(), start=1):
            mock_calls += len(MOCK_CALL_RE.findall(line))
            for kind, pat in SKIP_TEST_PATTERNS:
                if pat.search(line):
                    skipped_tests.append({"path": rel, "line": idx, "kind": kind, "snippet": line.strip()[:120]})
            for kind, pat in TAUTOLOGY_PATTERNS:
                if pat.search(line):
                    tautological.append({"path": rel, "line": idx, "kind": kind, "snippet": line.strip()[:120]})

    return {
        "assets": {
            "guardrails_config": (root / ".guardrails" / "config.json").is_file(),
            "feature_map": any(Path(p).name == "feature-map.md" for p in all_rels),
            "verify_skills": sorted(p[:-9] for p in all_rels if p.endswith("/SKILL.md") and Path(p).parent.name.startswith("verify-")),
            "formal_files": sorted(p for p in all_rels if p.endswith((".tla", ".lean"))),
            "test_configs": sorted(p for p in all_rels if Path(p).name in TEST_CONFIG_NAMES),
            "test_files_total": len(repo_tests),
            "test_files_scanned": len(target_tests),
        },
        "test_smells": {"mock_calls": mock_calls, "skipped_tests": skipped_tests, "tautological_smells": tautological},
    }


def scan_prose_and_skills(root: Path, all_repo_files: list[Path]) -> dict:
    """Inspect AGENTS.md/CLAUDE.md/GEMINI.md, Cursor rules, SKILL.md, and eval prompts."""
    docs: list[dict] = []
    eval_files: list[str] = []
    top_names = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "SKILL.md"}

    for fpath in all_repo_files:
        rel = _rel_posix(root, fpath)
        parts = rel.split("/")
        name = parts[-1]
        is_doc = (
            (len(parts) <= 2 and name in top_names)
            or (len(parts) >= 3 and parts[:2] == [".cursor", "rules"] and ".md" in name)
            or (len(parts) >= 4 and parts[:2] == [".agents", "skills"] and name == "SKILL.md")
        )
        if is_doc and _is_text_file(fpath):
            lf_raw = fpath.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            text = lf_raw.decode("utf-8", errors="replace")
            prohibitions = sum(1 for ln in text.splitlines() if PROHIBITION_RE.search(ln))
            lf_bytes = len(lf_raw)
            docs.append({
                "path": rel,
                "bytes": lf_bytes,
                "lines": len(text.splitlines()),
                "prohibitions": prohibitions,
                "prose_bloat": lf_bytes > PROSE_BLOAT_BYTES or prohibitions >= PROSE_BLOAT_PROHIBITIONS,
            })
        if ("eval" in name.lower() or "evals" in parts[:-1]) and name.endswith((".md", ".txt", ".json")):
            eval_files.append(rel)

    return {"instruction_docs": docs, "eval_files": sorted(eval_files)}


def audit_target(root: Path, diff_base: str | None = None) -> dict:
    """Run the full deterministic Poteto audit against root (or a git diff)."""
    root_res = root.resolve()
    target_files, all_repo_files, diff_info = collect_target_files(root_res, diff_base)
    return {
        "root": root_res.as_posix(),
        "scope": diff_info,
        "code_smells": scan_code_smells(root_res, target_files),
        "verification": scan_verification_surface(root_res, all_repo_files, target_files),
        "prose_and_skills": scan_prose_and_skills(root_res, all_repo_files),
    }


def _append_sample_lines(out: list[str], label: str, items: list[dict], key: str) -> None:
    if not items:
        return
    out.append(f"  {label} ({len(items)}):")
    for item in items[:10]:
        out.append(f"    - {item['path']}:{item['line']} [{item[key]}] {item['snippet']}")
    if len(items) > 10:
        out.append(f"    ... +{len(items) - 10} more")


def format_human(report: dict) -> str:
    """Format the audit report cleanly for human/agent reading."""
    scope, smells = report["scope"], report["code_smells"]
    assets, tsmells = report["verification"]["assets"], report["verification"]["test_smells"]
    prose = report["prose_and_skills"]

    lines = [
        f"poteto_audit | root={report['root']} | mode={scope['mode']}"
        + (f" base={scope['base']}" if scope["base"] else "")
        + f" | scanned_files={scope['files_count']}",
    ]
    if scope.get("note"):
        lines.append(f"  note: {scope['note']}")
    lines.append(
        f"  code_smells: god_files={len(smells['god_files'])} suppressions={len(smells['suppressions'])} "
        f"alibi_comments={len(smells['alibi_comments'])} symptom_guards={len(smells['symptom_guards'])}"
    )
    for gf in smells["god_files"][:10]:
        lines.append(f"    - god_file: {gf['path']} ({gf['lines']} lines)")
    _append_sample_lines(lines, "suppressions", smells["suppressions"], "kind")
    _append_sample_lines(lines, "alibi_comments", smells["alibi_comments"], "reason")
    _append_sample_lines(lines, "symptom_guards", smells["symptom_guards"], "kind")
    lines.append(
        f"  verification: guardrails={assets['guardrails_config']} feature_map={assets['feature_map']} "
        f"verify_skills={len(assets['verify_skills'])} formal_files={len(assets['formal_files'])} "
        f"test_files={assets['test_files_scanned']}/{assets['test_files_total']} "
        f"mock_calls={tsmells['mock_calls']} skipped={len(tsmells['skipped_tests'])} tautological={len(tsmells['tautological_smells'])}"
    )
    _append_sample_lines(lines, "skipped_tests", tsmells["skipped_tests"], "kind")
    _append_sample_lines(lines, "tautological_smells", tsmells["tautological_smells"], "kind")
    lines.append(
        f"  prose_and_skills: docs={len(prose['instruction_docs'])} "
        f"bloated={sum(1 for d in prose['instruction_docs'] if d['prose_bloat'])} eval_files={len(prose['eval_files'])}"
    )
    for doc in prose["instruction_docs"]:
        tag = " [BLOAT]" if doc["prose_bloat"] else ""
        lines.append(f"    - {doc['path']}: {doc['bytes']}B, {doc['lines']} lines, prohibitions={doc['prohibitions']}{tag}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only deterministic audit radar for Poteto Review.")
    parser.add_argument("--root", default=".", help="Target repository or directory to inspect (default: .)")
    parser.add_argument("--diff", nargs="?", const="HEAD", default=None, metavar="BASE", help="Inspect changed files vs BASE plus untracked files.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON report.")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: root directory not found: {root}", file=sys.stderr)
        return 2
    report = audit_target(root, diff_base=args.diff)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
