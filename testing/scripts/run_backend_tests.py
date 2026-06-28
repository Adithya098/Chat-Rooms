import argparse
import re
import subprocess
import sys
from pathlib import Path

SUMMARY_RE = re.compile(
    r"^(?P<passed>\d+) passed(?:, (?P<failed>\d+) failed)? in (?P<duration>[\d.]+s)\s*$",
    re.MULTILINE,
)

# Match pytest's default terminal green/red summary styling.
_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _rewrite_pytest_summary(stdout: str, total: int) -> str:
    """Rewrite `10 passed in 0.08s` as green `10/10 passed in 0.08s`."""

    def repl(match: re.Match[str]) -> str:
        passed = int(match.group("passed"))
        failed = int(match.group("failed") or 0)
        duration = match.group("duration")
        if failed:
            return f"{_RED}{passed}/{total} passed, {failed} failed in {duration}{_RESET}"
        return f"{_GREEN}{passed}/{total} passed in {duration}{_RESET}"

    return SUMMARY_RE.sub(repl, stdout)


def _collect_test_ids(python_exe: str, repo_root: Path, targets: list[str], passthrough: list[str]) -> list[str]:
    collect_cmd = [
        python_exe,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "--override-ini",
        "addopts=",
    ]
    collect_cmd.extend(targets)
    collect_cmd.extend(passthrough)
    proc = subprocess.run(
        collect_cmd,
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if "::" in line]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backend tests from testing/backend.")
    parser.add_argument("--api", action="store_true", help="Run API tests only.")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only.")
    args, passthrough = parser.parse_known_args()

    repo_root = Path(__file__).resolve().parents[2]
    backend_tests = repo_root / "testing" / "backend"

    test_targets: list[str] = []
    if args.api and not args.unit:
        test_targets.append(str(backend_tests / "api"))
    elif args.unit and not args.api:
        test_targets.append(str(backend_tests / "unit"))
    else:
        test_targets.append(str(backend_tests))

    passed_test_ids = _collect_test_ids(sys.executable, repo_root, test_targets, passthrough)

    cmd = [sys.executable, "-m", "pytest", "--color=yes"]
    cmd.extend(test_targets)
    cmd.extend(passthrough)
    proc = subprocess.run(cmd, cwd=str(repo_root), check=False, capture_output=True, text=True)
    stdout = proc.stdout
    if proc.returncode == 0 and passed_test_ids:
        stdout = _rewrite_pytest_summary(stdout, len(passed_test_ids))
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    result = proc.returncode

    if result == 0 and passed_test_ids:
        print("\nPassed tests:")
        for test_id in passed_test_ids:
            print(f"- {test_id}")

    return result


if __name__ == "__main__":
    raise SystemExit(main())
