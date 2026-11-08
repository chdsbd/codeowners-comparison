# /// script
# requires-python = ">=3.12"
# ///
"""Time CODEOWNERS tools on real repositories.

Each tool does its closest equivalent of counting ownership for a whole
repository: listing every file's owner, finding unowned files, or finding
rules that match nothing. The repositories are:

- getsentry/sentry, with its own .github/CODEOWNERS

It is fetched without file contents, then checked out as empty files,
which is all the tools read.

    uv run bench.py --gh-codeowners PATH [--runs N] [--timeout SECONDS]

Needs git, cargo, go and npm on PATH. Tools are installed into a temporary
directory at pinned versions; `node/` must have its dependencies installed
(`npm ci` there). Prints a Markdown table of median times.
"""

import argparse
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
NODE = HERE / "node" / "node_modules"

CODEOWNERS_LOCATIONS = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]

REPOS = {
    "sentry": (
        "https://github.com/getsentry/sentry",
        "063a6cb279fc42752e31ee200331f553f35ec26f",
    ),
}


@dataclass
class Tool:
    name: str
    does: str
    command: list[str]
    # Exit codes for a finished run. Some tools exit non-zero when they find
    # problems.
    ok: set[int] = field(default_factory=lambda: {0})
    env: dict[str, str] = field(default_factory=dict)


def sh(args: list[str], cwd: Path | None = None, **kwargs) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, stdout=subprocess.PIPE, text=True, **kwargs
    ).stdout


def fetch(name: str, work: Path) -> Path:
    """The repository at its pinned commit, with every file empty."""
    url, commit = REPOS[name]
    repo = work / name
    if not (repo / ".git").exists():
        checkout(name, url, commit, repo, work)
    # The tools read CODEOWNERS itself, so it needs its contents.
    for location in CODEOWNERS_LOCATIONS:
        tracked = sh(["git", "ls-files", location], repo).strip()
        if tracked:
            (repo / location).write_bytes(
                subprocess.run(
                    ["git", "show", f"HEAD:{location}"],
                    cwd=repo,
                    check=True,
                    stdout=subprocess.PIPE,
                ).stdout
            )
    return repo


def checkout(name: str, url: str, commit: str, repo: Path, work: Path) -> None:
    repo.mkdir(parents=True)
    sh(["git", "init", "-q"], repo)
    sh(["git", "fetch", "-q", "--depth", "1", "--filter=blob:none", url, commit], repo)
    sh(["git", "read-tree", commit], repo)
    sh(["git", "update-ref", "HEAD", commit], repo)
    for line in sh(["git", "ls-files", "-s"], repo).splitlines():
        mode, _, _, path = line.split(maxsplit=3)
        if mode == "160000":  # Submodules aren't files.
            continue
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).touch()
    (work / f"{name}.paths").write_text(sh(["git", "ls-files"], repo))


def install(bin_dir: Path) -> dict[str, Path]:
    cargo = ["cargo", "install", "-q", "--locked", "--root"]
    sh(
        cargo
        + [
            str(bin_dir / "rs"),
            "--git",
            "https://github.com/hmarr/codeowners-rs",
            "--rev",
            "bf0ecb4",
        ]
    )
    for package in [
        "github.com/hmarr/codeowners/cmd/codeowners@v1.2.1",
        "github.com/mszostok/codeowners-validator@v0.7.4",
        "github.com/jordonpeterson/codeowners-tool/cmd/codeowners-tool@v1.0.1",
    ]:
        sh(["go", "install", package], env=os.environ | {"GOBIN": str(bin_dir / "go")})
    return {
        "codeowners-rs": bin_dir / "rs" / "bin" / "codeowners",
        "hmarr": bin_dir / "go" / "codeowners",
        "validator": bin_dir / "go" / "codeowners-validator",
        "codeowners-tool": bin_dir / "go" / "codeowners-tool",
    }


