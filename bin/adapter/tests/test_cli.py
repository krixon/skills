"""Tests for the present/act output substrate and the synthesis-halt shape."""

import io
import json
import unittest

from adapter import cli


class TestPresent(unittest.TestCase):
    def test_present_json_writes_object_and_newline(self):
        out = io.StringIO()
        rc = cli.present_json({"branch": "feat/1-x"}, stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue()), {"branch": "feat/1-x"})
        self.assertTrue(out.getvalue().endswith("\n"))

    def test_act_result_json(self):
        out = io.StringIO()
        rc = cli.acted({"created": "feat/1-x"}, stream=out)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.getvalue())["created"], "feat/1-x")


class TestHalt(unittest.TestCase):
    def test_halt_is_nonzero(self):
        err = io.StringIO()
        rc = cli.halt("rebase hit a conflict", details={"paths": ["a.py"]}, stream=err)
        self.assertNotEqual(rc, 0)

    def test_halt_writes_reason_to_stream(self):
        err = io.StringIO()
        cli.halt("dirty tree", stream=err)
        payload = json.loads(err.getvalue())
        self.assertEqual(payload["status"], "halted")
        self.assertEqual(payload["reason"], "dirty tree")

    def test_halt_carries_details(self):
        err = io.StringIO()
        cli.halt("conflict", details={"paths": ["a.py", "b.py"]}, stream=err)
        payload = json.loads(err.getvalue())
        self.assertEqual(payload["paths"], ["a.py", "b.py"])


if __name__ == "__main__":
    unittest.main()
