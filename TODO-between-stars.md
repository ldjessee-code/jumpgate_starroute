# Jumpgate Starroute — between-stars work list

Agreed 2026-09-24. This is the work that stays in this repo.

Orbit Match (`../orbit_match/BRIEF.md`) is the sibling for planets, orbits, and in-system transfers. Game-system notes, with publisher links and free starters, are in [GAME_SYSTEMS.md](GAME_SYSTEMS.md). The same notes sit in the sibling folder so that program can stand alone.

Empty fields mean "this table does not track that." A high concept is enough for Fate, Scum and Villainy, or Mothership. The same card can later hold tags a Traveller or Stars Without Number referee will turn into their own world block. This program does not generate that block.

## Travel model

A pack can use any combination:

- **Network.** Travel only along a route (a gate, lane, or portal).
- **Range.** A ship drive can reach any star inside a light-year limit. Coordinates already support this. Routes are optional charted lanes.
- **Both.** Short drive and long infrastructure at once. The drive hops any pair inside `short_ftl_ly`. A gate edge is usable even when it is longer than that drive. This is the usual case for "jump points for the long haul, a slow drive for the last few light-years."

Store light-years. A parsec readout for Traveller can be a display later (`ly / 3.26156`). Do not store a second distance.

## Stays here

**Star.** Catalog name, coordinates, light-years from origin, spectral type, known-planet count, culture. Add a setting name beside the catalog name.

**System card, one row per star.**

- High concept (one sentence) and situation (a second sentence).
- Tags, typed by the user (`water world`, `asteroid yards`). Labels, not generated planets.
- Port: none, minor, standard, major, or blank.
- Services, open list: fuel, repair, trade, shipyard, and anything the user adds.
- Imports and exports, open tags (`food`, `fuel`, `ore`, `hulls`, `medicine`, `data`).
- Holder: the faction already assigned.
- Presences: zero or more other factions on that star, each with a role word (embassy, enclave, occupation, trade post).

**Faction stance.** Seven steps, stored as −3 to +3:

| Value | Word |
| --- | --- |
| −3 | Hostile |
| −2 | Unfriendly |
| −1 | Wary |
| 0 | Neutral |
| +1 | Cordial |
| +2 | Friendly |
| +3 | Allied |

Directed: A can be wary of B while B is cordial to A. Until the mirror is broken, editing one direction fills the other. A pair nobody has set is neutral, so ten factions are not ninety decisions.

Imports and exports stay on the star. Stance stays on the faction pair.

**Routes.**

- Generated edges, as today.
- Hand-added edges, kept across a rebuild.
- Suppressed pairs, so a deleted generated route does not come back. This is how a fixed portal map (Coriolis) is built: drop the generated net, draw the portals.
- Direction: both, or one way. Default both.
- Kind label: gate, lane, portal, charted. A label, not a ruleset.
- Optional tariff override, keeper, condition (open, tolled, watched, failing, closed), hazard note, and an access override when this road disagrees with the faction stance (a grain treaty through hostile space).

**Campaign tariff,** optional. The user names the units. Defaults apply per hop or per light-year, and a single route can override them.

- Transit time
- Fuel
- Toll (money)
- Dock time after arrival

A highlighted path sums whatever of those is filled in.

**Range, when both or range is on.** `short_ftl_ly` on the pack. Pathfinding treats pairs inside that limit as usable hops, and also treats stored edges as usable when they are longer. Suppressed pairs are not hopped by the drive either, if the user removed them on purpose.

## Does not stay here

- Planets, moons, belts, stations, and orbits.
- Gravity, atmosphere, hydrographics, day length, diameter, and a generated population or government.
- Transfers, delta-v, and arrival burns.
- Step-by-step random solar-system generation.
- Ship sheets, drive ratings per hull, and cargo tonnage. The campaign tariff is a table default, not a ship.
- A history of how stance changed. The file is the current state.
- Worldstack, Ptah, `star_network`, Gamer Eye.

The handoff shape is in `../orbit_match/BRIEF.md`. This map may store a pointer to a system file. Opening the star shows the card. Opening the file is the other program.

## Work list

Old snapshots must still load. New fields are optional and absent means blank.

### 1. System card and stances

- [ ] Add the card fields on a star, editable, saved with the snapshot.
- [ ] Add services and import/export tags.
- [ ] Add optional presences beside the existing holder.
- [ ] Add the stance table, −3 to +3, directed, mirror-until-broken, missing pair = neutral.
- [ ] Show the stance when a highlighted path crosses from one holder to another.

### 2. Routes the user owns

- [ ] Mark each edge generated or manual.
- [ ] Add a route by picking two stars.
- [ ] Remove a route. If it was generated, record the pair as suppressed.
- [ ] Rebuild (`build-presets` / generate) keeps manual routes and does not recreate suppressed pairs.
- [ ] Direction and kind label on the edge. Default: both ways, kind blank or gate.
- [ ] Optional access override and hazard note on the edge.

### 3. Tariff

- [ ] Campaign defaults: time, fuel, toll, dock time. Each has an amount, a user-named unit, and per-hop or per-light-year.
- [ ] Per-route overrides, including keeper and condition.
- [ ] Sum filled-in costs along the highlighted path.

### 4. Short drive and long gates

- [ ] Pack switch: network, range, or both. At least one of network or range is on.
- [ ] `short_ftl_ly` used when range or both is on.
- [ ] Pathfinding: drive hops inside that limit, plus stored edges of any length, minus suppressed pairs.
- [ ] The map can show gate edges and drive range as two different marks.

### Later

- [ ] Suggest trade pairs where one star's export matches another's import and the stance is not hostile. A suggestion, not a new stat.
- [ ] Group very close catalog stars (Alpha Centauri A and B) as one destination for gates, while keeping both rows. Threshold is a decision still open.
- [ ] Parsec display for Traveller, computed from stored light-years.
- [ ] Player view that can hide GM-only stances, hazards, and closed routes.
- [ ] Write and read the Orbit Match handoff file. Do not embed the solar system in the map snapshot.
- [ ] Attach `system_file` on a star once Orbit Match exists.

## Reserve these names

Use these on the snapshot so later work does not invent a second vocabulary.

```text
star.setting_name
star.high_concept
star.situation
star.tags[]
star.port                 none | minor | standard | major | null
star.services[]
star.imports[]
star.exports[]
star.presences[]          { faction, role }
star.system_file          path or null

pack.travel               network | range | both
pack.short_ftl_ly         number or null

stance[]                  { from, to, value }     value -3..3, absent = 0

edge.source               generated | manual
edge.direction            both | a_to_b | b_to_a
edge.kind                 gate | lane | portal | charted | ""
edge.hazard
edge.access               null or a short override
edge.tariff               optional override of the campaign tariff
edge.keeper
edge.condition            open | tolled | watched | failing | closed | ""

suppressed_pairs[]        { a, b }

tariff.time / fuel / toll / dock
  amount, unit (string), per: hop | ly
```

Known-planet count and spectral type already exist (`sy_pnum`, `spectype`). They stay catalog facts. They are not a world profile.
