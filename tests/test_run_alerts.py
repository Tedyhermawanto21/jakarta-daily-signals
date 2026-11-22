"""run_alerts dedup flow against an in-memory store."""

from datetime import date

import pytest

from jds.alerts.rules import Anomaly
from jds.alerts.run_alerts import run

REPORT = date(2026, 11, 18)
PM = Anomaly(date(2026, 11, 17), "pm25_high", "jkt_monas", "PM2.5 rata-rata 79.0")


class FakeStore:
    def __init__(self, candidates=(PM,)):
        self.log: dict[tuple, str] = {}
        self.candidates = list(candidates)

    def summary_status(self, d):
        return self.log.get((d, "daily_summary", "all"))

    def load_signals(self, d):
        return {"date_wib": date(2026, 11, 17), "aq_is_complete": False}, None

    def load_candidates(self, yesterday, fx_date):
        return self.candidates

    def sent_keys(self, candidates):
        return {a.key for a in candidates if self.log.get(a.key) == "sent"}

    def reserve_summary(self, d):
        key = (d, "daily_summary", "all")
        if key in self.log:
            return False
        self.log[key] = "sending"
        return True

    def release_summary(self, d):
        if self.log.get((d, "daily_summary", "all")) == "sending":
            del self.log[(d, "daily_summary", "all")]

    def mark_sent(self, d, anomalies, message_id, text):
        self.log[(d, "daily_summary", "all")] = "sent"
        for a in anomalies:
            self.log[a.key] = "sent"


class Sender:
    def __init__(self, fail=False):
        self.sent: list[str] = []
        self.fail = fail

    def __call__(self, text):
        if self.fail:
            raise RuntimeError("telegram down")
        self.sent.append(text)
        return len(self.sent)


def test_rerun_same_day_sends_only_once():
    store, sender = FakeStore(), Sender()
    assert run(REPORT, store, sender, dry_run=False) == 0
    assert run(REPORT, store, sender, dry_run=False) == 0
    assert len(sender.sent) == 1
    assert sender.sent[0].startswith("⚠️")


def test_dry_run_sends_nothing_and_writes_nothing():
    store, sender = FakeStore(), Sender()
    assert run(REPORT, store, sender, dry_run=True) == 0
    assert sender.sent == [] and store.log == {}


def test_failed_send_releases_reservation_so_next_run_retries():
    store = FakeStore()
    with pytest.raises(RuntimeError):
        run(REPORT, store, Sender(fail=True), dry_run=False)
    assert store.log == {}
    sender = Sender()
    assert run(REPORT, store, sender, dry_run=False) == 0
    assert len(sender.sent) == 1


def test_anomaly_already_reported_is_not_flagged_again_next_day():
    store, sender = FakeStore(), Sender()
    run(REPORT, store, sender, dry_run=False)
    run(date(2026, 11, 19), store, sender, dry_run=False)  # same candidate again
    assert sender.sent[0].startswith("⚠️")
    assert sender.sent[1].startswith("✅")


def test_stuck_sending_is_not_resent_and_exits_1():
    store, sender = FakeStore(), Sender()
    store.log[(REPORT, "daily_summary", "all")] = "sending"
    assert run(REPORT, store, sender, dry_run=False) == 1
    assert sender.sent == []
