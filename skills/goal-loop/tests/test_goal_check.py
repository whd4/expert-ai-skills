"""Exercise the real Bash check runner with isolated completion commands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "goal-check.sh"
BASH = ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt"
        else shutil.which("bash"))


class GoalCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="goal-check-qa-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_check(self, command, status=False):
        args = [BASH, SCRIPT.as_posix(), command]
        if status:
            args.append("--status")
        return subprocess.run(args, cwd=self.root, text=True,
                              encoding="utf-8", capture_output=True, check=False)

    def test_multiline_and_tab_commands_are_single_log_records(self):
        command = "printf 'first\\n'\nprintf '\tsecond\\n'; exit 7"
        result = self.run_check(command)
        self.assertEqual(result.returncode, 7)
        records = (self.root / ".goal/checks.log").read_text().splitlines()
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0].split("\t")), 4)
        self.assertEqual(records[0].split("\t")[2], "7")
        self.assertIn("Total runs: 1", self.run_check(command, status=True).stdout)

    def test_repeated_success_is_complete_not_stalled(self):
        for _ in range(3):
            self.assertEqual(self.run_check("true").returncode, 0)
        self.assertNotIn("STALLED", self.run_check("true", status=True).stdout)

    def test_identical_failure_stalls_and_changed_result_recovers(self):
        for _ in range(3):
            result = self.run_check("printf boom; exit 7")
            self.assertEqual(result.returncode, 7)
        self.assertIn("STALLED", result.stdout)
        result = self.run_check("printf changed; exit 7")
        self.assertNotIn("STALLED", result.stdout)

    def test_changed_command_is_not_a_stall(self):
        for command in ["true; exit 7", "printf ''; exit 7", "exit 7"]:
            result = self.run_check(command)
        self.assertNotIn("STALLED", result.stdout)


    def test_changed_exit_code_is_not_a_stall(self):
        for code in [1, 2, 3]:
            (self.root / "code").write_text(str(code), encoding="utf-8")
            result = self.run_check('exit $(cat code)')
            self.assertEqual(result.returncode, code)
        self.assertNotIn("STALLED", result.stdout)


if __name__ == "__main__":
    unittest.main()
