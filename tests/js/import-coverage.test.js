const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const JS_DIR = __dirname;
const FIXTURES = path.join(__dirname, "..", "fixtures");

function norm(filePath) {
  const resolved = path.resolve(filePath);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function relPosix(dir, filePath) {
  return path.relative(dir, filePath).split(path.sep).join("/");
}

function resolveRelative(fromDir, spec) {
  const base = path.resolve(fromDir, spec);
  const candidates = [base];
  if (path.extname(spec) === "") {
    candidates.push(
      base + ".js",
      base + ".mjs",
      base + ".cjs",
      base + ".json",
      path.join(base, "index.js"),
    );
  }
  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return candidate;
    }
  }
  return null;
}

function listTestFiles(dir) {
  const found = [];
  function walk(current) {
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name === "node_modules" || entry.name === ".git") {
        continue;
      }
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && /\.(?:test|spec)\.(?:js|mjs)$/.test(entry.name)) {
        found.push(full);
      }
    }
  }
  walk(dir);
  found.sort();
  return found;
}

function listImportedSpecs(source) {
  const patterns = [
    /require\s*\(\s*['"](\.[^'"]+)['"]\s*\)/g,
    /(?:^|[^.\w])import\s+(?:[^'";]*?\sfrom\s+)?['"](\.[^'"]+)['"]/gm,
    /(?:^|[^.\w])import\s*\(\s*['"](\.[^'"]+)['"]\s*\)/gm,
    /(?:^|[^.\w])export\s+[^'";]*?\sfrom\s+['"](\.[^'"]+)['"]/gm,
  ];
  const specs = [];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(source)) !== null) {
      specs.push(match[1]);
    }
  }
  return specs;
}

function checkImportCoverage(dir) {
  const pkgPath = path.join(dir, "package.json");
  if (!fs.existsSync(pkgPath) || !fs.statSync(pkgPath).isFile()) {
    return {
      ok: false,
      message: "package.json is missing",
      missing: [],
      dangling: [],
    };
  }
  let pkg;
  try {
    pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  } catch (err) {
    return {
      ok: false,
      message: "package.json is not valid JSON",
      missing: [],
      dangling: [],
    };
  }
  if (typeof pkg.main !== "string" || pkg.main.trim() === "") {
    return {
      ok: false,
      message: "package.json has no main",
      missing: [],
      dangling: [],
    };
  }
  const entry = path.resolve(dir, pkg.main);
  if (!fs.existsSync(entry) || !fs.statSync(entry).isFile()) {
    return {
      ok: false,
      message: "entry does not exist: " + pkg.main,
      missing: [],
      dangling: [pkg.main],
    };
  }
  const source = fs.readFileSync(entry, "utf8");
  const imported = new Set();
  const dangling = [];
  const entryDir = path.dirname(entry);
  for (const spec of listImportedSpecs(source)) {
    const resolved = resolveRelative(entryDir, spec);
    if (!resolved) {
      if (!dangling.includes(spec)) {
        dangling.push(spec);
      }
    } else {
      imported.add(norm(resolved));
    }
  }
  const missing = [];
  for (const filePath of listTestFiles(dir)) {
    if (!imported.has(norm(filePath))) {
      missing.push(relPosix(dir, filePath));
    }
  }
  if (missing.length > 0 || dangling.length > 0) {
    const parts = [];
    if (missing.length > 0) {
      parts.push("not imported: " + missing.join(", "));
    }
    if (dangling.length > 0) {
      parts.push("imports a file that does not exist: " + dangling.join(", "));
    }
    return { ok: false, message: parts.join("; "), missing, dangling };
  }
  return { ok: true, message: "ok", missing: [], dangling: [] };
}

test("tests/js entry imports every test file", () => {
  const result = checkImportCoverage(JS_DIR);
  assert.equal(result.ok, true, result.message);
});

test("fixture with an unimported test file is a failure", () => {
  const result = checkImportCoverage(path.join(FIXTURES, "import_gap"));
  assert.equal(result.ok, false, result.message);
  assert.match(result.message, /orphan\.test\.js/);
});

test("entry that requires a missing file is a failure", () => {
  const result = checkImportCoverage(path.join(FIXTURES, "import_dangling"));
  assert.equal(result.ok, false, result.message);
  assert.match(result.message, /missing\.test\.js/);
});

test("missing package.json is a failure", () => {
  const result = checkImportCoverage(path.join(FIXTURES, "import_no_pkg"));
  assert.equal(result.ok, false, result.message);
  assert.match(result.message, /package\.json/);
});

test("package.json without main is a failure", () => {
  const result = checkImportCoverage(path.join(FIXTURES, "import_no_main"));
  assert.equal(result.ok, false, result.message);
  assert.match(result.message, /main/);
});

test("esm import covers the imported file and still reports the orphan", () => {
  const result = checkImportCoverage(path.join(FIXTURES, "import_esm"));
  assert.equal(result.ok, false, result.message);
  assert.ok(result.missing.includes("orphan.test.js"), result.message);
  assert.ok(!result.missing.includes("kept.test.js"), result.message);
});

test("spec files count and an unimported spec is a failure", () => {
  const result = checkImportCoverage(path.join(FIXTURES, "import_spec"));
  assert.equal(result.ok, false, result.message);
  assert.match(result.message, /orphan\.spec\.js/);
  assert.match(result.message, /orphan\.spec\.mjs/);
  assert.ok(!result.missing.includes("kept.spec.js"), result.message);
  assert.ok(!result.missing.includes("kept.test.js"), result.message);
});

test("esm entry that imports every test and spec file passes", () => {
  const result = checkImportCoverage(path.join(FIXTURES, "import_esm_ok"));
  assert.equal(result.ok, true, result.message);
});
