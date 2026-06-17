"""Tests for the present/act output substrate and the synthesis-halt shape.

The two-zone envelope (ADR 0009): neutral fields at the top level, all
adapter-specific data under one reserved `info` key nothing branches on; act and
halt results carry a closed `outcome` code with free text confined to `message`.
"""

from __future__ import annotations

import io
import json
import unittest

from adapter import cli


class TestPresent(unittest.TestCase):
    def test_present_json_writes_object_and_newline(self) -> None:
        out = io.StringIO()
        rc = cli.present_json({"branch": "feat/1-x"}, stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue()), {"branch": "feat/1-x"})
        self.assertTrue(out.getvalue().endswith("\n"))


class TestActed(unittest.TestCase):
    def test_acted_carries_coded_outcome(self) -> None:
        out = io.StringIO()
        rc = cli.acted(cli.OK, stream=out)
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["outcome"], "ok")

    def test_acted_confines_free_text_to_message(self) -> None:
        out = io.StringIO()
        cli.acted(cli.OK, message="created issue 7", stream=out)
        payload = json.loads(out.getvalue())
        # Human-readable explanation lives only in message, never the outcome.
        self.assertEqual(payload["outcome"], "ok")
        self.assertEqual(payload["message"], "created issue 7")

    def test_acted_quarantines_adapter_specifics_under_info(self) -> None:
        out = io.StringIO()
        cli.acted(cli.OK, info={"url": "https://x", "number": 7}, stream=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["info"], {"url": "https://x", "number": 7})

    def test_acted_lifts_neutral_fields_to_top_level(self) -> None:
        out = io.StringIO()
        cli.acted(cli.OK, fields={"id": "7"}, info={"number": 7}, stream=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["id"], "7")
        self.assertEqual(payload["info"]["number"], 7)

    def test_outcome_must_be_in_the_closed_vocabulary(self) -> None:
        out = io.StringIO()
        with self.assertRaises(ValueError):
            cli.acted("made-up", stream=out)


class TestHalt(unittest.TestCase):
    def test_halt_is_nonzero(self) -> None:
        err = io.StringIO()
        rc = cli.halt(cli.UNSUPPORTED, message="no jira backend", stream=err)
        self.assertNotEqual(rc, 0)

    def test_halt_carries_coded_outcome_and_message(self) -> None:
        err = io.StringIO()
        cli.halt(cli.UNCONFIGURED, message="bot identity half-configured",
                 stream=err)
        payload = json.loads(err.getvalue())
        self.assertEqual(payload["outcome"], "unconfigured")
        self.assertEqual(payload["message"], "bot identity half-configured")

    def test_halt_quarantines_specifics_under_info(self) -> None:
        err = io.StringIO()
        cli.halt(cli.CONFLICT, message="rebase hit a conflict",
                 info={"paths": ["a.py", "b.py"]}, stream=err)
        payload = json.loads(err.getvalue())
        self.assertEqual(payload["info"]["paths"], ["a.py", "b.py"])


if __name__ == "__main__":
    unittest.main()
