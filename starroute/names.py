"""Host component letters, catalog ids with suffixes, Bayer display names.

Hostname ``55 Cnc B`` maps to component B. Bare ``55 Cnc`` maps to the
primary (A). HIP/HD tokens keep a trailing letter. Display names prefer a
Bayer form from HYG ``bf`` / ``bayer`` + ``con``, then a display overlay,
then the hostname.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from starroute.paths import CONFIG_DIR
from starroute.turquenish import clean_id

DISPLAY_NAMES_JSON = CONFIG_DIR / "display_names.json"

_GREEK_DISPLAY = {
    "alf": "Alpha",
    "bet": "Beta",
    "gam": "Gamma",
    "del": "Delta",
    "eps": "Epsilon",
    "zet": "Zeta",
    "eta": "Eta",
    "the": "Theta",
    "iot": "Iota",
    "kap": "Kappa",
    "lam": "Lambda",
    "mu": "Mu",
    "nu": "Nu",
    "xi": "Xi",
    "omi": "Omicron",
    "pi": "Pi",
    "rho": "Rho",
    "sig": "Sigma",
    "tau": "Tau",
    "ups": "Upsilon",
    "phi": "Phi",
    "chi": "Chi",
    "psi": "Psi",
    "ome": "Omega",
}

_GREEK_TOKEN = {
    "alpha": "alf",
    "alf": "alf",
    "beta": "bet",
    "bet": "bet",
    "gamma": "gam",
    "gam": "gam",
    "delta": "del",
    "del": "del",
    "epsilon": "eps",
    "eps": "eps",
    "zeta": "zet",
    "zet": "zet",
    "eta": "eta",
    "theta": "the",
    "the": "the",
    "tet": "the",
    "iota": "iot",
    "iot": "iot",
    "kappa": "kap",
    "kap": "kap",
    "lambda": "lam",
    "lam": "lam",
    "mu": "mu",
    "nu": "nu",
    "xi": "xi",
    "omicron": "omi",
    "omi": "omi",
    "pi": "pi",
    "rho": "rho",
    "sigma": "sig",
    "sig": "sig",
    "tau": "tau",
    "upsilon": "ups",
    "ups": "ups",
    "phi": "phi",
    "chi": "chi",
    "psi": "psi",
    "omega": "ome",
    "ome": "ome",
}

_CON_GENITIVE = {
    "and": "Andromedae",
    "ant": "Antliae",
    "aps": "Apodis",
    "aqr": "Aquarii",
    "aql": "Aquilae",
    "ara": "Arae",
    "ari": "Arietis",
    "aur": "Aurigae",
    "boo": "Bootis",
    "cae": "Caeli",
    "cam": "Camelopardalis",
    "cnc": "Cancri",
    "cma": "Canis Majoris",
    "cmi": "Canis Minoris",
    "cap": "Capricorni",
    "car": "Carinae",
    "cas": "Cassiopeiae",
    "cen": "Centauri",
    "cep": "Cephei",
    "cet": "Ceti",
    "cha": "Chamaeleontis",
    "cir": "Circini",
    "col": "Columbae",
    "com": "Comae Berenices",
    "cra": "Coronae Australis",
    "crb": "Coronae Borealis",
    "crv": "Corvi",
    "crt": "Crateris",
    "cru": "Crucis",
    "cyg": "Cygni",
    "del": "Delphini",
    "dor": "Doradus",
    "dra": "Draconis",
    "equ": "Equulei",
    "eri": "Eridani",
    "for": "Fornacis",
    "gem": "Geminorum",
    "gru": "Gruis",
    "her": "Herculis",
    "hor": "Horologii",
    "hya": "Hydrae",
    "hyi": "Hydri",
    "ind": "Indi",
    "lac": "Lacertae",
    "leo": "Leonis",
    "lmi": "Leonis Minoris",
    "lep": "Leporis",
    "lib": "Librae",
    "lup": "Lupi",
    "lyn": "Lyncis",
    "lyr": "Lyrae",
    "men": "Mensae",
    "mic": "Microscopii",
    "mon": "Monocerotis",
    "mus": "Muscae",
    "nor": "Normae",
    "oct": "Octantis",
    "oph": "Ophiuchi",
    "ori": "Orionis",
    "pav": "Pavonis",
    "peg": "Pegasi",
    "per": "Persei",
    "phe": "Phoenicis",
    "pic": "Pictoris",
    "psc": "Piscium",
    "psa": "Piscis Austrini",
    "pup": "Puppis",
    "pyx": "Pyxidis",
    "ret": "Reticuli",
    "sge": "Sagittae",
    "sgr": "Sagittarii",
    "sco": "Scorpii",
    "scl": "Sculptoris",
    "sct": "Scuti",
    "ser": "Serpentis",
    "sex": "Sextantis",
    "tau": "Tauri",
    "tel": "Telescopii",
    "tri": "Trianguli",
    "tra": "Trianguli Australis",
    "tuc": "Tucanae",
    "uma": "Ursae Majoris",
    "umi": "Ursae Minoris",
    "vel": "Velorum",
    "vir": "Virginis",
    "vol": "Volantis",
    "vul": "Vulpeculae",
}

_SPACE_COMP = re.compile(r"^(?P<base>.+?)\s+(?P<letter>[A-Da-d])$")
_GLUED_COMP = re.compile(r"^(?P<base>.*\d)\s*(?P<letter>[A-Da-d])$")
_CATALOG_ID = re.compile(
    r"^(?:(?P<prefix>HIP|HD|HR|GJ|GL|GLIESE)\s*)?0*(?P<number>\d+)(?:\s*(?P<letter>[A-Za-z]))?$",
    re.IGNORECASE,
)
_GLIESE = re.compile(r"^(?:gl|gj|nn|gliese)\s*(\d+(?:\.\d+)?)([A-Da-d])?$", re.IGNORECASE)


def split_host_component(value: Any) -> tuple[str, str]:
    """Return ``(base, letter)``. Bare names are the primary (empty letter)."""
    text = clean_id(value)
    if not text:
        return "", ""
    space = _SPACE_COMP.match(text)
    if space:
        return space.group("base").strip(), space.group("letter").upper()
    glued = _GLUED_COMP.match(text)
    if glued:
        return glued.group("base").strip(), glued.group("letter").upper()
    return text, ""


def primary_letter(letter: str) -> str:
    """Empty letter is the primary, treated as A for matching."""
    text = (letter or "").strip().upper()
    return text if text else "A"


def components_compatible(left: Any, right: Any) -> bool:
    """True when both names are the same component (bare = primary = A)."""
    _, left_letter = split_host_component(left)
    _, right_letter = split_host_component(right)
    return primary_letter(left_letter) == primary_letter(right_letter)


def catalog_id_token(value: Any, prefix: str = "") -> str:
    """Digits plus a trailing component letter when the source has one.

    ``HIP 28393 A`` stays ``28393A``. A bare ``HIP 28393`` stays ``28393``.
    """
    text = clean_id(value)
    if not text:
        return ""
    if prefix:
        match = re.match(
            r"^" + re.escape(prefix) + r"\s*0*(?P<number>\d+)(?:\s*(?P<letter>[A-Za-z]))?$",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            token = str(int(match.group("number")))
            letter = (match.group("letter") or "").upper()
            return token + letter if letter else token
        return ""
    match = _CATALOG_ID.match(text)
    if not match:
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits
    token = str(int(match.group("number")))
    letter = (match.group("letter") or "").upper()
    return token + letter if letter else token


def gliese_token(value: Any) -> str:
    """``Gl 324B`` / ``GJ 324 B`` / ``Gliese 324 A`` → ``324B`` / ``324A``."""
    text = re.sub(r"\s+", "", clean_id(value))
    if not text:
        return ""
    match = _GLIESE.match(text)
    if not match:
        return ""
    number = match.group(1)
    letter = (match.group(2) or "").upper()
    return number + letter


def with_component(base: str, letter: str) -> str:
    text = (base or "").strip()
    comp = (letter or "").strip().upper()
    if not text:
        return comp
    if not comp or comp == "A":
        return text
    return f"{text} {comp}"


def _canon_greek(token: str) -> str:
    raw = re.sub(r"[^a-z0-9]", "", (token or "").lower())
    match = re.match(r"^([a-z]+)(\d*)$", raw)
    if not match:
        return raw
    greek = _GREEK_TOKEN.get(match.group(1))
    if not greek:
        return raw
    return greek + match.group(2)


def _greek_display(token: str) -> str:
    raw = _canon_greek(token)
    match = re.match(r"^([a-z]+)(\d*)$", raw)
    if not match:
        return (token or "").strip()
    word = _GREEK_DISPLAY.get(match.group(1), match.group(1).title())
    suffix = match.group(2)
    if suffix == "1":
        return word
    return word + suffix if suffix else word


def _con_display(con: str) -> str:
    abbr = (con or "").strip().lower()
    if abbr in _CON_GENITIVE:
        return _CON_GENITIVE[abbr]
    return (con or "").strip()


def bayer_from_bf(bf: Any, con: Any = "") -> str:
    """HYG ``bf`` plus constellation → ``Rho Cancri``."""
    compact = re.sub(r"\s+", "", clean_id(bf))
    if not compact:
        return ""
    con_text = clean_id(con)
    body = compact
    if con_text and compact.lower().endswith(con_text.lower()):
        body = compact[: len(compact) - len(con_text)]
    else:
        match = re.match(r"^(.+?)([A-Za-z]{3})$", compact)
        if match:
            body, con_text = match.group(1), match.group(2)
    body = re.sub(r"^\d+", "", body)
    greek = _canon_greek(body)
    if not greek or not con_text:
        return ""
    return f"{_greek_display(greek)} {_con_display(con_text)}"


def _overlay_table(path: str | Path | None = None) -> dict[str, Any]:
    file_path = Path(path) if path else DISPLAY_NAMES_JSON
    if not file_path.is_file():
        return {}
    with file_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    hosts = payload.get("hosts") if isinstance(payload, dict) else None
    return hosts if isinstance(hosts, dict) else {}


def overlay_for(hostname: Any, path: str | Path | None = None) -> dict[str, Any]:
    host = clean_id(hostname)
    if not host:
        return {}
    table = _overlay_table(path)
    if host in table and isinstance(table[host], dict):
        return dict(table[host])
    base, letter = split_host_component(host)
    if letter and base in table and isinstance(table[base], dict):
        found = dict(table[base])
        name = clean_id(found.get("name"))
        if name:
            found["name"] = with_component(name, letter)
        return found
    return {}


def display_name_for(row: Mapping[str, Any], overlay_path: str | Path | None = None) -> str:
    """Bayer name, then overlay, then proper, then hostname."""
    host = clean_id(
        row.get("hostname") or row.get("exo_hostname") or row.get("sy_name") or row.get("proper")
    )
    _, letter = split_host_component(host)
    bayer = bayer_from_bf(row.get("bf"), row.get("con"))
    if not bayer:
        bayer_token = clean_id(row.get("bayer"))
        con = clean_id(row.get("con"))
        if bayer_token and con:
            bayer = f"{_greek_display(bayer_token)} {_con_display(con)}"
    overlay = overlay_for(host, overlay_path)
    if bayer:
        return with_component(bayer, letter) if letter else bayer
    overlay_name = clean_id(overlay.get("name"))
    if overlay_name:
        return overlay_name
    proper = clean_id(row.get("proper"))
    if proper:
        return with_component(proper, letter) if letter and letter not in proper.split()[-1:] else proper
    return host


def _alias_variants(text: str) -> list[str]:
    value = clean_id(text)
    if not value:
        return []
    out = [value]
    base, letter = split_host_component(value)
    if letter == "A" and base:
        out.append(base)
    if letter and base:
        out.append(f"{base} {letter}")
        out.append(f"{base}{letter}")
    return out


def aliases_for(row: Mapping[str, Any], overlay_path: str | Path | None = None) -> list[str]:
    """Hostname, Bayer, proper, HD/HIP/Gliese forms, plus overlay aliases."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(value: Any) -> None:
        for item in _alias_variants(str(value) if value is not None else ""):
            key = item.casefold()
            if key in seen or not item:
                continue
            seen.add(key)
            ordered.append(item)

    host = clean_id(row.get("hostname") or row.get("exo_hostname") or row.get("sy_name"))
    add(host)
    base, letter = split_host_component(host)
    if letter:
        add(base)
        add(f"{base} {letter}")
        add(f"{base} A" if letter != "A" else None)
    else:
        add(f"{host} A")
    add(display_name_for(row, overlay_path))
    add(row.get("proper"))
    bf_name = bayer_from_bf(row.get("bf"), row.get("con"))
    add(bf_name)
    if bf_name and letter:
        add(with_component(bf_name, letter))
    for label, raw in (
        ("HD", row.get("hd") or row.get("hd_name")),
        ("HIP", row.get("hip") or row.get("hip_name")),
    ):
        token = catalog_id_token(raw, label)
        if token:
            digits = "".join(ch for ch in token if ch.isdigit())
            suffix = "".join(ch for ch in token if ch.isalpha())
            add(f"{label} {digits}")
            if suffix:
                add(f"{label} {digits} {suffix}")
    gl = clean_id(row.get("gl") or row.get("gliese"))
    gl_token = gliese_token(gl) or gliese_token(host)
    if gl_token:
        number = re.match(r"^(\d+(?:\.\d+)?)([A-D]?)$", gl_token)
        if number:
            num, gl_letter = number.group(1), number.group(2)
            for prefix in ("Gliese", "Gl", "GJ"):
                add(f"{prefix} {num}")
                if gl_letter:
                    add(f"{prefix} {num} {gl_letter}")
                    add(f"{prefix} {num}{gl_letter}")
                elif letter:
                    add(f"{prefix} {num} {letter}")
                    add(f"{prefix} {num}{letter}")
    overlay = overlay_for(host, overlay_path)
    for item in overlay.get("aliases") or []:
        add(item)
    return ordered
