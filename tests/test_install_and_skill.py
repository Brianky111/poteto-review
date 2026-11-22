#!/usr/bin/env python3
"""Consistency, budget, LF, and cross-host installer tests for poteto-review."""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
installer = importlib.import_module("install")


class SkillContractAndInstallerTests(unittest.TestCase):
    def run_install(self, home_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(SKILL_ROOT / "scripts" / "install.py"), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )

    def test_shipped_files_utf8_lf_budgets_and_links(self) -> None:
        ref_count, errors = installer.verify_installed_copy(SKILL_ROOT)
        self.assertEqual(ref_count, 2)
        self.assertEqual(errors, [])

        audit_lines = (SKILL_ROOT / "scripts" / "poteto_audit.py").read_text(encoding="utf-8").splitlines()
        self.assertLess(len(audit_lines), 500)

        for path in SKILL_ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
                continue
            raw = path.read_bytes()
            self.assertNotIn(b"\r\n", raw, f"CRLF line ending found in {path.relative_to(SKILL_ROOT)}")
            raw.decode("utf-8")

        skill_bytes = len((SKILL_ROOT / "SKILL.md").read_bytes())
        self.assertLessEqual(skill_bytes, 6000)

        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        fm = re.match(r"\A---\n(.*?)\n---\n", skill_text, re.S)
        self.assertIsNotNone(fm)
        assert fm is not None
        self.assertRegex(fm.group(1), r"(?m)^name:\s*poteto-review\s*$")

        for ref_name in ("01-review-rubric-and-modes.md", "02-case-anchors-and-boundaries.md"):
            ref_bytes = len((SKILL_ROOT / "references" / ref_name).read_bytes())
            self.assertLessEqual(ref_bytes, 12000, ref_name)

        rubric_text = (SKILL_ROOT / "references" / "01-review-rubric-and-modes.md").read_text(encoding="utf-8")
        self.assertIn("No is an acceptable answer", skill_text)
        for marker in ("Attack the Premise", "Minimize Reader Load", "Explain the Number", "bugbot-triage"):
            self.assertIn(marker, skill_text)
        for marker in ("attack-the-premise", "minimize-reader-load", "explain-the-number", "bugbot-triage"):
            self.assertIn(marker, rubric_text)

    def test_dry_run_install_idempotent_collision_and_uninstall(self) -> None:
        host_subdirs = (
            Path(".claude/skills"),
            Path(".cursor/skills"),
            Path(".codex/skills"),
            Path(".agents/skills"),
            Path(".pi/agent/skills"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for rel_host in host_subdirs:
                unrelated = home / rel_host / "other-skill" / "SKILL.md"
                unrelated.parent.mkdir(parents=True, exist_ok=True)
                unrelated.write_text("---\nname: other-skill\ndescription: keep\n---\n", encoding="utf-8", newline="\n")

            dry = self.run_install(home, "--target", "all", "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            for rel_host in host_subdirs:
                self.assertFalse((home / rel_host / "poteto-review").exists())

            inst1 = self.run_install(home, "--target", "all")
            self.assertEqual(inst1.returncode, 0, inst1.stdout + inst1.stderr)
            self.assertEqual(inst1.stdout.count("VERIFY  ["), 5)
            for rel_host in host_subdirs:
                installed = home / rel_host / "poteto-review"
                self.assertTrue((installed / "SKILL.md").is_file())
                self.assertTrue((installed / installer.MANAGED_MARKER).is_file())
                self.assertFalse((installed / "tests").exists())
                self.assertFalse((installed / ".git").exists())

            # Re-run is idempotent and does not nest poteto-review/poteto-review.
            inst2 = self.run_install(home, "--target", "all")
            self.assertEqual(inst2.returncode, 0, inst2.stdout + inst2.stderr)
            for rel_host in host_subdirs:
                self.assertFalse((home / rel_host / "poteto-review" / "poteto-review").exists())

            # Remove managed marker on cursor -> refuses without --force, overwrites with --force.
            (home / ".cursor/skills/poteto-review" / installer.MANAGED_MARKER).unlink()
            blocked = self.run_install(home, "--target", "all")
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("unmanaged collision", blocked.stderr)

            forced = self.run_install(home, "--target", "all", "--force")
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
            self.assertTrue((home / ".cursor/skills/poteto-review" / installer.MANAGED_MARKER).is_file())

            # Uninstall removes managed skill and keeps unrelated sibling skills intact.
            uninst = self.run_install(home, "--target", "all", "--uninstall")
            self.assertEqual(uninst.returncode, 0, uninst.stdout + uninst.stderr)
            for rel_host in host_subdirs:
                self.assertFalse((home / rel_host / "poteto-review").exists())
                self.assertTrue((home / rel_host / "other-skill" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
