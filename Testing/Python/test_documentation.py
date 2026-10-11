"""Documentation structure and active local links."""

import unittest
from scripts.audit_documentation import audit


class DocumentationTest(unittest.TestCase):
    def test_active_documents_are_consistent(self):
        result = audit()
        self.assertEqual(result["status"], "pass", result["findings"])
