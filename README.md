# codeowners-comparison

How CODEOWNERS libraries and tools match files, compared with GitHub itself, and how fast they are on real repositories.

[`data/github.txt`](data/github.txt) records which files GitHub says a CODEOWNERS line owns, for 4,157 lines and paths. Each case is one line, a path and GitHub's answer:

```
<CODEOWNERS line> | <file path> | <1 if the line owns the file, else 0>
```

They were recorded from a private test repository, by reading which rule GitHub shows as owning each file. The cases cover the parts of GitHub's matching that its docs don't spell out, like `!`, `?`, `**`, escapes, brackets and comments.

[`examples/CODEOWNERS`](examples/CODEOWNERS) is an example file with a commented rule for each of those quirks, and notes on which libraries get each one wrong.

## Results

| Library | Language | Agrees with GitHub |
|---|---|---|
| [gh-codeowners](https://github.com/chdsbd/gh-codeowners) | Rust | 4157/4157 |
| [sbdchd/codeowners](https://github.com/sbdchd/codeowners) | Python | 4039/4157 |
| [hmarr/codeowners](https://github.com/hmarr/codeowners) | Go | 4021/4157 |
| [codeowners-tool](https://github.com/jordonpeterson/codeowners-tool) | Go | 4021/4157 |
| [codeowners-deadzone](https://www.npmjs.com/package/codeowners-deadzone) | Node | 4013/4157 |
| [chdsbd/github-codeowners](https://github.com/chdsbd/github-codeowners), a fork of `@snyk/github-codeowners` | Node | 4005/4157 |
| [codeowners-rs](https://crates.io/crates/codeowners-rs) | Rust | 4004/4157 |
| [jjmschofield/github-codeowners](https://github.com/jjmschofield/github-codeowners), which the fork is based on | Node | 4004/4157 |
| [softprops/codeowners](https://crates.io/crates/codeowners) | Rust | 3993/4157 |
| [codeowners-audit](https://github.com/watson/codeowners-audit) | Node | 3991/4157 |
| [codeowners-validator](https://github.com/mszostok/codeowners-validator) | Go | 3990/4157 |
| [beaugunderson/codeowners](https://github.com/beaugunderson/codeowners) | Node | 3976/4157 |

## Running it

```bash
uv run compare.py
```

It prints how often each library agrees with GitHub, and the cases where it doesn't, grouped by CODEOWNERS line. `--limit N` sets how many lines to show for each library. It needs cargo, go and npm on `PATH`, and skips a library whose tool is missing, unless you pass `--require-all`. It exits with status 1 if gh-codeowners disagrees with GitHub.

Each library has a small driver that prints a verdict for every case: `1` if the line owns the file, `0` if not, `E` if the library rejects the line, and `P` if it panics. A rejected line counts as owning nothing, like on GitHub.

- [`rust/`](rust) runs gh-codeowners, codeowners-rs and softprops/codeowners.
- [`go/`](go) runs hmarr/codeowners.
- [`node/`](node) runs the `@snyk/github-codeowners` fork, jjmschofield/github-codeowners, beaugunderson/codeowners, codeowners-deadzone and codeowners-audit.
- [`clis.py`](clis.py) runs codeowners-validator and codeowners-tool, which are only usable as commands. It builds them with `go install`, then runs them on small repositories made from the cases. codeowners-validator's `files` check reports rules that match no files, so each case gets a repository with just that file. codeowners-tool's `snapshot` lists each committed file's owners, so each CODEOWNERS line gets a committed repository with its paths.
- sbdchd/codeowners runs inside `compare.py`.

gh-codeowners is private for now, so Cargo fetches it with the `git` command, using your git credentials. In CI, the `GH_CODEOWNERS_TOKEN` secret needs read access to it.
