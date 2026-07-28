import unittest

import business_card_mailer as mailer


class DashboardRejectionTests(unittest.TestCase):
    def test_dashboard_hides_rejected_non_business_card_files(self) -> None:
        payload = {
            "generated_at": "2026-07-27T09:00:00",
            "request_file_count": 1,
            "draft_count": 0,
            "ready_count": 0,
            "pending_count": 0,
            "parse_errors": [],
            "rejected_files": [
                {
                    "file": "\uc5f0\ucc28\uacc4\ud68d.xlsx",
                    "reason": "\uba85\ud568 \uc2e0\uccad\uc11c \ud575\uc2ec \ud5e4\ub354 \uae30\uc900\uc744 \ucda9\uc871\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
                }
            ],
            "drafts": [],
        }

        html = mailer.render_dashboard_html(payload, mailer.DEFAULT_TEMPLATE, {}, {}, {})

        self.assertNotIn("\uc5f0\ucc28\uacc4\ud68d.xlsx", html)
        self.assertNotIn("\uba85\ud568 \uc2e0\uccad\uc11c \ud575\uc2ec \ud5e4\ub354 \uae30\uc900\uc744 \ucda9\uc871\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.", html)
        self.assertIn('<span class="section-count">0\uac74</span>', html)
        self.assertIn("\ud604\uc7ac \uc6b0\uc120 \ucc98\ub9ac\ud560 \ud56d\ubaa9\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.", html)


if __name__ == "__main__":
    unittest.main()