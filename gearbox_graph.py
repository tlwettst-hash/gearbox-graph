"""gearbox-graph: draw an Obsidian vault as a machine of meshing gears, in one offline HTML file.

Read-only on the vault: it only opens .md files for reading, and writes one file (--out).
No network, no third-party packages. Python 3.9+.

Colors: by default each top-level folder gets its own color. A config file (--config)
can name groups and map folders and `project:` frontmatter tags to them; see
groups.example.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP_DIRS = {".obsidian", ".git", "__pycache__", "node_modules", ".trash", "site-packages"}
MAX_BYTES = 2_000_000  # only the first 2MB of any note is scanned for links

# Brick colors for automatic folder groups, most notes first.
PALETTE = ["#C91A09", "#0055BF", "#F2CD37", "#237841", "#FE8A18", "#C870A0",
           "#E4CD9E", "#069D9F", "#81007B", "#A5CA18", "#582A12"]
OTHER_COLOR, ROOT_COLOR = "#A0A5A9", "#F4F4F4"   # light bluish gray, white

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
PROJECT_RE = re.compile(r"^project:\s*(.+?)\s*$", re.M)
LINK_RE = re.compile(r"!?\[\[([^\]\|#\^\n]+)")
ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> dict:
    """Read and validate a groups config. Anything unexpected is an error, not a guess."""
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"can't read {path}: {e}") from None
    if not isinstance(cfg, dict):
        raise ConfigError("config must be a JSON object")
    unknown = set(cfg) - {"groups", "folders", "tags", "folders_win", "fallback"}
    if unknown:
        raise ConfigError(f"unknown config keys: {', '.join(sorted(unknown))}")

    groups = cfg.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ConfigError('"groups" must be a non-empty object of {id: {label, color}}')
    for gid, g in groups.items():
        if not ID_RE.match(gid):
            raise ConfigError(f'group id "{gid}" must be 1-32 chars of a-z, 0-9, _ or -')
        if not isinstance(g, dict) or set(g) != {"label", "color"}:
            raise ConfigError(f'group "{gid}" must have exactly "label" and "color"')
        if not isinstance(g["label"], str) or not 0 < len(g["label"]) <= 60:
            raise ConfigError(f'group "{gid}" label must be a string of 1-60 chars')
        if not isinstance(g["color"], str) or not COLOR_RE.match(g["color"]):
            raise ConfigError(f'group "{gid}" color must look like #C91A09')

    def mapping(key):
        m = cfg.get(key, {})
        if not isinstance(m, dict) or not all(isinstance(k, str) and v in groups for k, v in m.items()):
            raise ConfigError(f'"{key}" must map names to group ids defined in "groups"')
        return m

    folders, tags = mapping("folders"), {k.lower(): v for k, v in mapping("tags").items()}
    folders_win = cfg.get("folders_win", [])
    if not isinstance(folders_win, list) or not all(f in folders for f in folders_win):
        raise ConfigError('"folders_win" must be a list of folders that appear in "folders"')
    fallback = cfg.get("fallback")
    if fallback not in groups:
        raise ConfigError('"fallback" must be one of the group ids')
    return {"groups": groups, "folders": folders, "tags": tags,
            "folders_win": set(folders_win), "fallback": fallback}


def scan(vault: Path):
    """Every note's path relative to the vault, skipping hidden and tool folders."""
    files = []
    for p in sorted(vault.rglob("*.md")):
        rel = p.relative_to(vault)
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        files.append(rel)
    return files


def top_folder(rel: Path) -> str:
    return rel.parts[0] if len(rel.parts) > 1 else ""


