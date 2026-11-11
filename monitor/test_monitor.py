import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from content import fingerprint
from remote import approved_history, git, load_snapshot, publish_snapshot
from run import update_record

SITE = {"id": "demo", "name": "Demo", "url": "https://example.com/", "hash": None}
NOW = datetime(2026, 11, 11, 15, tzinfo=timezone.utc)


def observation(text):
    html = f"<title>Demo</title><main><h1>Notícias</h1><p>{text}</p></main>"
    digest, sections = fingerprint(html, SITE, SITE["url"])
    return {"hash": digest, "sections": sections, "ms": 10}


class MonitorTests(unittest.TestCase):
    def update(self, site, observed, record, old=None, live=False):
        return update_record(
            [site], site, observed, record, old or {}, NOW, ["2026-11-11"], live
        )

    def test_ignores_dynamic_region_and_detects_link_replacement(self):
        site = dict(SITE, ignore=[".contador"])
        html = '<title>Demo</title><main><a href="/correto">Entrar</a><span class="contador">3</span></main>'
        original, _ = fingerprint(html, site, site["url"])
        self.assertEqual(original, fingerprint(html.replace(">3<", ">4<"), site, site["url"])[0])
        self.assertNotEqual(original, fingerprint(html.replace("/correto", "/alterado"), site, site["url"])[0])

    def test_normalizes_only_configured_link_fragments_and_image_parameters(self):
        site = dict(SITE, ignoreLinkFragments=["/email"], ignoreImageQuery=["v"])
        html = '<main><a href="/email#1">Contato</a><img src="/photo.png?v=1&amp;size=50"></main>'
        original, _ = fingerprint(html, site, site["url"])
        self.assertEqual(original, fingerprint(html.replace("#1", "#2").replace("v=1", "v=2"), site, site["url"])[0])
        self.assertNotEqual(original, fingerprint(html.replace("size=50", "size=80"), site, site["url"])[0])
        self.assertNotEqual(original, fingerprint(html.replace("/photo.png", "/other.png"), site, site["url"])[0])

    def test_baseline_proposal_and_change_alert_are_sent_once(self):
        original = observation("Versão original")
        changed = observation("Versão alterada")
        pull = {"state": "open", "number": 1, "html_url": "https://github.com/a/b/pull/1",
                "body": f"Hash: `{original['hash']}`"}
        with patch("run.initial_pr", return_value=pull), patch("run.telegram", return_value=True) as telegram:
            record, report = self.update(SITE, original, {}, live=True)
            self.assertEqual(report["status"], "pending")
            self.assertIn(pull["html_url"], telegram.call_args.args[0])
            record, _ = self.update(SITE, original, record, live=True)
            telegram.assert_called_once()
            approved = dict(SITE, hash=original["hash"])
            record, report = self.update(approved, original, record, live=True)
            self.assertEqual(report["status"], "up")
            record, report = self.update(approved, changed, record, live=True)
            self.assertEqual(report["status"], "changed")
            self.assertIn("Notícias", telegram.call_args.args[0])
            self.assertIn(changed["hash"], telegram.call_args.args[0])
            _, report = self.update(approved, changed, record, live=True)
            self.assertEqual(report["status"], "changed")
            self.assertEqual(telegram.call_count, 2)

    def test_availability_and_previously_approved_hash(self):
        original = observation("Versão original")
        latest = observation("Versão nova")
        site = dict(SITE, hash=latest["hash"])
        record, report = self.update(site, original, {}, {original["hash"]: NOW.isoformat()})
        self.assertEqual(report["status"], "up")
        record, report = self.update(site, original, record)
        self.assertEqual(report["status"], "changed")
        _, report = self.update(site, {"status": "down", "reason": "HTTP 503"}, record)
        self.assertEqual(report["status"], "down")
        self.assertEqual(report["uptime"], 66.67)


class GitTests(unittest.TestCase):
    def test_retention_and_replacing_dist_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            previous = Path.cwd()
            os.chdir(temporary)
            try:
                self.exercise_git()
            finally:
                os.chdir(previous)

    def exercise_git(self):
        git("init", "-q", "-b", "main")
        git("config", "user.name", "Monitor")
        git("config", "user.email", "monitor@example.com")
        first = observation("Primeira")["hash"]
        second = observation("Segunda")["hash"]
        third = observation("Terceira")["hash"]
        for days, digest in [(120, first), (100, second), (20, third)]:
            date = (NOW - timedelta(days=days)).isoformat()
            Path("sites.json").write_text(json.dumps([dict(SITE, hash=digest)]), encoding="utf-8")
            git("add", "sites.json")
            env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
            git("commit", "-qm", "Aprovar", env=env)
        history = approved_history(NOW - timedelta(days=90))
        self.assertEqual(set(history[(SITE["id"], SITE["url"])]), {second})

        subprocess.run(["git", "init", "-q", "--bare", "remote"], check=True)
        git("remote", "add", "origin", str(Path("remote").resolve()))
        public = Path("public")
        public.mkdir()
        (public / "status.json").write_text("{}", encoding="utf-8")
        head, state = load_snapshot()
        self.assertEqual((head, state), ("", {}))
        publish_snapshot(public, {"checks": 1}, head)
        head, state = load_snapshot()
        self.assertEqual(state, {"checks": 1})
        publish_snapshot(public, {"checks": 2}, head)
        new_head, state = load_snapshot()
        self.assertNotEqual(new_head, head)
        self.assertEqual(state, {"checks": 2})
        self.assertEqual(git("rev-list", "--count", new_head), "1")


if __name__ == "__main__":
    unittest.main()
