import unittest

import business_card_portal as portal


class PortalSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "drafts": [
                {
                    "draft_id": "draft-1",
                    "source_hash": "abc123",
                    "vendor_to": "vendor@example.com",
                    "vendor_cc": "manager@example.com",
                    "subject": "명함 발주",
                    "request_count": 2,
                    "attachment_paths": ["C:/requests/card.xlsx"],
                    "status": "ready",
                }
            ]
        }

    def test_digest_changes_when_recipient_changes(self) -> None:
        original = portal.draft_batch_digest(self.payload)
        changed = {"drafts": [{**self.payload["drafts"][0], "vendor_to": "other@example.com"}]}
        self.assertNotEqual(original, portal.draft_batch_digest(changed))

    def test_digest_changes_when_attachment_changes(self) -> None:
        original = portal.draft_batch_digest(self.payload)
        changed = {"drafts": [{**self.payload["drafts"][0], "attachment_paths": ["C:/requests/other.xlsx"]}]}
        self.assertNotEqual(original, portal.draft_batch_digest(changed))

    def test_digest_changes_when_html_body_changes(self) -> None:
        original = portal.draft_batch_digest(self.payload)
        changed = {"drafts": [{**self.payload["drafts"][0], "html_body": "<p>after</p>"}]}
        self.assertNotEqual(original, portal.draft_batch_digest(changed))

    def test_missing_csrf_is_rejected(self) -> None:
        digest = portal.draft_batch_digest(self.payload)
        self.assertFalse(portal.validate_send_request("secret", "", digest, digest))

    def test_wrong_digest_is_rejected(self) -> None:
        digest = portal.draft_batch_digest(self.payload)
        self.assertFalse(portal.validate_send_request("secret", "secret", digest, "outdated"))

    def test_matching_token_and_digest_are_accepted(self) -> None:
        digest = portal.draft_batch_digest(self.payload)
        self.assertTrue(portal.validate_send_request("secret", "secret", digest, digest))

    def test_confirm_page_contains_recipient_attachment_and_count(self) -> None:
        html = portal.render_send_confirmation(self.payload, "secret")
        self.assertIn("vendor@example.com", html)
        self.assertIn("card.xlsx", html)
        self.assertIn("신청 인원</th><td>2명", html)
        self.assertIn('name="csrf_token" value="secret"', html)
        self.assertIn('name="draft_digest"', html)


if __name__ == "__main__":
    unittest.main()
