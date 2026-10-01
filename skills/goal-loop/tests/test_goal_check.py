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

    def test_failing_pipeline_stage_fails_the_check(self):
        # Regression: without pipefail, `false | cat` logged PASS with exit 0.
        result = self.run_check("false | cat")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stdout.startswith("FAIL"))
        record = (self.root / ".goal/checks.log").read_text().splitlines()[-1]
        self.assertEqual(record.split("\t")[2], "1")

    def test_producer_exit_code_propagates_through_pipeline(self):
        result = self.run_check("(printf data; exit 5) | cat")
        self.assertEqual(result.returncode, 5)

    def test_passing_pipeline_still_passes(self):
        result = self.run_check("printf ok | grep -q ok")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith("PASS"))

    # The exact-value form documented in templates/goal.md and SKILL.md.
    EXACT = 'set -o pipefail; out=$({cmd}) && test "$out" = "expected"'

    def test_exact_value_form_fails_when_command_fails_with_expected_output(self):
        # Regression: `test "$(cmd)" = value` passed when cmd exited 7 but printed value.
        result = self.run_check(self.EXACT.format(cmd="(printf expected; exit 7) | cat"))
        self.assertEqual(result.returncode, 7)
        self.assertTrue(result.stdout.startswith("FAIL"))

    def test_exact_value_form_passes_on_match(self):
        result = self.run_check(self.EXACT.format(cmd="printf expected | cat"))
        self.assertEqual(result.returncode, 0)

    def test_exact_value_form_fails_on_mismatch(self):
        result = self.run_check(self.EXACT.format(cmd="printf other | cat"))
        self.assertEqual(result.returncode, 1)

    def test_documented_exact_value_forms_use_assignment(self):
        # Guard the docs: the unsafe `test "$(` form must not come back.
        root = SCRIPT.parents[1]
        for doc in [root / "SKILL.md", root / "templates" / "goal.md"]:
            for line in doc.read_text(encoding="utf-8").splitlines():
                if line.lstrip().startswith('test "$('):
                    self.fail(f"{doc.name}: unsafe exact-value form: {line}")

    def test_unwritable_log_fails_before_running_the_command(self):
        # Regression: a directory at the log path still printed PASS and exited 0.
        (self.root / ".goal/checks.log").mkdir(parents=True)
        result = self.run_check("touch ran")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("PASS", result.stdout)
        self.assertIn("cannot write evidence log", result.stderr)
        self.assertFalse((self.root / "ran").exists(), "command ran without a log")

    def test_failed_record_write_is_not_reported_as_pass(self):
        # Regression: a write error after the run (disk full) still printed PASS.
        if not Path("/dev/full").exists():
            self.skipTest("/dev/full not available")
        (self.root / ".goal").mkdir()
        (self.root / ".goal/checks.log").symlink_to("/dev/full")
        result = self.run_check("true")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("PASS", result.stdout)
        self.assertIn("could not write evidence record", result.stderr)

    def test_exact_value_form_is_safe_without_the_runner(self):
        # Regression: the documented form relied on the runner's pipefail, so
        # under plain bash (as in /goal) a failing producer still passed.
        cmd = self.EXACT.format(cmd="(printf expected; exit 7) | cat")
        plain = subprocess.run([BASH, "-c", cmd], cwd=self.root, check=False)
        self.assertEqual(plain.returncode, 7)

    def test_documented_pipelines_are_self_contained(self):
        # Every condition containing a pipe, in the docs' code blocks, must
        # enable pipefail itself so it is correct outside the runner.
        root = SCRIPT.parents[1]
        for doc in [root / "SKILL.md", root / "templates" / "goal.md"]:
            in_code = False
            for line in doc.read_text(encoding="utf-8").splitlines():
                if line.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code and " | " in line:
                    self.assertTrue(line.lstrip().startswith("set -o pipefail;"),
                                    f"{doc.name}: pipeline without pipefail: {line}")

    def test_status_is_read_only(self):
        # Regression: --status required write access and created .goal/out.
        self.assertEqual(self.run_check("printf boom; exit 3").returncode, 3)
        shutil.rmtree(self.root / ".goal/out")
        log = self.root / ".goal/checks.log"
        log.chmod(0o444)
        (self.root / ".goal").chmod(0o555)
        self.addCleanup((self.root / ".goal").chmod, 0o755)
        args = [BASH, SCRIPT.as_posix(), "x", "--status"]
        if os.geteuid() == 0:
            # root ignores file modes; run as an unprivileged user instead.
            if shutil.which("runuser") is None:
                self.skipTest("cannot drop root to test read-only access")
            os.chmod(self.root, 0o755)
            args = ["runuser", "-u", "nobody", "--"] + args
        result = subprocess.run(args, cwd=self.root, text=True,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Total runs: 1", result.stdout)
        self.assertFalse((self.root / ".goal/out").exists())

    def test_status_without_log_creates_nothing(self):
        result = self.run_check("x", status=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("No runs recorded", result.stdout)
        self.assertFalse((self.root / ".goal").exists())

    def test_parallel_runs_get_unique_outputs_and_log_records(self):
        # Regression: run ids came from the log length, so concurrent runs
        # shared one output file and one id.
        n = 10
        procs = [
            subprocess.Popen(
                [BASH, SCRIPT.as_posix(), f"sleep 0.2; printf 'run-{i}'; exit 3"],
                cwd=self.root, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            for i in range(n)
        ]
        outs = [p.communicate()[0] for p in procs]
        self.assertTrue(all(p.returncode == 3 for p in procs))

        run_ids = {line.split("run=")[1].split()[0]
                   for out in outs for line in out.splitlines()
                   if line.startswith("FAIL")}
        self.assertEqual(len(run_ids), n)

        out_files = sorted((self.root / ".goal/out").iterdir())
        self.assertEqual(len(out_files), n)
        contents = {f.read_text() for f in out_files}
        self.assertEqual(contents, {f"run-{i}" for i in range(n)})

        records = (self.root / ".goal/checks.log").read_text().splitlines()
        self.assertEqual(len(records), n)
        self.assertTrue(all(len(r.split("\t")) == 4 for r in records))
        self.assertEqual(len({r.split("\t")[3] for r in records}), n)


class HasherFallbackTests(unittest.TestCase):
    """Run the script with a PATH that hides some hashing tools."""

    # Everything the script and its test commands need, minus the hashers.
    BASE_TOOLS = ["bash", "mktemp", "date", "cut", "tail", "awk", "grep",
                  "wc", "cat", "printf", "touch", "mkdir", "flock"]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="goal-check-hash-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for tool in self.BASE_TOOLS:
            real = shutil.which(tool)
            if real:
                (self.bin / tool).symlink_to(real)

    def add_tool(self, name):
        real = shutil.which(name)
        if real is None:
            self.skipTest(f"{name} not installed")
        (self.bin / name).symlink_to(real)

    def run_check(self, command):
        env = {"PATH": str(self.bin), "HOME": str(self.root)}
        return subprocess.run([str(self.bin / "bash"), SCRIPT.as_posix(), command],
                              cwd=self.root, env=env, text=True,
                              capture_output=True, check=False)

    def assert_hashes_track_output(self):
        for i in range(3):
            result = self.run_check(f"printf 'out-{i}'; exit 4")
            self.assertEqual(result.returncode, 4, result.stderr)
        self.assertNotIn("STALLED", result.stdout)
        hashes = [r.split("\t")[3] for r in
                  (self.root / ".goal/checks.log").read_text().splitlines()]
        self.assertEqual(len(hashes), 3)
        self.assertTrue(all(len(h) == 16 for h in hashes))
        self.assertEqual(len(set(hashes)), 3)

    def test_shasum_fallback_when_sha256sum_missing(self):
        # Regression: on stock macOS the empty hash made changed output look stalled.
        self.add_tool("shasum")
        self.assert_hashes_track_output()

    def test_openssl_fallback_when_sha256sum_and_shasum_missing(self):
        self.add_tool("openssl")
        self.assert_hashes_track_output()

    def test_no_hasher_fails_loudly_and_logs_nothing(self):
        result = self.run_check("true")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no SHA-256 tool", result.stderr)
        log = self.root / ".goal/checks.log"
        self.assertEqual(log.read_text() if log.exists() else "", "")


class GitignoreTests(unittest.TestCase):
    REPO = Path(__file__).resolve().parents[3]

    def check_ignored(self, path):
        return subprocess.run(["git", "check-ignore", "-q", path],
                              cwd=self.REPO, check=False).returncode == 0

    def test_raw_evidence_is_ignored(self):
        self.assertTrue(self.check_ignored(".goal/checks.log"))
        self.assertTrue(self.check_ignored(".goal/out/run.abc123"))

    def test_raw_evidence_in_nested_dirs_is_ignored(self):
        # Regression: root-anchored patterns missed runs launched from subdirectories.
        for prefix in ["foo/", "skills/goal-loop/", "a/b/c/"]:
            self.assertTrue(self.check_ignored(prefix + ".goal/checks.log"), prefix)
            self.assertTrue(self.check_ignored(prefix + ".goal/out/run.abc123"), prefix)

    def test_nested_handoff_files_are_tracked(self):
        for prefix in ["foo/", "a/b/c/"]:
            self.assertFalse(self.check_ignored(prefix + ".goal/goal.md"), prefix)
            self.assertFalse(self.check_ignored(prefix + ".goal/progress.md"), prefix)

    def test_handoff_files_are_tracked(self):
        # Regression: ignoring all of .goal/ dropped the committed handoff files.
        self.assertFalse(self.check_ignored(".goal/goal.md"))
        self.assertFalse(self.check_ignored(".goal/progress.md"))


if __name__ == "__main__":
    unittest.main()
