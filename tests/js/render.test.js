const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const app = fs.readFileSync(
  path.join(__dirname, "..", "..", "starroute", "web", "static", "js", "app.js"),
  "utf8",
);

test("map legend and traces name the three tiers", () => {
  assert.match(app, /gate_candidate/);
  assert.match(app, /exo_no_gate/);
  assert.match(app, /no_known_planets/);
  assert.match(app, /No known planets/);
  assert.match(app, /Exoplanet host, no gate/);
  assert.match(app, /Gate candidate/);
});
