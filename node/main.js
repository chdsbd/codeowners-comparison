// For each case in a fixture, prints each Node library's verdict, separated
// by spaces, in this order:
//
//   chdsbd's fork of @snyk/github-codeowners, which the VS Code extension uses
//   jjmschofield/github-codeowners, which the fork is based on
//   beaugunderson/codeowners
//   codeowners-deadzone
//   codeowners-audit
//
// A verdict is 1 if the line owns the file, 0 if not, E if the library
// rejects the line, and P if it throws while matching.
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  OwnershipEngine: ForkEngine,
} = require("@snyk/github-codeowners/dist/lib/ownership/OwnershipEngine.js");
const {
  OwnershipEngine,
} = require("github-codeowners/dist/lib/ownership/lib/OwnershipEngine.js");
const Codeowners = require("codeowners");

// Some libraries only read CODEOWNERS from a file, or find it in a directory.
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "compare-"));
const codeowners = path.join(dir, "CODEOWNERS");

function fork(line, file) {
  const engine = ForkEngine.FromCodeownersFile(codeowners);
  if (engine.errors.length || engine.getRules().length === 0) {
    return "E";
  }
  return engine.calcFileOwnership(file) ? "1" : "0";
}

function jjmschofield(line, file) {
  let engine;
  try {
    engine = OwnershipEngine.FromCodeownersFile(codeowners);
  } catch {
    // It throws for lines it rejects.
    return "E";
  }
  if (engine.getRules().length === 0) {
    return "E";
  }
  // It returns the owners, which are also empty when nothing matches, so
  // check whether the rule matched.
  engine.calcFileOwnership(file);
  return engine.getRules()[0].matched > 0 ? "1" : "0";
}

function beaugunderson(line, file) {
  // Every recorded line has owners, so no owners means no match.
  return new Codeowners(dir).getOwner(file).length > 0 ? "1" : "0";
}

function deadzone(lib, line, file) {
  // It leaves out invalid rules when matching.
  const rules = lib
    .parseCodeowners(line + "\n", codeowners)
    .rules.filter((r) => !r.isComment && !r.isBlank && r.isValid);
  if (rules.length === 0) {
    return "E";
  }
  return lib.ownershipForFile(file, rules, false, 1).status === "owned"
    ? "1"
    : "0";
}

function audit(lib, line, file) {
  const rules = lib.parseCodeowners(line + "\n");
  if (rules.length === 0) {
    return "E";
  }
  return lib.findMatchingRule(file, rules) ? "1" : "0";
}

function verdict(f, ...args) {
  try {
    return f(...args);
  } catch {
    return "P";
  }
}

async function main() {
  // jjmschofield/github-codeowners logs each line it rejects.
  console.error = () => {};
  // These two are ES modules.
  const deadzoneLib = await import("codeowners-deadzone");
  const auditLib = await import("codeowners-audit/lib/codeowners-parser.js");
  const cases = fs
    .readFileSync(process.argv[2], "utf8")
    .split("\n")
    .filter((l) => l && !l.startsWith("#"));
  for (const c of cases) {
    const [line, file] = c.split(" | ");
    fs.writeFileSync(codeowners, line + "\n");
    console.log(
      [
        verdict(fork, line, file),
        verdict(jjmschofield, line, file),
        verdict(beaugunderson, line, file),
        verdict(deadzone, deadzoneLib, line, file),
        verdict(audit, auditLib, line, file),
      ].join(" "),
    );
  }
  fs.rmSync(dir, { recursive: true });
}

main();
