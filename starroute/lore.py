"""Walk ``setting/**/*.md`` and write the static lore index + page copies.

Stdlib only. Missing NASA CSVs / pandas must not block this path.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from starroute.paths import ROOT, SETTING_DIR, STATIC_LORE

SKIP_NAMES = {"readme.md"}
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip('"').strip("'")
        if key == "order":
            try:
                meta[key] = int(value)
            except ValueError:
                try:
                    meta[key] = float(value)
                except ValueError:
                    meta[key] = value
        else:
            meta[key] = value
    return meta, text[match.end() :]


def _title_from_body(body: str, fallback: str) -> str:
    match = HEADING_RE.search(body)
    if match:
        return match.group(1).strip()
    return fallback.replace("-", " ").replace("_", " ").title()


def collect_pages(vault: Path) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    if not vault.is_dir():
        return pages
    for path in sorted(vault.rglob("*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(vault).as_posix()
        if path.name.lower() in SKIP_NAMES and rel.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(text)
        stem = rel[: -len(".md")] if rel.lower().endswith(".md") else rel
        title = str(meta.get("title") or _title_from_body(body, Path(stem).name))
        order = meta.get("order", 100)
        pages.append(
            {
                "id": stem.replace("\\", "/"),
                "title": title,
                "order": order,
                "source": rel,
                "path": f"pages/{rel}",
            }
        )
    pages.sort(key=lambda item: (item["order"], item["title"].lower(), item["id"]))
    return pages


def emit_static(pages: list[dict[str, Any]], vault: Path, dest: Path) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    pages_dir = dest / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)

    for page in pages:
        src = vault / page["source"]
        out = dest / page["path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)

    index = {"default": pages[0]["id"] if pages else None, "pages": pages}
    blob = json.dumps(index, indent=2) + "\n"
    (dest / "index.json").write_text(blob, encoding="utf-8")
    (dest / "index.js").write_text(
        "window.STARROUTE_LORE_INDEX=" + json.dumps(index, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    return index


def build_lore(vault: Path | None = None, dest: Path | None = None) -> dict[str, Any]:
    vault = Path(vault) if vault else SETTING_DIR
    dest = Path(dest) if dest else STATIC_LORE
    if not vault.is_dir():
        raise SystemExit(f"Lore vault not found: {vault}")
    pages = collect_pages(vault)
    index = emit_static(pages, vault, dest)
    def _rel(path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return str(resolved)

    return {
        "vault": _rel(vault),
        "dest": _rel(dest),
        "pages": len(pages),
        "ids": [page["id"] for page in pages],
        "default": index.get("default"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the static lore wiki index from setting/*.md")
    parser.add_argument("--vault", help="Markdown vault (default: setting/)")
    parser.add_argument("--dest", help="Static lore folder (default: starroute/web/static/docs/lore)")
    args = parser.parse_args(argv)
    result = build_lore(args.vault, args.dest)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
