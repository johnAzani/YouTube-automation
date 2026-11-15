"""Job headers are read by the fast YAML parser, and it must change nothing.

`pipeline.script_doc._load_yaml_mapping` reads the header of every queued and
published file. The watchdogs and the release planner call it thousands of times
per pass, and with PyYAML's pure Python parser that was nearly all of their
time: one supervisor pass spent 98% of its time parsing headers (measured 15
November 2026), and three unit tests took over two minutes each for the same
reason.

It now uses PyYAML's C parser (`CSafeLoader`) when PyYAML has one. These tests
hold the three things that make that safe:

1. every header in the repository reads to exactly the same value either way;
2. a header the fast parser refuses is handed to the reference parser, so
   nothing that could be read before can stop being readable;
3. it is still a *safe* loader: a header cannot construct Python objects.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import yaml

from pipeline import script_doc

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"


def _headers() -> list[tuple[str, str]]:
    found = []
    for path in sorted(CONTENT.rglob("*.md")):
        match = script_doc._FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if match:
            found.append((str(path.relative_to(ROOT)), match.group(1)))
    return found


class TheFastParserChangesNothing(unittest.TestCase):
    def test_this_installation_has_the_fast_parser(self):
        # requirements.txt installs PyYAML from a wheel, which includes it. If
        # this ever fails the code still works (see the last test), only slowly.
        self.assertIsNotNone(script_doc._FAST_SAFE_LOADER)
        self.assertTrue(issubclass(script_doc._FAST_SAFE_LOADER, yaml.cyaml.CSafeLoader))

    def test_every_header_in_the_repository_reads_the_same(self):
        headers = _headers()
        self.assertGreater(len(headers), 50, "the queue and receipts were not found")
        different = []
        for name, raw in headers:
            reference = yaml.safe_load(raw) or {}
            fast = script_doc._load_yaml_mapping(raw)
            # repr as well as ==, so 1 and 1.0, or True and 1, cannot pass as equal.
            if fast != reference or repr(fast) != repr(reference):
                different.append(name)
        self.assertEqual(different, [])

    def test_every_yaml_file_under_content_reads_the_same(self):
        different = []
        for path in sorted(CONTENT.rglob("*.yml")) + sorted(CONTENT.rglob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            try:
                reference = yaml.safe_load(text) or {}
            except yaml.YAMLError:
                continue  # not this test's subject; the next class covers errors
            if repr(script_doc._load_yaml_mapping(text)) != repr(reference):
                different.append(str(path.relative_to(ROOT)))
        self.assertEqual(different, [])

    def test_the_values_keep_their_types(self):
        meta = script_doc._load_yaml_mapping(
            'id: "0091"\n'
            "target_minutes: 8\n"
            "ratio: 0.85\n"
            "approved: true\n"
            "published_on: 2026-11-15\n"
            "tags: [prayer, midday]\n"
            "notes: |\n  first line\n  second line\n"
            "empty:\n"
        )
        self.assertEqual(meta["id"], "0091")
        self.assertIs(type(meta["target_minutes"]), int)
        self.assertIs(type(meta["ratio"]), float)
        self.assertIs(meta["approved"], True)
        self.assertEqual(meta["published_on"].isoformat(), "2026-11-15")
        self.assertEqual(meta["tags"], ["prayer", "midday"])
        self.assertEqual(meta["notes"], "first line\nsecond line\n")
        self.assertIsNone(meta["empty"])

    def test_an_empty_header_is_an_empty_mapping(self):
        self.assertEqual(script_doc._load_yaml_mapping(""), {})
        self.assertEqual(script_doc._load_yaml_mapping("# only a comment\n"), {})


class NothingReadableBecomesUnreadable(unittest.TestCase):
    def test_a_header_the_fast_parser_refuses_goes_to_the_reference_parser(self):
        class Refuses(yaml.SafeLoader):
            def __init__(self, stream):
                raise yaml.YAMLError("the fast parser refused this header")

        with mock.patch.object(script_doc, "_FAST_SAFE_LOADER", Refuses):
            meta = script_doc._load_yaml_mapping('id: "0091"\ntitle: Midday prayer\n')
        self.assertEqual(meta, {"id": "0091", "title": "Midday prayer"})

    def test_a_broken_header_still_raises_a_yaml_error(self):
        with self.assertRaises(yaml.YAMLError):
            script_doc._load_yaml_mapping('title: "never closed\nid: 7\n  bad: [\n')

    def test_it_works_without_the_fast_parser(self):
        with mock.patch.object(script_doc, "_FAST_SAFE_LOADER", None):
            meta = script_doc._load_yaml_mapping("id: 7\ntags: [a, b]\n")
        self.assertEqual(meta, {"id": 7, "tags": ["a", "b"]})


class AHeaderCannotRunCode(unittest.TestCase):
    def test_a_python_object_tag_is_refused(self):
        for raw in ("run: !!python/object/apply:os.system ['echo unsafe']\n",
                    "mod: !!python/name:os.system\n"):
            with self.subTest(raw=raw), self.assertRaises(yaml.YAMLError):
                script_doc._load_yaml_mapping(raw)


if __name__ == "__main__":
    unittest.main()
