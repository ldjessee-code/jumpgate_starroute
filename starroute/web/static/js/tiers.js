/* Star tiers. Keep in step with starroute/mapgen/tiers.py. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.StarrouteTiers = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  var TIER_GATE = "gate_candidate";
  var TIER_EXO = "exo_no_gate";
  var TIER_BACKGROUND = "no_known_planets";
  var PENDING_DOUG = "pending_doug";

  function blank(value) {
    if (value === null || value === undefined) return true;
    if (typeof value === "string") {
      var low = value.trim().toLowerCase();
      return low === "" || low === "nan" || low === "none" || low === "<na>";
    }
    return typeof value === "number" && !Number.isFinite(value);
  }

  function asFloat(value) {
    if (blank(value) || typeof value === "boolean") return null;
    var number = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(number)) return null;
    return number;
  }

  function flagTrue(value) {
    if (blank(value)) return null;
    if (typeof value === "string") {
      var low = value.trim().toLowerCase();
      if (low === "true" || low === "yes" || low === "y" || low === "1") return true;
      if (low === "false" || low === "no" || low === "n" || low === "0") return false;
      return null;
    }
    if (typeof value === "boolean") return value;
    var number = asFloat(value);
    if (number === null) return null;
    return number !== 0;
  }

  function isExoplanetHost(row) {
    if (flagTrue(row.has_known_exoplanets) === true) return true;
    var count = asFloat(row.exoplanet_count);
    if (count !== null && count > 0) return true;
    return false;
  }

  function gateStatusFor(row) {
    var explicit = row.gate_status;
    if (!blank(explicit)) return String(explicit).trim();
    return null;
  }

  function coordsOf(row) {
    var x = asFloat(row.calculated_x);
    var y = asFloat(row.calculated_y);
    var z = asFloat(row.calculated_z);
    if (x === null || y === null || z === null) return null;
    return [x, y, z];
  }

  function meetsGateCriteria(row, minStellarMass, maxStellarMass, origin) {
    var floor = minStellarMass === undefined || minStellarMass === null ? 0.25 : Number(minStellarMass);
    var host = String(row.hostname || "");
    var root = origin || "Sol";
    var coords = coordsOf(row);
    if (!coords) return false;
    if (coords[0] === 0 && coords[1] === 0 && coords[2] === 0 && host !== root) return false;
    if (gateStatusFor(row) === PENDING_DOUG) return false;
    var mass = asFloat(row.st_mass);
    if (!isExoplanetHost(row) && mass === null) return false;
    if (host === root) return true;
    if (mass === null) return true;
    if (mass < floor) return false;
    if (maxStellarMass !== undefined && maxStellarMass !== null && mass > Number(maxStellarMass)) return false;
    return true;
  }

  function classifyTier(row, minStellarMass, maxStellarMass, origin) {
    if (!isExoplanetHost(row)) return TIER_BACKGROUND;
    if (meetsGateCriteria(row, minStellarMass, maxStellarMass, origin)) return TIER_GATE;
    return TIER_EXO;
  }

  return {
    TIER_GATE: TIER_GATE,
    TIER_EXO: TIER_EXO,
    TIER_BACKGROUND: TIER_BACKGROUND,
    classifyTier: classifyTier,
    meetsGateCriteria: meetsGateCriteria,
    isExoplanetHost: isExoplanetHost,
    gateStatusFor: gateStatusFor,
  };
});
