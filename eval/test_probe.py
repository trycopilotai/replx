#!/usr/bin/env python3
# eval/test_probe.py
"""Offline tests for eval/probe.py.

Every test runs against a fake OpenAI-compatible server bound
to a loopback ephemeral port, so the suite needs no network,
no API key, and no third-party package. A clean clone can run
it with only python3 installed:

    python3 -m unittest discover -s eval -q

Two of these tests are the reason the harness exists, and
they are the ones to keep working:

    test_held_out_checks_reject_shortcut_patch
    test_repair_prompt_never_reveals_the_oracle

The first proves a passing command is not accepted as a
result. The second proves the harness does not hand over the
answer, which is the defect in the original this was
ported from.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("probe.py")
SPEC = importlib.util.spec_from_file_location("replx_probe", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
PROBE = importlib.util.module_from_spec(SPEC)
sys.modules["replx_probe"] = PROBE
SPEC.loader.exec_module(PROBE)


CALC_CORRECT = "def add(a, b):\n    return a + b\n"

VISIBLE_TEST = (
    "import unittest\n"
    "\n"
    "from calc import add\n"
    "\n"
    "\n"
    "class AddTest(unittest.TestCase):\n"
    "    def test_two_plus_two(self):\n"
    "        self.assertEqual(add(2, 2), 4)\n"
)

# Turns the correct implementation into the seeded defect.
BUG_PATCH = (
    "diff --git a/subject/calc.py b/subject/calc.py\n"
    "--- a/subject/calc.py\n"
    "+++ b/subject/calc.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def add(a, b):\n"
    "-    return a + b\n"
    "+    return a - b\n"
)

# Applied only at verification time. The model never sees it.
HELD_OUT_PATCH = (
    "diff --git a/subject/test_calc_heldout.py"
    " b/subject/test_calc_heldout.py\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/subject/test_calc_heldout.py\n"
    "@@ -0,0 +1,11 @@\n"
    "+import unittest\n"
    "+\n"
    "+from calc import add\n"
    "+\n"
    "+\n"
    "+class AddHeldOutTest(unittest.TestCase):\n"
    "+    def test_one_plus_two(self):\n"
    "+        self.assertEqual(add(1, 2), 3)\n"
    "+\n"
    "+    def test_zero(self):\n"
    "+        self.assertEqual(add(0, 0), 0)\n"
)

# The real repair.
FIX_PATCH = (
    "diff --git a/subject/calc.py b/subject/calc.py\n"
    "--- a/subject/calc.py\n"
    "+++ b/subject/calc.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def add(a, b):\n"
    "-    return a - b\n"
    "+    return a + b\n"
)

# Passes the visible test without fixing anything. This is the
# behaviour the held-out checks exist to catch.
SHORTCUT_PATCH = (
    "diff --git a/subject/calc.py b/subject/calc.py\n"
    "--- a/subject/calc.py\n"
    "+++ b/subject/calc.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def add(a, b):\n"
    "-    return a - b\n"
    "+    return 4\n"
)

# Passes the visible test by removing the assertion. The
# semantic guard pins the assertion text, so this is caught
# even though the held-out checks would also fail it.
GUT_TEST_PATCH = (
    "diff --git a/subject/test_calc.py b/subject/test_calc.py\n"
    "--- a/subject/test_calc.py\n"
    "+++ b/subject/test_calc.py\n"
    "@@ -5,4 +5,4 @@\n"
    "\n"
    " class AddTest(unittest.TestCase):\n"
    "     def test_two_plus_two(self):\n"
    "-        self.assertEqual(add(2, 2), 4)\n"
    "+        pass\n"
)

TARGET_COMMAND = (
    "python3 -m unittest discover -q -s subject -t subject -p 'test_*.py'"
)
HELD_OUT_COMMAND = (
    "python3 -m unittest discover -q -s subject -t subject"
    " -p 'test_*_heldout.py'"
)

GUARD_ASSERTION = "self.assertEqual(add(2, 2), 4)"


def repair_payload(summary: str, diff: str) -> dict:
    """A chat completion whose content is bare repair JSON."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"summary": summary, "unified_diff": diff}
                    ),
                }
            }
        ]
    }


