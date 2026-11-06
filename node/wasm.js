// Runs gh-codeowners' WebAssembly build on the repository in the current
// directory: counts the files each rule owns, like `gh-codeowners list`.
//
//     node wasm.js path/to/gh_codeowners_wasm.wasm
//
// WebAssembly can't read git's index, so this lists the files with
// `git ls-files -z`, as a host such as the VS Code extension would.

const { execFileSync } = require("child_process");
const fs = require("fs");

const LOCATIONS = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"];

const wasm = new WebAssembly.Instance(
  new WebAssembly.Module(fs.readFileSync(process.argv[2])),
  {},
).exports;

function write(bytes) {
  const ptr = wasm.alloc(bytes.length);
  new Uint8Array(wasm.memory.buffer, ptr, bytes.length).set(bytes);
  return ptr;
}

const codeowners = fs.readFileSync(LOCATIONS.find((path) => fs.existsSync(path)));
const files = execFileSync("git", ["ls-files", "-z"], { maxBuffer: 1 << 30 });
const status = wasm.count_files(
  write(codeowners),
  codeowners.length,
  write(files),
  files.length,
);
const output = Buffer.from(wasm.memory.buffer, wasm.output_ptr(), wasm.output_len());
if (status !== 0) {
  process.stderr.write(output);
  process.exit(1);
}
process.stdout.write(output);
