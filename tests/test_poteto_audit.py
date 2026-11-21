#!/usr/bin/env python3
"""Unit tests for scripts/poteto_audit.py."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
poteto_audit = importlib.import_module("poteto_audit")


class PotetoAuditTests(unittest.TestCase):
    def write_file(self, root: Path, rel: str, content: str) -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def run_git(self, root: Path, *args: str) -> None:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")

    def test_repo_mode_detects_all_pyramid_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(root, "src/giant.py", "\n".join(f"x_{i} = {i}" for i in range(505)) + "\n")
            self.write_file(
                root,
                "src/license_head.py",
                "#!/usr/bin/env python3\n"
                "# Copyright (c) 2026 Example\n"
                "# SPDX-License-Identifier: MIT\n"
                "# Permission is granted\n"
                "# All rights reserved\n"
                "def ok():\n    return 1\n",
            )
            self.write_file(
                root,
                "src/bad.ts",
                "// @ts-ignore\n"
                "const a: any = 1;\n"
                "// HACK: temporary fix for timing issue\n"
                "// Line 1 explanation\n"
                "// Line 2 explanation\n"
                "// Line 3 explanation\n"
                "// Line 4 explanation\n"
                "// Line 5 explanation\n"
                "setTimeout(() => {}, 50);\n"
                "try {\n  run();\n} catch (e) {\n  // ignore\n}\n",
            )
            self.write_file(
                root,
                "src/bad.py",
                "import time\n"
                "x = 1  # noqa\n"
                "try:\n"
                "    time.sleep(0.1)\n"
                "except Exception:\n"
                "    pass\n",
            )
            self.write_file(
                root,
                "tests/sample.test.ts",
                "vi.mock('./dep');\n"
                "test.skip('later', () => {});\n"
                "expect(value).toBeDefined();\n"
                "setTimeout(() => {}, 10);\n",
            )
            self.write_file(
                root,
                "tests/test_sample.py",
                "import unittest\n"
                "from unittest.mock import patch\n"
                "@unittest.skip('wip')\n"
                "def test_ok():\n"
                "    assert True\n",
            )
            self.write_file(root, ".guardrails/config.json", '{"version": 2}\n')
            self.write_file(root, "feature-map.md", "# Feature Map\n")
            self.write_file(root, "spec/flow.tla", "---- MODULE flow ----\n====\n")
            self.write_file(root, ".agents/skills/verify-app/SKILL.md", "---\nname: verify-app\ndescription: x\n---\n")
            self.write_file(
                root,
                "AGENTS.md",
                "\n".join(f"- 禁止做第 {i} 件机械事" for i in range(9)) + "\n",
            )

            report = poteto_audit.audit_target(root)
            smells = report["code_smells"]
            self.assertEqual([g["path"] for g in smells["god_files"]], ["src/giant.py"])
            self.assertEqual(smells["god_files"][0]["lines"], 505)

            sup_kinds = {(s["path"], s["kind"]) for s in smells["suppressions"]}
            self.assertIn(("src/bad.ts", "ts-ignore"), sup_kinds)
            self.assertIn(("src/bad.py", "noqa"), sup_kinds)

            alibi_reasons = {(a["path"], a["reason"]) for a in smells["alibi_comments"]}
            self.assertIn(("src/bad.ts", "marker-tag"), alibi_reasons)
            self.assertIn(("src/bad.ts", "comment-sermon (6 lines)"), alibi_reasons)
            self.assertNotIn("src/license_head.py", {a["path"] for a in smells["alibi_comments"]})

            guard_pairs = {(g["path"], g["kind"]) for g in smells["symptom_guards"]}
            self.assertIn(("src/bad.ts", "setTimeout"), guard_pairs)
            self.assertIn(("src/bad.ts", "empty-catch"), guard_pairs)
            self.assertIn(("src/bad.py", "time.sleep"), guard_pairs)
            self.assertIn(("src/bad.py", "silent-except"), guard_pairs)
            self.assertNotIn("tests/sample.test.ts", {g["path"] for g in smells["symptom_guards"]})

            ver = report["verification"]
            self.assertTrue(ver["assets"]["guardrails_config"])
            self.assertTrue(ver["assets"]["feature_map"])
            self.assertEqual(ver["assets"]["verify_skills"], [".agents/skills/verify-app"])
            self.assertEqual(ver["assets"]["formal_files"], ["spec/flow.tla"])
            self.assertGreaterEqual(ver["test_smells"]["mock_calls"], 1)
            self.assertEqual(
                {(s["path"], s["kind"]) for s in ver["test_smells"]["skipped_tests"]},
                {("tests/sample.test.ts", "js-skip"), ("tests/test_sample.py", "unittest-skip")},
            )
            self.assertEqual(
                {(t["path"], t["kind"]) for t in ver["test_smells"]["tautological_smells"]},
                {("tests/sample.test.ts", "toBeDefined"), ("tests/test_sample.py", "assert-True")},
            )

            docs = {d["path"]: d for d in report["prose_and_skills"]["instruction_docs"]}
            self.assertTrue(docs["AGENTS.md"]["prose_bloat"])
            self.assertEqual(docs["AGENTS.md"]["prohibitions"], 9)

    def test_diff_mode_scopes_to_changed_and_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_git(root, "init", "-b", "main")
            self.run_git(root, "config", "user.email", "test@example.com")
            self.run_git(root, "config", "user.name", "Test")

            # Unborn HEAD fallback checks staged/untracked cleanly.
            self.write_file(root, "unborn.py", "import time\ntime.sleep(1)\n")
            unborn_report = poteto_audit.audit_target(root, diff_base="HEAD")
            self.assertIn("unborn HEAD", unborn_report["scope"]["note"] or "")
            self.assertEqual([g["path"] for g in unborn_report["code_smells"]["symptom_guards"]], ["unborn.py"])
            (root / "unborn.py").unlink()

            self.write_file(root, "clean.py", "def ok():\n    return 1\n")
            self.write_file(root, "legacy_dirty.py", "import time\nx = 1  # noqa\ntime.sleep(2)\n")
            self.run_git(root, "add", ".")
            self.run_git(root, "commit", "-m", "baseline")

            self.run_git(root, "checkout", "-b", "feat/check")
            self.write_file(root, "feature.py", "x = 2  # type: ignore\n")
            self.run_git(root, "add", "feature.py")
            self.run_git(root, "commit", "-m", "add feature")
            self.write_file(root, "untracked_ui.ts", "// fine for now\nsetTimeout(() => {}, 10);\n")

            head_report = poteto_audit.audit_target(root, diff_base="HEAD")
            self.assertEqual([g["path"] for g in head_report["code_smells"]["symptom_guards"]], ["untracked_ui.ts"])

            main_report = poteto_audit.audit_target(root, diff_base="main")
            sup_paths = {s["path"] for s in main_report["code_smells"]["suppressions"]}
            self.assertEqual(sup_paths, {"feature.py"})
            self.assertNotIn("legacy_dirty.py", sup_paths)
            self.assertEqual(main_report["scope"]["files_count"], 2)

    def test_json_cli_and_cp1252_stdout_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_file(root, "AGENTS.md", "# 规则\n- 禁止绕过检查\n")
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "cp1252"
            env.pop("PYTHONUTF8", None)
            proc = subprocess.run(
                [sys.executable, str(SKILL_ROOT / "scripts" / "poteto_audit.py"), "--root", str(root), "--json"],
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", errors="replace"))
            payload = json.loads(proc.stdout.decode("utf-8"))
            self.assertEqual(payload["prose_and_skills"]["instruction_docs"][0]["path"], "AGENTS.md")

    def test_self_audit_is_clean(self) -> None:
        report = poteto_audit.audit_target(SKILL_ROOT)
        smells = report["code_smells"]
        self.assertEqual(smells["god_files"], [])
        self.assertEqual(smells["suppressions"], [])
        self.assertEqual(smells["alibi_comments"], [])
        self.assertEqual(smells["symptom_guards"], [])
        self.assertEqual(report["verification"]["test_smells"]["skipped_tests"], [])
        self.assertEqual(report["verification"]["test_smells"]["tautological_smells"], [])
        for doc in report["prose_and_skills"]["instruction_docs"]:
            self.assertFalse(doc["prose_bloat"], f"unexpected bloat in {doc}")


if __name__ == "__main__":
    unittest.main()
