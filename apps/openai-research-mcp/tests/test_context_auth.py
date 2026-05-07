from __future__ import annotations

import unittest

from research_mcp.auth import TrustedHeaderAuthorizer


class ContextAuthTests(unittest.TestCase):
    def test_context_authorizer_accepts_named_context(self):
        authorizer = TrustedHeaderAuthorizer()
        ctx = authorizer.authorize_read(
            None,
            headers={"X-Subject": "reader", "X-Organization": "demo-org", "X-Scopes": "documents:read"},
        )
        self.assertEqual(ctx.subject, "reader")
        self.assertEqual(ctx.organization, "demo-org")


if __name__ == "__main__":
    unittest.main()
