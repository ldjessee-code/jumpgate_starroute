# Table Top RPGs - How to Use/Integrate into different systems

## Homebrew settings

## Example Game systems to include

### GURPS 4e

### Stars Without Numbers

### Traveller Classic

### Traveller 2e (Mongoose/Cepheus)

### Traveller 3e (Mongoose/Cepheus)

### Savage Worlds

### Fate Core

### Coriolis  

### Scum and Villiany (Forged in the Dark)
  
### Mothership

### Starfinder (1, 2e, revised?)



## Research to support

Building a setting intended to be cross-compatible across multiple space-based TTRPG systems requires separating **narrative/world-building baseline data** from system-specific **stat blocks**.

Below is an overview of what each key element requires, focusing on **Stars Without Number (SWN)**, **GURPS 4e**, and other popular sci-fi systems like **Traveller (Mongoose/Cepheus)** or **Fate Core**.

---

### 1. Star Systems & Mapping

The core challenge of multi-system settings is that different games map space differently: SWN uses hex grid sectors, Traveller uses subsectors, GURPS uses 3D coordinates or freeform distances, and Fate uses abstract zone-based connections.

* **System-Neutral Core Data:**
* **Coordinates / Relative Distances:** Hex coordinates (2D grid) or light-year distances between key points.
* **Stellar Classification:** Standard spectral types (e.g., G2V, M3V) to anchor realism.


* **SWN Specifics:**
* **Hex Location:** Uses a 8x10 Sector Grid.
* **System Tags:** 1–2 broad sector/system-level tags (e.g., *Pretech Cache*, *Refugee Colony*) that drive world generation.


* **GURPS 4e Specifics:**
* **Location:** Real light-year distance or 3D coordinates ($X, Y, Z$) relative to a home sector.
* **Stellar Masses & Luminosity:** GURPS relies heavily on physical physics to calculate habitability zones and transit times (found in *GURPS Space*).


* **Resources:**
* [SWN Revised Free Edition (PDF)](https://www.google.com/search?q=https://www.drivethrurpg.com/en/product/248218/Stars-Without-Number-Revised-Edition-Free-Version&utm_source=gemini): Contains full sector-building and tag rules.
* [Sectorgraph](https://sectorgraph.com/?utm_source=gemini): An online generator/mapping tool compatible with SWN and Traveller subsectors.



---

### 2. Planets & Environments

Different games handle planetary data with varying levels of granularity—SWN cares about narrative conflicts and hazards, while GURPS tracks exact physical dimensions and exact socio-economic metrics.

| System Requirement | Stars Without Number (SWN) | GURPS 4e | Traveller / Cepheus Engine |
| --- | --- | --- | --- |
| **Technology Rating** | **Tech Level (TL 0–5+):** Baseline is TL4 (Postech). | **Tech Level (TL 0–12):** Baseline sci-fi is TL9–TL11. | **Tech Level (TL 0–15+):** Baseline interstellar is TL10–TL12. |
| **Atmosphere & Climate** | Qualitative descriptors (e.g., *Breathable, Corrosive, Inert*). | Atmospheric Pressure (atm), Gas composition, Average Surface Temp (°F/°C). | UWP (Universal World Profile) digit rating (0–F for pressure/composition). |
| **Population & Government** | Population range + 2 **World Tags** (e.g., *Rigid Culture*, *Seismic Instability*). | Population size, Control Rating (CR 0–6), Governance Type, Legality Classes. | UWP digits for Population (exponent), Government (0–F), and Law Level (0–J). |
| **Gravity & Size** | Binary or minor modifiers (e.g., *Low-G*, *High-G*). | Surface Gravity in *g* (impacts encumbrance, falls, jumping), Diameter in miles. | Size digit (0–10) directly mapping to gravity and planetary radius. |

* **Tech Level Bridge Rule:**
* **SWN TL0–TL3** ≈ **GURPS TL0–TL8** (Pre-spaceflight).
* **SWN TL4 (Postech)** ≈ **GURPS TL9–TL10** (Interstellar standard).
* **SWN TL5 (Pretech)** ≈ **GURPS TL11–TL12** (Exotic/Miraculous tech).


* **Resources:**
* [Traveller Map / UWP Wiki](https://www.google.com/search?q=https://wiki.wiki.travellermap.com/Universal_World_Profile&utm_source=gemini): Standard overview of the 8-digit UWP format used widely across 2d6 space RPGs.
* [GURPS Calculator (Planet Generator)](https://www.google.com/search?q=https://gurpscalculator.com/&utm_source=gemini): Tools that translate *GURPS Space* math into simple stat blocks.



---

### 3. Faster-Than-Light (FTL) Travel & Space Transit

FTL mechanics define the entire tone of a setting's economy and politics. To make a setting multi-system, you should describe the **in-universe narrative logic** of FTL first, then map it to each mechanical system.

* **Universal Narrative Parameters:**
* **Method:** Hyper-space lanes, Jump points/Gates, Warp drives, or Spike drives.
* **Hazards:** Mass shadows (needing to reach system rims before jumping), jump decay, or warp anomalies.
* **Fuel & Cost:** Fuel requirements (refined hydrogen, anti-matter, rare crystals) and transit duration per light-year/parsec.


* **System-Specific Adaptations:**
* **SWN (Spike Drives):** Uses *Phase/Spike Drives* rated from Drive-1 to Drive-6. Drives move ship across sector hexes; requires a navigation check using *Astrogation* or *Pilot* modified by route difficulty.
* **GURPS 4e:** Requires selecting an FTL engine type from *GURPS Spaceships* (e.g., *Hyperdrive*, *Jumpdrive*, or *Warp Drive*). Define rating in terms of light-years per day or fuel consumed per parsec.
* **Traveller/Cepheus:** Uses a 1-to-6 week-long *Jump Drive* mechanic where 1 Jump consumes 10% of hull volume per Jump-number in liquid hydrogen.


* **Resources:**
* [GURPS Spaceships PDF Series (SJ Games)](https://www.sjgames.com/gurps/books/spaceships/?utm_source=gemini): Modular ship design system containing plug-and-play FTL drive modules.
* [Stars Without Number Sector Generator (SINE NOMINE)](https://www.google.com/search?q=https://swn.bin.sh/&utm_source=gemini): Automated tool that outputs SWN-compliant navigation routes and system data.



---

### Recommended Layout Template for Setting Modules

To present a system-agnostic world profile efficiently:

```markdown
### SYSTEM: Alpha Centauri
* Narrative Overview & History

#### System Properties
* Stellar Type: G2V
* FTL Nodes / Transit Hazards: Outer System Mass-Shadow at 10 AU.

#### Planet: Terra Nova
* Narrative Description: Arid mining world under corporate blockade.
* Core Physical Specs: Gravity 1.15g | Atmosphere: Breathable (Thin) | Temp: Warm
* Game Stats:
  - SWN: TL4 | Tags: Minefield, Corporate Control
  - GURPS 4e: TL9 | CR 4 | Pop 2,000,000 | Hydrographic 10%
  - Traveller/Cepheus UWP: C763644-9

```

This video explains how to build and calculate classical planetary systems step-by-step: [How to Create a Classical Planetary System](https://www.youtube.com/watch?v=J5xU-8Kb63Y&utm_source=gemini)