import argparse
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape
from os.path import commonprefix
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from content import capture_scope, check
from remote import CONFIG, approved_history, initial_pr, load_snapshot, publish_snapshot, telegram

DAYS = 90
MINUTES_PER_SLOT = 15
LOCAL_ZONE = ZoneInfo("America/Sao_Paulo")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SELECTOR = re.compile(r"[.#]?[a-zA-Z][\w-]*")


def load_sites():
    sites = json.loads(Path(CONFIG).read_text(encoding="utf-8"))
    ids = set()
    for site in sites:
        identifier = site["id"]
        url = urlsplit(site["url"])
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier) or identifier in ids:
            raise ValueError(f"ID inválido ou repetido: {identifier}")
        if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None:
            raise ValueError(f"URL inválida para {identifier}")
        if site["hash"] is not None and not DIGEST.fullmatch(site["hash"]):
            raise ValueError(f"Hash inválida para {identifier}")
        mode = site.get("hashMode")
        if "hashMode" in site and mode not in ("title", "page", "element"):
            raise ValueError(f"hashMode inválido para {identifier}")
        if mode == "element" and not site.get("selector"):
            raise ValueError(f"Modo element exige selector para {identifier}")
        if mode in ("title", "page") and "selector" in site:
            raise ValueError(f"Modo {mode} não usa selector para {identifier}")
        if not site["name"].strip() or any(
            not SELECTOR.fullmatch(selector)
            for selector in [site.get("selector", "main"), *site.get("ignore", [])]
        ):
            raise ValueError(f"Nome ou seletor inválido para {identifier}")
        ids.add(identifier)
    return sites


def differences(before, after):
    if before is None:
        return "Comparação detalhada indisponível para a referência aprovada."
    lines = []
    for label in dict.fromkeys([*before, *after]):
        old, new = before.get(label), after.get(label)
        if old == new:
            continue
        if old is None:
            lines.append(f"• {label}: seção adicionada")
        elif new is None:
            lines.append(f"• {label}: seção removida")
        elif old["excerpt"] == new["excerpt"]:
            lines.append(f"• {label}: conteúdo alterado")
        else:
            before_text, after_text = old["excerpt"], new["excerpt"]
            start = max(0, len(commonprefix([before_text, after_text])) - 30)
            prefix = "…" if start else ""
            lines.append(
                f"• {label}: {prefix}{before_text[start:start + 100]} → "
                f"{prefix}{after_text[start:start + 100]}"
            )
        if len(lines) == 6:
            break
    return "\n".join(lines) or "Diferença fora dos trechos guardados para comparação."


def classify(site, result, record, valid):
    digest = result.get("hash")
    if not digest:
        return result["status"]
    if not site["hash"]:
        return "pending"
    if digest in valid:
        record["last_approved"] = digest
        return "up"
    return "changed"


def alert_message(site, icon, details):
    name = site["name"].strip()[:200]
    url = site["url"][:1000]
    limit = 3900 - len(icon) - len(name) - len(url) - 4
    return f"{icon} <b>{escape(name)}</b>\n{escape(url)}\n\n{escape(details[:limit])}"


def initial_alert(sites, site, digest, record):
    try:
        pull = initial_pr(sites, site, digest)
    except RuntimeError:
        print(f"::warning::Não foi possível abrir o PR inicial de {site['id']}. Confira as permissões do Actions.")
        return None
    if pull["state"] != "open":
        return None
    url = pull["html_url"]
    key = f"pr:{pull['number']}"
    proposal = next(
        (line.replace("`", "") for line in (pull.get("body") or "").splitlines() if line.startswith("Hash: ")),
        "Hash registrada no PR",
    )
    if record.get("initial_notified") != key and telegram(
        alert_message(site, "🔎", f"Hash inicial registrada para aprovação\n\n{proposal}\n{url}")
    ):
        record["initial_notified"] = key
    return url


