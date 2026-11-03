"""Count gate for tests/run-tests.ps1. Spawns pwsh; never discovers this suite again."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "run-tests.ps1"
ZERO = ROOT / "tests" / "fixtures" / "zero_tests"

PY_OK = """\
test_a (example.T.test_a) ... ok
test_b (example.T.test_b) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK
"""

PY_ZERO = """\
----------------------------------------------------------------------
Ran 0 tests in 0.000s

NO TESTS RAN
"""

PY_FAIL = """\
test_a (example.T.test_a) ... FAIL
test_b (example.T.test_b) ... ERROR

----------------------------------------------------------------------
Ran 4 tests in 0.010s

FAILED (failures=1, errors=2)
"""

NODE_OK = """\
TAP version 13
1..2
ok 1 - one
ok 2 - two
# tests 2
# suites 0
# pass 2
# fail 0
# cancelled 0
# skipped 0
# todo 0
"""

NODE_SPEC = """\
\u2139 tests 2
\u2139 suites 0
\u2139 pass 2
\u2139 fail 0
\u2139 cancelled 0
\u2139 skipped 0
\u2139 todo 0
"""

NODE_ZERO = """\
# tests 0
# suites 0
# pass 0
# fail 0
# cancelled 0
# skipped 0
# todo 0
"""

NODE_FAIL = """\
# tests 3
# suites 0
# pass 1
# fail 2
# cancelled 0
# skipped 0
# todo 0
"""

# Real spec lines from Node 24.20.0 on this repo: a comment-only entry is
# reported as one passing test whose name is the relative directory.
NODE_EMPTY_SPEC = """\
\u2714 tests\\js (31.9217ms)
\u2139 tests 1
\u2139 suites 0
\u2139 pass 1
\u2139 fail 0
\u2139 cancelled 0
\u2139 skipped 0
\u2139 todo 0
\u2139 duration_ms 37.1849
"""

# Real 11-test spec summary from `node --test tests/js/` (plain titles, no entry path).
NODE_ELEVEN = """\
\u2714 browser tiers match the shared fixture (1.3118ms)
\u2714 background stars fail the gate check (0.1307ms)
\u2714 missing mass on a planet host can be a gate (0.127ms)
\u2714 no planets and no mass is not a gate (0.0912ms)
\u2714 companion host at the default mass floor is a gate (0.1294ms)
\u2714 map legend and traces name the three tiers (0.1749ms)
\u2714 tests/js entry imports every test file (1.0562ms)
\u2714 fixture with an unimported test file is a failure (0.5959ms)
\u2714 entry that requires a missing file is a failure (0.5278ms)
\u2714 missing package.json is a failure (0.2028ms)
\u2714 package.json without main is a failure (0.2421ms)
\u2139 tests 11
\u2139 suites 0
\u2139 pass 11
\u2139 fail 0
\u2139 cancelled 0
\u2139 skipped 0
\u2139 todo 0
\u2139 duration_ms 54.7878
"""

EMPTY = ROOT / "tests" / "fixtures" / "empty_entry"
_EMPTY_JS_TAP = str(EMPTY / "tests" / "js").replace("\\", "\\\\")
NODE_EMPTY_TAP = f"""\
TAP version 13
1..1
ok 1 - {_EMPTY_JS_TAP}
# tests 1
# suites 0
# pass 1
# fail 0
# cancelled 0
# skipped 0
# todo 0
"""


def _pack(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")


def _run(args: list[str], timeout: int = 25) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(RUNNER), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return completed


def _parse(kind: str, text: str) -> subprocess.CompletedProcess[str]:
    return _run(["-ParseOnly", "-Kind", kind, "-Text", _pack(text)])


class RunnerZeroGateTests(unittest.TestCase):
    def test_parse_normal_python(self) -> None:
        result = _parse("python", PY_OK)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("python: ran 2, failed 0", result.stdout)

    def test_parse_normal_node_tap(self) -> None:
        result = _parse("node", NODE_OK)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("node: ran 2, failed 0", result.stdout)

    def test_parse_normal_node_spec(self) -> None:
        result = _parse("node", NODE_SPEC)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("node: ran 2, failed 0", result.stdout)

    def test_parse_python_failures(self) -> None:
        result = _parse("python", PY_FAIL)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("python: ran 4, failed 3", result.stdout)

    def test_parse_node_failures(self) -> None:
        result = _parse("node", NODE_FAIL)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("node: ran 3, failed 2", result.stdout)

    def test_parse_python_zero(self) -> None:
        result = _parse("python", PY_ZERO)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("python: ran 0, failed 0", result.stdout)

    def test_parse_node_zero(self) -> None:
        result = _parse("node", NODE_ZERO)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("node: ran 0, failed 0", result.stdout)

    def test_parse_node_empty_entry_spec(self) -> None:
        result = _parse("node", NODE_EMPTY_SPEC)
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("node: ran 0, failed 0", combined)
        self.assertIn("Node entry registered no tests", combined)

    def test_parse_node_empty_entry_tap(self) -> None:
        result = _parse("node", NODE_EMPTY_TAP)
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("node: ran 0, failed 0", combined)
        self.assertIn("Node entry registered no tests", combined)

    def test_parse_node_eleven_real_tests(self) -> None:
        result = _parse("node", NODE_ELEVEN)
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("node: ran 11, failed 0", combined)
        self.assertNotIn("Node entry registered no tests", combined)

    def test_parse_empty(self) -> None:
        result = _parse("python", "")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("python: PARSE_ERROR", result.stdout)

    def test_parse_garbage(self) -> None:
        result = _parse("node", "this is not a test report")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("node: PARSE_ERROR", result.stdout)

    def test_zero_fixture_exits_nonzero(self) -> None:
        result = _run(["-Root", str(ZERO), "-Only", "all"], timeout=25)
        combined = result.stdout + "\n" + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("python: ran 0, failed 0", combined)
        self.assertIn("node: ran 0, failed 0", combined)

    def test_empty_entry_fixture_exits_nonzero(self) -> None:
        result = _run(["-Root", str(EMPTY), "-Only", "all"], timeout=40)
        combined = result.stdout + "\n" + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("python: ran 1, failed 0", combined)
        self.assertIn("node: ran 0, failed 0", combined)
        self.assertIn("Node entry registered no tests", combined)


if __name__ == "__main__":
    unittest.main()
