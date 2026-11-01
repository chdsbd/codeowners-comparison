# codeowners-comparison

How CODEOWNERS libraries match files, compared with GitHub itself.

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
| [chdsbd/github-codeowners](https://github.com/chdsbd/github-codeowners), a fork of `@snyk/github-codeowners` | Node | 4005/4157 |
| [codeowners-rs](https://crates.io/crates/codeowners-rs) | Rust | 4004/4157 |

## Running it

```bash
uv run compare.py
```

It prints how often each library agrees with GitHub, and the cases where it doesn't, grouped by CODEOWNERS line. `--limit N` sets how many lines to show for each library. It needs cargo, go and npm on `PATH`, and skips a library whose tool is missing, unless you pass `--require-all`. It exits with status 1 if gh-codeowners disagrees with GitHub.

Each library has a small driver that prints a verdict for every case: `1` if the line owns the file, `0` if not, `E` if the library rejects the line, and `P` if it panics. A rejected line counts as owning nothing, like on GitHub.

- [`rust/`](rust) runs gh-codeowners and codeowners-rs.
- [`go/`](go) runs hmarr/codeowners.
- [`node/`](node) runs the `@snyk/github-codeowners` fork.
- sbdchd/codeowners runs inside `compare.py`.

gh-codeowners is private for now, so Cargo fetches it with the `git` command, using your git credentials. In CI, the `GH_CODEOWNERS_TOKEN` secret needs read access to it.