def update_record(sites, site, result, record, past, now, dates, live):
    if record.get("url") != site["url"]:
        record = {"url": site["url"]}
    scope = list(capture_scope(site))
    if record.get("capture_scope", ["legacy", site.get("selector", "main")]) != scope:
        record = {
            "url": site["url"],
            "days": record.get("days", {}),
            "today": record.get("today"),
        }
    record["capture_scope"] = scope
    digest = result.get("hash")
    current = site["hash"]
    valid = set(past) | {current} if current else set()
    status = classify(site, result, record, valid)
    recent = record.setdefault("snapshots", {})
    cutoff = now - timedelta(days=DAYS)
    recent = {
        key: value for key, value in recent.items()
        if key in valid or datetime.fromisoformat(value["at"]) > cutoff
    }
    if digest:
        recent[digest] = {"at": now.isoformat(), "fields": result["sections"]}
    candidates = sorted(
        (key for key in recent if key not in valid),
        key=lambda key: recent[key]["at"], reverse=True,
    )
    record["snapshots"] = {key: recent[key] for key in recent if key in valid or key in candidates[:16]}

    approval_url = None
    if live and status == "pending":
        approval_url = initial_alert(sites, site, digest, record)

    if status in {"down", "changed"}:
        key = status if status == "down" else f"changed:{digest}"
        if record.get("active_alert") != key:
            record["active_alert"] = key
            record.pop("alert", None)
        if live and record.get("alert") != key:
            if status == "down":
                icon = "🔴"
                details = f"Site fora do ar\n\n{result['reason']}"
            else:
                baseline = record.get("last_approved")
                if baseline not in valid:
                    baseline = current
                diff = differences(recent.get(baseline, {}).get("fields"), result["sections"])
                icon = "🟡"
                details = f"Alteração detectada\n\nHash para aprovação: {digest}\n\n{diff}"
            if telegram(alert_message(site, icon, details)):
                record["alert"] = key
    else:
        record.pop("active_alert", None)
        record.pop("alert", None)

    history = record.get("days", {})
    history = {date: history[date] for date in dates if date in history}
    today = history.setdefault(dates[-1], {})
    today[status] = today.get(status, 0) + 1
    record["days"] = history

    local = now.astimezone(LOCAL_ZONE)
    date = local.date().isoformat()
    timeline = record.get("today") or {}
    if timeline.get("date") != date:
        timeline = {"date": date, "slots": {}}
    slot = str((local.hour * 60 + local.minute) // MINUTES_PER_SLOT)
    timeline["slots"].setdefault(slot, []).append({"at": now.isoformat(), "status": status})
    record["today"] = timeline

    offline = sum(day.get("down", 0) for day in history.values())
    samples = sum(sum(day.values()) for day in history.values())
    report = {
        "name": site["name"], "url": site["url"], "status": status,
        "checkedAt": now.isoformat(), "responseMs": result.get("ms"),
        "reason": result.get("reason"), "approvalUrl": approval_url,
        "uptime": round(100 * (samples - offline) / samples, 2),
        "days": [{"date": date, "checks": history.get(date, {})} for date in dates],
        "today": timeline,
    }
    return record, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    sites = load_sites()
    now = datetime.now(timezone.utc)
    local_date = now.astimezone(LOCAL_ZONE).date()
    dates = [(local_date - timedelta(days=offset)).isoformat() for offset in reversed(range(DAYS))]
    previous, old_state = load_snapshot() if args.live else ("", {})
    approvals = approved_history(now - timedelta(days=DAYS)) if args.live else {}

    public = Path(".build/public")
    public.mkdir(parents=True, exist_ok=True)
    for path in Path("web").iterdir():
        shutil.copy2(path, public / path.name)
    reports, state = [], {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(check, sites))
    for site, result in zip(sites, results, strict=True):
        key = site["id"]
        state[key], report = update_record(
            sites, site, result, old_state.get(key, {}),
            approvals.get((key, site["url"], *capture_scope(site)), {}), now, dates, args.live,
        )
        reports.append(report)
        print(f"{key}: {report['status']}")
    (public / "status.json").write_text(
        json.dumps({"updatedAt": now.isoformat(), "sites": reports}, ensure_ascii=False),
        encoding="utf-8",
    )
    if args.live:
        publish_snapshot(public, state, previous)


if __name__ == "__main__":
    main()
