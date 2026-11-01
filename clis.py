"""Drivers for CODEOWNERS tools that are only usable as commands.

Each driver builds its tool with `go install` at a pinned version, then runs
it on small repositories made from the fixture's cases, and returns a
verdict for each case: 1 if the line owns the file, 0 if not, E if the tool
rejects the line.
"""

import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VALIDATOR = "github.com/mszostok/codeowners-validator@v0.7.4"
CODEOWNERS_TOOL = "github.com/jordonpeterson/codeowners-tool/cmd/codeowners-tool@v1.0.1"

Case = tuple[str, str, str]


def go_install(package: str, bin_dir: Path) -> Path:
    subprocess.run(
        ["go", "install", package],
        check=True,
        env=os.environ | {"GOBIN": str(bin_dir)},
    )
    return bin_dir / package.split("@")[0].rsplit("/", 1)[1]


def make_repo(root: Path, line: str, paths: list[str]) -> None:
    """A directory with `line` as its CODEOWNERS and an empty file at each path."""
    (root / ".github").mkdir(parents=True)
    (root / ".github" / "CODEOWNERS").write_text(line + "\n", encoding="utf-8")
    for path in paths:
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).touch()


def validator(cases: list[Case], bin_dir: Path) -> list[str]:
    """codeowners-validator's `files` check, which reports rules that match
    no files. With one rule and one file, that says whether the rule matches
    the file."""
    tool = go_install(VALIDATOR, bin_dir)

    def verdict(case: Case) -> str:
        line, path, _ = case
        with tempfile.TemporaryDirectory() as tmp:
            make_repo(Path(tmp), line, [path])
            result = subprocess.run(
                [tool],
                check=False,
                env=os.environ | {"REPOSITORY_PATH": tmp, "CHECKS": "files"},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        if result.returncode == 0:
            return "1"
        if "does not match any files" in result.stdout:
            return "0"
        return "E"

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        return list(pool.map(verdict, cases))


def without_conflicts(paths: list[str]) -> list[list[str]]:
    """Split paths into groups where no path is a directory of another, so
    each group can be files in one repository."""
    groups: list[list[str]] = []
    for path in paths:
        for group in groups:
            if not any(
                other.startswith(path + "/") or path.startswith(other + "/")
                for other in group
            ):
                group.append(path)
                break
        else:
            groups.append([path])
    return groups


def codeowners_tool(cases: list[Case], bin_dir: Path) -> list[str]:
    """codeowners-tool's `snapshot`, which lists the owners of each tracked
    file. It only reads committed files, so each repository is committed."""
    tool = go_install(CODEOWNERS_TOOL, bin_dir)
    by_line: dict[str, list[str]] = {}
    for line, path, _ in cases:
        by_line.setdefault(line, []).append(path)
    git = ["git", "-c", "user.name=compare", "-c", "user.email=compare@example.com"]

    def verdicts(line: str, paths: list[str]) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            make_repo(Path(tmp), line, paths)
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "compare"]):
                subprocess.run(git + args, cwd=tmp, check=True)
            result = subprocess.run(
                [tool, "snapshot", "--repo", tmp],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        if result.returncode != 0:
            return {path: "E" for path in paths}
        ownership = json.loads(result.stdout)["ownership"]
        return {path: "1" if ownership.get(path) else "0" for path in paths}

    jobs = [
        (line, group)
        for line, paths in by_line.items()
        for group in without_conflicts(list(dict.fromkeys(paths)))
    ]
    results: dict[tuple[str, str], str] = {}
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        for (line, _), found in zip(jobs, pool.map(lambda job: verdicts(*job), jobs)):
            for path, verdict in found.items():
                results[(line, path)] = verdict
    return [results[(line, path)] for line, path, _ in cases]


def collect(cases: list[Case]) -> dict[str, list[str]]:
    bin_dir = Path(tempfile.mkdtemp(prefix="compare-bin-"))
    try:
        return {
            "codeowners-validator": validator(cases, bin_dir),
            "codeowners-tool": codeowners_tool(cases, bin_dir),
        }
    finally:
        shutil.rmtree(bin_dir)