def fenced_repair_payload(summary: str, diff: str) -> dict:
    """The same, wrapped in a markdown fence as models do."""
    inner = json.dumps({"summary": summary, "unified_diff": diff})
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "```json\n" + inner + "\n```",
                }
            }
        ]
    }


def raw_payload(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class FakeCompletionHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.server.requests.append(json.loads(body))  # type: ignore[attr-defined]
        responses = self.server.responses  # type: ignore[attr-defined]
        if responses:
            payload = responses.pop(0)
        else:
            payload = raw_payload("no more scripted responses")
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args: object) -> None:
        return


class FakeCompletionServer:
    """OpenAI-compatible endpoint on a loopback ephemeral port."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []
        self.httpd: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> "FakeCompletionServer":
        self.httpd = HTTPServer(("127.0.0.1", 0), FakeCompletionHandler)
        self.httpd.responses = self.responses  # type: ignore[attr-defined]
        self.httpd.requests = self.requests  # type: ignore[attr-defined]
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True
        )
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        assert self.httpd is not None
        host, port = self.httpd.server_address[:2]
        return "http://%s:%d/v1" % (host, port)

    def prompts(self) -> list[str]:
        found: list[str] = []
        for request in self.requests:
            for message in request.get("messages", []):
                if message.get("role") == "user":
                    found.append(message.get("content", ""))
        return found


def run_git(repo: Path, args: list[str]) -> None:
    subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True
    )


class ProbeTest(unittest.TestCase):
    def make_repo(self, post_checks: bool = True) -> tempfile.TemporaryDirectory:
        """A git repo holding the correct code and the case.

        The defect is not committed. It is applied by
        `bug.patch` at probe time, so the base ref stays green
        and the case is replayable.
        """
        holder = tempfile.TemporaryDirectory()
        root = Path(holder.name)

        subject = root / "subject"
        subject.mkdir()
        (subject / "calc.py").write_text(CALC_CORRECT, encoding="utf-8")
        (subject / "test_calc.py").write_text(VISIBLE_TEST, encoding="utf-8")

        case_dir = root / "eval" / "cases" / "add"
        case_dir.mkdir(parents=True)
        (case_dir / "bug.patch").write_text(BUG_PATCH, encoding="utf-8")
        (case_dir / "held-out.patch").write_text(
            HELD_OUT_PATCH, encoding="utf-8"
        )

        case: dict = {
            "id": "add",
            "description": "add returns a difference instead of a sum",
            "base_ref": "HEAD",
            "bug_patch": "bug.patch",
            "command": TARGET_COMMAND,
            "max_iterations": 3,
            "context_files": ["subject/calc.py", "subject/test_calc.py"],
            "semantic_guard": {
                "required_substrings": {
                    "subject/test_calc.py": [GUARD_ASSERTION]
                }
            },
            "strip_paths": ["eval"],
            "models": [],
        }
        if post_checks:
            case["held_out_patch"] = "held-out.patch"
            case["post_checks"] = [HELD_OUT_COMMAND]
        (case_dir / "case.json").write_text(
            json.dumps(case, indent=2), encoding="utf-8"
        )

        run_git(root, ["init", "-q"])
        run_git(root, ["config", "user.email", "test@example.com"])
        run_git(root, ["config", "user.name", "Test"])
        run_git(root, ["add", "-A"])
        run_git(root, ["commit", "-q", "-m", "base"])
        return holder

    def run_probe(
        self,
        holder: tempfile.TemporaryDirectory,
        server: FakeCompletionServer,
        max_iterations: int = 3,
    ) -> dict:
        root = Path(holder.name)
        case_path = root / "eval" / "cases" / "add" / "case.json"
        case = PROBE.load_case(case_path)
        model = PROBE.ModelSpec(
            label="fake", base_url=server.base_url, model="fake-model"
        )
        out_dir = root / "out"
        return PROBE.run_case(
            root, case, [model], out_dir, max_iterations
        )["results"][0]

    # --- the two tests that carry the harness's thesis ---

    def test_held_out_checks_reject_shortcut_patch(self) -> None:
        """A passing command is a claim, not a result."""
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [repair_payload("hardcode", SHORTCUT_PATCH)] * 3
            ) as server:
                result = self.run_probe(holder, server)

        self.assertFalse(result["solved"])
        self.assertTrue(result["bad_success"])
        self.assertEqual(result["status"], "bad_success")
        # The command really did pass. That is the point.
        self.assertEqual(result["command_passed_at_iteration"], 1)
        self.assertTrue(result["post_checks"])
        self.assertFalse(any(c["passed"] for c in result["post_checks"]))

        # The check must fail on its assertion, not on an
        # import or syntax error. A held-out patch that does
        # not apply cleanly would also report `passed: false`,
        # which would make this test pass for the wrong reason
        # and quietly stop measuring anything.
        output = result["post_checks"][0]["output"]
        self.assertIn("AssertionError", output)
        self.assertNotIn("ImportError", output)
        self.assertNotIn("IndentationError", output)
        self.assertNotIn("SyntaxError", output)

    def test_repair_prompt_never_reveals_the_oracle(self) -> None:
        """The prompt must not contain the answer or the oracle."""
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [repair_payload("hardcode", SHORTCUT_PATCH)] * 3
            ) as server:
                result = self.run_probe(holder, server)
                prompts = server.prompts()

        # Iteration 2 exists only because verification rejected
        # iteration 1, so it is the prompt most at risk of
        # carrying the reason.
        self.assertGreaterEqual(len(prompts), 2)
        self.assertTrue(result["bad_success"])

        # Every line the held-out patch adds, checked against
        # every prompt. This is deliberately mechanical: a
        # future change that starts echoing check output will
        # trip it without anyone having to think of the case.
        held_out_lines = [
            line[1:].strip()
            for line in HELD_OUT_PATCH.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        # Only content unique to the held-out file counts.
        # `import unittest` also appears in the visible test the
        # model is given on purpose, so it is not a secret.
        secrets = [
            line
            for line in held_out_lines
            if len(line) > 3 and line not in VISIBLE_TEST
        ]
        self.assertTrue(secrets, "expected held-out content to check")

        for index, prompt in enumerate(prompts, start=1):
            with self.subTest(prompt=index):
                # The held-out command and its file name.
                self.assertNotIn(HELD_OUT_COMMAND, prompt)
                self.assertNotIn("test_calc_heldout", prompt)
                # Any line of the held-out test body.
                for secret in secrets:
                    self.assertNotIn(secret, prompt)
                # Guard mechanics and the guard substring.
                self.assertNotIn("semantic_guard", prompt)
                self.assertNotIn("required_substrings", prompt)
                # The case description, which names the defect.
                self.assertNotIn("difference instead of a sum", prompt)

        # Naming the mechanism is allowed, because it reveals
        # no content and warns the model that passing is not
        # enough. What is not allowed is saying more than the
        # one fixed sentence, so it appears exactly once.
        self.assertIn(PROBE.OPAQUE_REJECTION, prompts[1])
        self.assertEqual(prompts[1].count(PROBE.OPAQUE_REJECTION), 1)

    def test_case_metadata_is_stripped_from_the_worktree(self) -> None:
        """The model cannot read the oracle off the disk either."""
        holder = self.make_repo()
        with holder:
            root = Path(holder.name)
            case_path = root / "eval" / "cases" / "add" / "case.json"
            case = PROBE.load_case(case_path)
            out_dir = root / "out"
            work_root = out_dir / "work"
            worktree = PROBE.create_case_sandbox(
                root, case, work_root, "probe"
            )

            self.assertFalse((worktree / "eval").exists())
            self.assertTrue((worktree / "subject" / "calc.py").exists())
            self.assertFalse(
                (worktree / "subject" / "test_calc_heldout.py").exists()
            )

            for path in worktree.rglob("*"):
                if not path.is_file():
                    continue
                if ".git" in path.parts:
                    continue
                body = path.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn(HELD_OUT_COMMAND, body)
                self.assertNotIn("AddHeldOutTest", body)

            shutil.rmtree(worktree, ignore_errors=True)

    def test_sandbox_has_no_history_to_read_the_answer_from(self) -> None:
        """The pre-defect code must not be recoverable from git.

        A worktree would carry the parent commit, and the parent
        is the state before the defect was seeded, so `git diff`,
        `git log -p`, and `git show` would each hand over the
        original correct code. The sandbox is a history-free
        export with the defect as its root commit instead. This
        asserts that directly, rather than trusting the
        construction.
        """
        holder = self.make_repo()
        with holder:
            root = Path(holder.name)
            case = PROBE.load_case(
                root / "eval" / "cases" / "add" / "case.json"
            )
            sandbox = PROBE.create_case_sandbox(
                root, case, root / "out" / "work", "probe"
            )

            def git(*args: str) -> str:
                return subprocess.run(
                    ["git", *args],
                    cwd=str(sandbox),
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout

            # Exactly one commit, so there is no parent to diff.
            self.assertEqual(git("rev-list", "--count", "HEAD").strip(), "1")
            self.assertEqual(git("log", "--format=%P").strip(), "")

            # The correct implementation must appear nowhere in
            # any object git can reach, and the working tree must
            # hold the defect rather than the fix.
            correct = "return a + b"
            self.assertNotIn(correct, git("log", "-p", "--all"))
            self.assertNotIn(correct, git("show", "HEAD"))
            self.assertNotIn(correct, git("diff"))
            self.assertNotIn(correct, git("diff", "HEAD"))
            self.assertIn(
                "return a - b",
                (sandbox / "subject" / "calc.py").read_text(),
            )

            # And a clean tree at the start, so the first diff the
            # model is shown contains only its own edits.
            self.assertEqual(git("status", "--porcelain").strip(), "")

            shutil.rmtree(sandbox, ignore_errors=True)

    # --- ported behaviour ---

    def test_successful_one_iteration_patch(self) -> None:
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [repair_payload("fix the operator", FIX_PATCH)]
            ) as server:
                result = self.run_probe(holder, server)

        self.assertTrue(result["solved"])
        self.assertEqual(result["status"], "solved")
        self.assertEqual(result["iterations_used"], 1)
        self.assertFalse(result["bad_success"])
        self.assertTrue(all(c["passed"] for c in result["post_checks"]))
        self.assertGreater(result["final_diff_lines"], 0)

    def test_fenced_json_response_is_parsed(self) -> None:
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [fenced_repair_payload("fix", FIX_PATCH)]
            ) as server:
                result = self.run_probe(holder, server)

        self.assertTrue(result["solved"])
        self.assertEqual(result["invalid_json_count"], 0)

    def test_invalid_json_response_is_recorded(self) -> None:
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [raw_payload("I cannot help with that.")] * 3
            ) as server:
                result = self.run_probe(holder, server)

        self.assertFalse(result["solved"])
        self.assertEqual(result["status"], "unsolved")
        self.assertEqual(result["invalid_json_count"], 3)

    def test_invalid_unified_diff_is_recorded(self) -> None:
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [repair_payload("bad diff", "not a diff at all\n")] * 3
            ) as server:
                result = self.run_probe(holder, server)

        self.assertFalse(result["solved"])
        self.assertEqual(result["invalid_patch_count"], 3)

    def test_max_iteration_failure_is_recorded(self) -> None:
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [repair_payload("no change", FIX_PATCH.replace("+", "+"))]
                + [raw_payload("giving up")] * 5
            ) as server:
                result = self.run_probe(holder, server, max_iterations=2)

        self.assertLessEqual(result["iterations_used"], 2)

    def test_semantic_guard_rejects_a_gutted_test(self) -> None:
        """Removing the assertion passes the command and fails."""
        holder = self.make_repo()
        with holder:
            with FakeCompletionServer(
                [repair_payload("skip it", GUT_TEST_PATCH)] * 3
            ) as server:
                result = self.run_probe(holder, server)

        self.assertFalse(result["solved"])
        self.assertTrue(result["bad_success"])
        self.assertTrue(result["guard_failed"])

    def test_endpoint_failure_is_reported_not_raised(self) -> None:
        holder = self.make_repo()
        with holder:
            root = Path(holder.name)
            case_path = root / "eval" / "cases" / "add" / "case.json"
            case = PROBE.load_case(case_path)
            # Port 1 is not listening.
            model = PROBE.ModelSpec(
                label="dead", base_url="http://127.0.0.1:1/v1", model="none"
            )
            report = PROBE.run_case(root, case, [model], root / "out", 2)

        result = report["results"][0]
        self.assertEqual(result["status"], "endpoint-error")
        self.assertFalse(result["solved"])

    # --- input validation ---

    def test_post_checks_without_a_held_out_patch_is_rejected(self) -> None:
        """Otherwise the checks sit in the worktree, readable."""
        holder = tempfile.TemporaryDirectory()
        with holder:
            case_path = Path(holder.name) / "case.json"
            case_path.write_text(
                json.dumps(
                    {
                        "id": "x",
                        "base_ref": "HEAD",
                        "bug_patch": "bug.patch",
                        "command": "true",
                        "post_checks": ["echo hi"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(PROBE.ProbeError) as caught:
                PROBE.load_case(case_path)
            self.assertIn("held_out_patch", str(caught.exception))

    def test_shipped_case_runs_end_to_end(self) -> None:
        """The committed case works, not just an inline fixture.

        Exercises the real `bug.patch`, `held-out.patch`, and
        `case.json` against this repository, so a case that was
        edited without being re-verified fails here.
        """
        shipped_dir = Path(__file__).parent / "cases" / "chunk-off-by-one"
        case = PROBE.load_case(shipped_dir / "case.json")
        repo_root = PROBE.find_repo_root(shipped_dir)

        fix = (
            "diff --git a/probe_subject/chunker.py"
            " b/probe_subject/chunker.py\n"
            "--- a/probe_subject/chunker.py\n"
            "+++ b/probe_subject/chunker.py\n"
            "@@ -12,4 +12,4 @@\n"
            "     chunks = []\n"
            "     for start in range(0, len(items), size):\n"
            "-        chunks.append(list(items[start : start + size - 1]))\n"
            "+        chunks.append(list(items[start : start + size]))\n"
            "     return chunks\n"
        )

        with tempfile.TemporaryDirectory() as out_root:
            with FakeCompletionServer(
                [repair_payload("use the full width", fix)]
            ) as server:
                model = PROBE.ModelSpec(
                    label="shipped",
                    base_url=server.base_url,
                    model="fake-model",
                )
                report = PROBE.run_case(
                    repo_root, case, [model], Path(out_root), 2
                )

        result = report["results"][0]
        self.assertEqual(
            result["status"], "solved", msg=result["error_message"]
        )
        self.assertEqual(result["command_passed_at_iteration"], 1)
        self.assertTrue(result["post_checks"])
        self.assertTrue(all(c["passed"] for c in result["post_checks"]))
        self.assertFalse(result["guard_failed"])

    def test_run_manifest_matches_the_shipped_protocol(self) -> None:
        """The committed transcript must cite the live protocol.

        A transcript's manifest is the only thing making it
        checkable rather than decorative, and a manifest goes
        stale the moment the protocol is reformatted. Editing
        prose is a normal thing to do; noticing that it
        invalidated a hash four files away is not, so this
        asserts it instead of relying on anyone remembering.
        """
        import hashlib
        import re

        root = Path(__file__).resolve().parent.parent
        protocol = root / "skill" / "SKILL.md"
        transcript = root / "examples" / "smoke-oracle-run.md"

        actual = hashlib.sha256(protocol.read_bytes()).hexdigest()
        text = transcript.read_text(encoding="utf-8")

        cited = re.search(
            r"`skill/SKILL\.md`,\s*sha256\s*`([0-9a-f]+)", text
        )
        self.assertIsNotNone(
            cited, "the run manifest does not cite a protocol sha256"
        )
        assert cited is not None
        prefix = cited.group(1)
        self.assertTrue(
            actual.startswith(prefix),
            "run manifest is stale: it cites %s… but skill/SKILL.md "
            "hashes to %s…. Re-run the example against the current "
            "protocol and update the manifest; do not just edit the "
            "hash, because the transcript claims to be unedited output "
            "of the protocol it names." % (prefix, actual[: len(prefix)]),
        )

    def test_shipped_case_loads_and_declares_held_out_checks(self) -> None:
        """The case committed to this repo is valid."""
        shipped = (
            Path(__file__).parent / "cases" / "chunk-off-by-one" / "case.json"
        )
        case = PROBE.load_case(shipped)
        self.assertEqual(case.case_id, "chunk-off-by-one")
        self.assertTrue(case.post_checks)
        self.assertIsNotNone(case.held_out_patch)
        assert case.held_out_patch is not None
        self.assertTrue(case.held_out_patch.exists())
        self.assertTrue(case.bug_patch.exists())
        self.assertIn("eval", case.strip_paths)


if __name__ == "__main__":
    unittest.main()