def tools(bins: dict[str, Path], gh_codeowners: Path) -> list[Tool]:
    node = shutil.which("node") or "node"
    return [
        Tool(
            "gh-codeowners `list`",
            "files each rule owns",
            [str(gh_codeowners), "list"],
        ),
        Tool(
            "gh-codeowners `check --unused`",
            "problems, including rules matching nothing",
            [str(gh_codeowners), "check", "--unused"],
            ok={0, 1},
        ),
        Tool(
            "codeowners-rs, file list from git ls-files",
            "owner of each file",
            ["sh", "-c", f"git ls-files | {bins['codeowners-rs']} -p /dev/stdin"],
        ),
        Tool(
            "codeowners-rs, walking", "owner of each file", [str(bins["codeowners-rs"])]
        ),
        Tool(
            "codeowners-validator",
            "rules matching no files",
            [str(bins["validator"])],
            {0, 3},
            {"REPOSITORY_PATH": ".", "CHECKS": "files"},
        ),
        Tool("hmarr/codeowners", "owner of each file", [str(bins["hmarr"])]),
        Tool(
            "codeowners-tool audit",
            "12 checks, incl. dead and shadowed rules",
            [str(bins["codeowners-tool"]), "audit", "--format", "text", "--repo", "."],
            {0, 4},
        ),
        Tool(
            "codeowners-audit",
            "unowned files and more",
            [
                node,
                str(NODE / "codeowners-audit" / "report.js"),
                ".",
                "--no-report",
                "--no-open",
                "-y",
            ],
            {0, 1},
        ),
        Tool(
            "snyk fork audit",
            "owner of each file",
            [
                node,
                str(NODE / "@snyk" / "github-codeowners" / "dist" / "cli.js"),
                "audit",
                "-d",
                ".",
                "-o",
                "jsonl",
            ],
        ),
        Tool(
            "beaugunderson/codeowners audit",
            "owner of each file and directory",
            [node, str(NODE / "codeowners" / "index.js"), "audit"],
        ),
        Tool(
            "jjmschofield/github-codeowners audit",
            "owner of each file",
            [
                node,
                str(NODE / "github-codeowners" / "dist" / "cli.js"),
                "audit",
                "-d",
                ".",
            ],
        ),
        Tool(
            "codeowners-deadzone scan",
            "coverage, unused and shadowed rules",
            [
                node,
                str(NODE / "codeowners-deadzone" / "dist" / "cli.js"),
                "scan",
                ".",
                "--format",
                "json",
            ],
        ),
    ]


def run(tool: Tool, repo: Path, timeout: float) -> tuple[float | None, str]:
    """Seconds taken, or None and why it didn't finish."""
    start = time.perf_counter()
    try:
        result = subprocess.run(
            tool.command,
            check=False,
            cwd=repo,
            env=os.environ | tool.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"over {timeout:.0f} s"
    elapsed = time.perf_counter() - start
    if result.returncode in tool.ok:
        return elapsed, ""
    if "heap out of memory" in result.stderr:
        return None, f"out of memory after {elapsed:.0f} s"
    error = result.stderr.strip().splitlines()[0][:60] if result.stderr.strip() else ""
    return None, f"failed: exit {result.returncode} {error}".strip()


def show(seconds: float) -> str:
    return f"{seconds * 1000:.0f} ms" if seconds < 10 else f"{seconds:.0f} s"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gh-codeowners", type=Path, required=True, help="gh-codeowners binary"
    )
    parser.add_argument(
        "--runs", type=int, default=11, help="runs for tools under 10 s"
    )
    parser.add_argument(
        "--timeout", type=float, default=900, help="seconds before giving up on a run"
    )
    parser.add_argument(
        "--work", type=Path, help="directory to keep repositories in between runs"
    )
    args = parser.parse_args()

    work = args.work or Path(tempfile.mkdtemp(prefix="bench-"))
    bin_dir = Path(tempfile.mkdtemp(prefix="bench-bin-"))
    try:
        bins = install(bin_dir)
        repos = {name: fetch(name, work) for name in REPOS}
        for name, repo in repos.items():
            # Shows the rule and file counts, so a missing or empty
            # CODEOWNERS is obvious.
            summary = sh([str(args.gh_codeowners.resolve()), "list"], repo)
            print(f"{name}: {summary.splitlines()[0]}\n")
        print(
            f"{os.cpu_count()} CPUs. Medians of up to {args.runs} runs; tools over 10 s ran once.\n"
        )
        header = (
            "| Tool | What it computes | "
            + " | ".join(
                f"{name} ({len((work / f'{name}.paths').read_text().splitlines()):,} files)"
                for name in repos
            )
            + " |"
        )
        print(header)
        print("|---|---|" + "---|" * len(repos))
        per_repo = {name: tools(bins, args.gh_codeowners.resolve()) for name in repos}
        for i, tool in enumerate(per_repo["sentry"]):
            cells = []
            for name, repo in repos.items():
                here = per_repo[name][i]
                first, why = run(here, repo, args.timeout)
                if first is None:
                    cells.append(why)
                    continue
                times = [first]
                if first < 10:
                    for _ in range(args.runs - 1):
                        seconds, why = run(here, repo, args.timeout)
                        if seconds is None:
                            break
                        times.append(seconds)
                cells.append(why or show(statistics.median(times)))
            print(
                f"| {tool.name} | {tool.does} | " + " | ".join(cells) + " |", flush=True
            )
    finally:
        shutil.rmtree(bin_dir)
        if not args.work:
            shutil.rmtree(work)


if __name__ == "__main__":
    main()
