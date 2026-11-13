import json
import unittest
from datetime import date, datetime
from io import BytesIO
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from daily import DAILY_REPORT, daily_summary, send_daily_summary
from remote import telegram

DAY = date(2026, 11, 12)
MIDNIGHT = datetime(2026, 11, 13, tzinfo=ZoneInfo("America/Sao_Paulo"))
SITE = {"id": "demo", "name": "Demo & Cia", "url": "https://example.com/"}


class DailyReportTests(unittest.TestCase):
    def history(self, checks):
        return {"demo": {"url": SITE["url"], "days": {DAY.isoformat(): checks}}}

    def test_summary_reports_recovered_outage_and_separates_integrity(self):
        summary = daily_summary(DAY, [SITE], self.history({"up": 94, "down": 1, "changed": 1}))
        self.assertIn("12/11/2026", summary)
        self.assertIn("Demo &amp; Cia", summary)
        self.assertIn("99.0% disponível em 96 checagens", summary)
        self.assertIn("1 fora do ar, 1 com alteração de conteúdo", summary)

    def test_summary_distinguishes_all_healthy_from_missing_checks(self):
        self.assertIn("100% das checagens registradas", daily_summary(DAY, [SITE], self.history({"up": 96})))
        summary = daily_summary(DAY, [SITE], {})
        self.assertIn("Nenhuma checagem registrada", summary)
        self.assertNotIn("100%", summary)

    def test_midnight_summary_retries_and_records_success_once(self):
        history = self.history({"up": 96})
        send = Mock(side_effect=[False, True])
        failed, delivered, duplicate = {}, {}, {}
        send_daily_summary(MIDNIGHT, [SITE], history, failed, send)
        self.assertNotIn(DAILY_REPORT, failed)
        send_daily_summary(MIDNIGHT, [SITE], history, delivered, send)
        self.assertEqual(delivered[DAILY_REPORT], DAY.isoformat())
        send_daily_summary(MIDNIGHT, [SITE], history | delivered, duplicate, send)
        self.assertEqual(duplicate, delivered)
        self.assertEqual(send.call_count, 2)

    def test_telegram_sends_to_optional_topic(self):
        for thread, expected in [("", {}), (" 42 ", {"message_thread_id": 42})]:
            env = {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "-1001",
                   "TELEGRAM_MESSAGE_THREAD_ID": thread}
            with self.subTest(thread=thread), patch.dict("os.environ", env), patch(
                "remote.urlopen", return_value=BytesIO(b'{"ok":true}')
            ) as request:
                self.assertTrue(telegram("Resumo"))
                payload = json.loads(request.call_args.args[0].data)
                self.assertEqual(payload.pop("chat_id"), "-1001")
                self.assertEqual({key: payload[key] for key in expected}, expected)
                self.assertEqual("message_thread_id" in payload, bool(expected))
