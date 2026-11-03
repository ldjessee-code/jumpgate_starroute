const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const tiers = require("../../starroute/web/static/js/tiers.js");

const cases = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "fixtures", "tier_cases.json"), "utf8"),
);

test("browser tiers match the shared fixture", () => {
  for (const item of cases) {
    const got = tiers.classifyTier(
      item.row,
      item.min_stellar_mass,
      item.max_stellar_mass,
      item.origin,
    );
    assert.equal(got, item.expect, item.name);
  }
});

test("background stars fail the gate check", () => {
  const row = cases.find((item) => item.name === "no planets").row;
  assert.equal(tiers.meetsGateCriteria(row, 0.25, null, "Sol"), true);
  assert.equal(tiers.classifyTier(row, 0.25, null, "Sol"), "no_known_planets");
});

test("missing mass on a planet host can be a gate", () => {
  const row = cases.find((item) => item.name === "exo missing mass").row;
  assert.equal(tiers.meetsGateCriteria(row, 0.25, null, "Sol"), true);
  assert.equal(tiers.classifyTier(row, 0.25, null, "Sol"), "gate_candidate");
  assert.equal(tiers.classifyTier(row, 0.66, 1.5, "Sol"), "gate_candidate");
});

test("no planets and no mass is not a gate", () => {
  const row = {
    hostname: "BareDark",
    calculated_x: 5,
    calculated_y: 0,
    calculated_z: 0,
    st_mass: null,
    sy_pnum: 0,
    has_known_exoplanets: false,
  };
  assert.equal(tiers.classifyTier(row, 0.25, null, "Sol"), "no_known_planets");
  assert.equal(tiers.meetsGateCriteria(row, 0.25, null, "Sol"), false);
  const origin = {
    hostname: "Sol",
    calculated_x: 0,
    calculated_y: 0,
    calculated_z: 0,
    st_mass: null,
    sy_pnum: 0,
    has_known_exoplanets: false,
  };
  assert.equal(tiers.meetsGateCriteria(origin, 0.25, null, "Sol"), false);
  assert.equal(tiers.classifyTier(origin, 0.25, null, "Sol"), "no_known_planets");
});

test("companion host at the default mass floor is a gate", () => {
  const row = cases.find((item) => item.name === "companion host at default mass floor").row;
  assert.equal(tiers.gateStatusFor(row), null);
  assert.equal(tiers.meetsGateCriteria(row, 0.25, null, "Sol"), true);
  assert.equal(tiers.classifyTier(row, 0.25, null, "Sol"), "gate_candidate");
  const syOnly = cases.find((item) => item.name === "sy_pnum alone is not a host").row;
  assert.equal(tiers.classifyTier(syOnly, 0.25, null, "Sol"), "no_known_planets");
  const explicit = cases.find((item) => item.name === "explicit pending_doug").row;
  assert.equal(tiers.gateStatusFor(explicit), "pending_doug");
  assert.equal(tiers.meetsGateCriteria(explicit, 0.25, null, "Sol"), false);
  assert.equal(tiers.gateStatusFor({ hostname: "Kept", gate_status: "open" }), "open");
});
