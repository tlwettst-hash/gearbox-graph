"""Tests for the gearbox-graph engine. Run from the repo root:  python3 -m unittest discover tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import gearbox_graph as gg  # noqa: E402


def make_vault(tmp: Path, notes: dict) -> Path:
    """notes: {"Folder/Name.md": "text"}"""
    for rel, text in notes.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp


class Links(unittest.TestCase):
    def test_basename_path_alias_heading_and_embed(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(Path(t), {
                "A/One.md": "[[Two]] [[B/Three|alias]] [[Two#Heading]] ![[Three]] [[Missing]] [[One]]",
                "A/Two.md": "", "B/Three.md": ""})
            d = gg.build(v)
            names = [n["t"] for n in d["nodes"]]
            pairs = {tuple(sorted((names[a], names[b]))) for a, b in d["edges"]}
            self.assertEqual(pairs, {("One", "Two"), ("One", "Three")})   # no self-link, no dangling link

    def test_hidden_and_tool_folders_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(Path(t), {"Note.md": "", ".obsidian/x.md": "", ".trash/y.md": "", "node_modules/z.md": ""})
            self.assertEqual([n["t"] for n in gg.build(v)["nodes"]], ["Note"])


class Groups(unittest.TestCase):
    def test_auto_groups_by_top_folder_with_generated_ids(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(Path(t), {"Big/a.md": "", "Big/b.md": "", "__proto__/c.md": "", "root.md": ""})
            d = gg.build(v)
            by_title = {n["t"]: n["g"] for n in d["nodes"]}
            self.assertEqual(by_title["a"], "g0")          # biggest folder first
            self.assertEqual(by_title["c"], "g1")          # odd folder name never becomes an id
            self.assertEqual(by_title["root"], "root")
            self.assertEqual(d["groups"]["g1"]["label"], "__proto__")

    def test_overflow_folders_share_other(self):
        with tempfile.TemporaryDirectory() as t:
            notes = {f"F{i:02d}/n{i}.md": "" for i in range(len(gg.PALETTE) + 2)}
            d = gg.build(make_vault(Path(t), notes))
            self.assertIn("other", d["groups"])
            self.assertEqual(len(d["groups"]), len(gg.PALETTE) + 1)

    def test_config_tags_folders_and_folders_win(self):
        cfg = {"groups": {"work": {"label": "Work", "color": "#C91A09"},
                          "home": {"label": "Home", "color": "#0055BF"},
                          "misc": {"label": "Misc", "color": "#A0A5A9"}},
               "folders": {"Jobs": "work", "Diary": "home"},
               "tags": {"Garden": "home"}, "folders_win": ["Diary"], "fallback": "misc"}
        with tempfile.TemporaryDirectory() as t:
            tp = Path(t)
            (tp / "cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
            v = make_vault(tp / "v", {
                "Jobs/a.md": "",
                "Jobs/b.md": "---\nproject: garden\n---\n",     # tag beats folder
                "Diary/c.md": "---\nproject: garden\n---\n",    # but not in a folders_win folder
                "Stuff/d.md": "", "e.md": ""})
            d = gg.build(v, gg.load_config(tp / "cfg.json"))
            g = {n["t"]: n["g"] for n in d["nodes"]}
            self.assertEqual(g, {"a": "work", "b": "home", "c": "home", "d": "misc", "e": "misc"})


class ConfigValidation(unittest.TestCase):
    GOOD = {"groups": {"a": {"label": "A", "color": "#123456"}}, "fallback": "a"}

    def check_bad(self, cfg, fragment):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "c.json"
            p.write_text(cfg if isinstance(cfg, str) else json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(gg.ConfigError) as cm:
                gg.load_config(p)
            self.assertIn(fragment, str(cm.exception))

    def test_good_config_loads(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "c.json"
            p.write_text(json.dumps(self.GOOD), encoding="utf-8")
            self.assertEqual(gg.load_config(p)["fallback"], "a")

    def test_rejects_bad_configs(self):
        g = self.GOOD["groups"]
        self.check_bad("{not json", "can't read")
        self.check_bad([], "JSON object")
        self.check_bad({**self.GOOD, "extra": 1}, "unknown config keys")
        self.check_bad({"groups": {"Bad Id!": {"label": "x", "color": "#123456"}}, "fallback": "Bad Id!"}, "group id")
        self.check_bad({"groups": {"a": {"label": "x", "color": "red"}}, "fallback": "a"}, "color")
        self.check_bad({"groups": {"a": {"label": "x", "color": "#123456';alert(1)//"}}, "fallback": "a"}, "color")
        self.check_bad({"groups": {"a": {"label": "x" * 61, "color": "#123456"}}, "fallback": "a"}, "label")
        self.check_bad({"groups": {"a": {"label": "x", "color": "#123456", "js": 1}}, "fallback": "a"}, "exactly")
        self.check_bad({"groups": g, "folders": {"F": "nope"}, "fallback": "a"}, '"folders"')
        self.check_bad({"groups": g, "folders_win": ["F"], "fallback": "a"}, "folders_win")
        self.check_bad({"groups": g}, "fallback")


class Render(unittest.TestCase):
    def test_hostile_title_cannot_break_out_of_script(self):
        data = {"vault": "v", "groups": {}, "edges": [],
                "nodes": [{"t": "</script><script>alert(1)</script><!--", "p": "x.md", "g": "g0"},
                          {"t": "line sep", "p": "y.md", "g": "g0"}]}
        html = gg.render(data, "<script>const DATA = /*__DATA__*/null;</script>")
        self.assertEqual(html.count("</script>"), 1)
        self.assertNotIn("<!--", html)
        self.assertNotIn(" ", html)
        blob = html[len("<script>const DATA = "):-len(";</script>")]
        self.assertEqual(json.loads(blob), data)   # escaping doesn't change the data

    def test_missing_placeholder_is_an_error(self):
        with self.assertRaises(ValueError):
            gg.render({}, "<html></html>")

    def test_template_has_placeholder_and_no_network(self):
        html = (ROOT / "template.html").read_text(encoding="utf-8")
        self.assertIn("/*__DATA__*/null", html)
        for bad in ("http://", "https://", "fetch(", "XMLHttpRequest", "eval(", "new Function", "<script src"):
            self.assertNotIn(bad, html)


class DemoVault(unittest.TestCase):
    def test_demo_vault_builds_with_gears(self):
        d = gg.build(ROOT / "demo-vault")
        self.assertGreater(len(d["nodes"]), 40)
        self.assertGreater(len(d["edges"]), 100)


class NoBrandNames(unittest.TestCase):
    def test_no_toy_brand_words_in_repo(self):
        # Spelled in pieces so this file doesn't match itself.
        words = ["le" + "go", "tech" + "nic", "brick" + "link", "lift" + "arm"]
        for p in ROOT.rglob("*"):
            if not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
                continue
            if p.suffix.lower() in (".png", ".ico") or p.name in ("gearbox-graph.html", ".vault-path", ".DS_Store"):
                continue
            text = p.read_text(encoding="utf-8", errors="replace").lower()
            for w in words:
                self.assertNotIn(w, text, f"{p.relative_to(ROOT)} mentions {w}")


if __name__ == "__main__":
    unittest.main()
