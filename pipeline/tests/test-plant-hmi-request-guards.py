"""Tests for the shared write-route guard (CSRF + DNS rebinding).

Run: .venv/bin/python tests/test-plant-hmi-request-guards.py
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException  # noqa: E402

from plant_hmi.plant_request_guards import _host_allowed, require_trusted_request  # noqa: E402


class FakeRequest:
    def __init__(self, **headers):
        self.headers = {k.replace("_", "-").lower(): v for k, v in headers.items()}


class HostAllowlistTest(unittest.TestCase):
    def test_local_ips_and_single_label_names_pass(self):
        for host in ("127.0.0.1:7860", "localhost:7860", "[::1]:7860", "sontn-x99:7860", "testserver"):
            self.assertTrue(_host_allowed(host), host)

    def test_rebinding_domains_and_foreign_ips_blocked(self):
        for host in ("evil.example:7860", "sontn-x99.evil.com", "192.0.2.10:7860", "", ":7860"):
            self.assertFalse(_host_allowed(host), host)

    def test_env_allowlist_admits_magicdns_name(self):
        with mock.patch.dict(os.environ, {"PLANT_HMI_ALLOWED_HOSTS": "sontn-x99.tail1234.ts.net"}):
            self.assertTrue(_host_allowed("sontn-x99.tail1234.ts.net:7860"))
            self.assertFalse(_host_allowed("other.tail1234.ts.net:7860"))


class GuardTest(unittest.TestCase):
    def check(self, header="1", **headers):
        try:
            require_trusted_request(FakeRequest(**headers), header)
            return 200
        except HTTPException as exc:
            return exc.status_code

    def test_guard_order(self):
        self.assertEqual(self.check(None, host="127.0.0.1:7860"), 403)                 # no header
        self.assertEqual(self.check(host="evil.example:7860", origin="http://evil.example:7860"), 403)  # rebinding
        self.assertEqual(self.check(host="127.0.0.1:7860", origin="https://evil.example"), 403)       # CSRF
        self.assertEqual(self.check(host="127.0.0.1:7860", sec_fetch_site="cross-site"), 403)
        self.assertEqual(self.check(host="127.0.0.1:7860", origin="http://127.0.0.1:7860",
                                    sec_fetch_site="same-origin"), 200)
        self.assertEqual(self.check(host="127.0.0.1:7860"), 200)                       # curl


if __name__ == "__main__":
    unittest.main(verbosity=2)