def auto_config(files) -> dict:
    """One group per top-level folder, biggest first; the overflow shares one gray group."""
    counts = {}
    for rel in files:
        top = top_folder(rel)
        if top:
            counts[top] = counts.get(top, 0) + 1
    ranked = sorted(counts, key=lambda f: (-counts[f], f.lower()))
    groups, folders = {}, {}
    for i, name in enumerate(ranked[:len(PALETTE)]):
        gid = f"g{i}"   # generated ids: a folder name never becomes a JS object key
        groups[gid] = {"label": name[:60], "color": PALETTE[i]}
        folders[name] = gid
    if len(ranked) > len(PALETTE):
        groups["other"] = {"label": "Other folders", "color": OTHER_COLOR}
    groups["root"] = {"label": "Vault root", "color": ROOT_COLOR}
    return {"groups": groups, "folders": folders, "tags": {}, "folders_win": set(),
            "fallback": "other" if "other" in groups else "root", "root": "root"}


def group_for(rel: Path, text: str, cfg: dict) -> str:
    top = top_folder(rel)
    if top in cfg["folders_win"]:
        return cfg["folders"][top]
    m = FM_RE.match(text)
    if m:
        p = PROJECT_RE.search(m.group(1))
        if p:
            tag = p.group(1).strip().strip("\"'").lower()
            if tag in cfg["tags"]:
                return cfg["tags"][tag]
    if not top and "root" in cfg:
        return cfg["root"]
    return cfg["folders"].get(top, cfg["fallback"])


def build(vault: Path, cfg=None, vault_name=None) -> dict:
    files = scan(vault)
    cfg = cfg or auto_config(files)

    # Obsidian resolves [[Name]] by basename, or by path for [[Folder/Name]].
    by_name, by_path = {}, {}
    for i, rel in enumerate(files):
        by_name.setdefault(rel.stem.lower(), i)
        by_path[rel.with_suffix("").as_posix().lower()] = i

    nodes, edges = [], set()
    for i, rel in enumerate(files):
        with open(vault / rel, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read(MAX_BYTES)
        nodes.append({"t": rel.stem, "p": rel.as_posix(), "g": group_for(rel, text, cfg)})
        for raw in LINK_RE.findall(text):
            target = raw.strip().removesuffix(".md").lower()
            j = by_path.get(target)
            if j is None:
                j = by_name.get(target.rsplit("/", 1)[-1])
            if j is not None and j != i:
                edges.add((min(i, j), max(i, j)))

    used = {n["g"] for n in nodes}
    return {
        "vault": vault_name or vault.name,
        "groups": {k: v for k, v in cfg["groups"].items() if k in used},
        "nodes": nodes,
        "edges": sorted(edges),
    }


def render(data: dict, template: str) -> str:
    # Escape "<" so a note title can never close the <script> block or open a comment,
    # and U+2028/2029 so old JS engines don't read them as line breaks.
    blob = (json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    if "/*__DATA__*/null" not in template:
        raise ValueError("template is missing the /*__DATA__*/null placeholder")
    return template.replace("/*__DATA__*/null", blob, 1)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):   # a Windows console can't print every path; don't crash on it
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap =argparse.ArgumentParser(description="Draw an Obsidian vault as a gearbox, in one offline HTML file.")
    ap.add_argument("--vault", required=True, type=Path, help="the vault folder")
    ap.add_argument("--out", type=Path, default=HERE / "gearbox-graph.html", help="output HTML file")
    ap.add_argument("--config", type=Path, help="optional groups config (see groups.example.json)")
    ap.add_argument("--vault-name", help="Obsidian's name for the vault, if not the folder name")
    ap.add_argument("--template", type=Path, default=HERE / "template.html", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    vault = a.vault.expanduser().resolve()
    if not vault.is_dir():
        sys.exit(f"Not a folder: {vault}")
    try:
        cfg = load_config(a.config.expanduser()) if a.config else None
    except ConfigError as e:
        sys.exit(f"Config problem: {e}")
    data = build(vault, cfg, a.vault_name)
    if not data["nodes"]:
        sys.exit(f"No .md notes found in {vault}")
    html = render(data, a.template.read_text(encoding="utf-8"))
    a.out.write_text(html, encoding="utf-8")
    print(f"{len(data['nodes'])} notes, {len(data['edges'])} links -> {a.out}")


if __name__ == "__main__":
    main()
