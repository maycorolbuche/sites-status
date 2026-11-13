from datetime import timedelta
from html import escape

DAILY_REPORT = "_daily_report"
STATUS_LABELS = {
    "down": "fora do ar",
    "changed": "com alteração de conteúdo",
    "pending": "aguardando aprovação de hash",
    "unverified": "com integridade não verificada",
}


def daily_summary(date, sites, history):
    lines = [f"📊 <b>Resumo dos sites · {date:%d/%m/%Y}</b>"]
    details = []
    total_checks = offline_checks = without_checks = affected_sites = 0
    for site in sites:
        record = history.get(site["id"], {})
        checks = record.get("days", {}).get(date.isoformat(), {}) if record.get("url") == site["url"] else {}
        samples = sum(checks.values())
        total_checks += samples
        offline_checks += checks.get("down", 0)
        name = escape(site["name"].strip()[:200])
        if not samples:
            without_checks += 1
            details.append(f"⚪ <b>{name}</b> · sem checagens")
            continue
        issues = [f"{checks[key]} {label}" for key, label in STATUS_LABELS.items() if checks.get(key)]
        if issues:
            affected_sites += 1
            availability = 100 * (samples - checks.get("down", 0)) / samples
            icon = "🔴" if checks.get("down") else "🟡"
            details.append(
                f"{icon} <b>{name}</b> · {availability:.1f}% disponível em {samples} checagens"
                f"\n{', '.join(issues)}"
            )

    if not total_checks:
        lines.append("⚪ Nenhuma checagem registrada no dia.")
    elif not affected_sites and not without_checks:
        lines.append("✅ Todos os sites operaram normalmente em 100% das checagens registradas.")
    elif not offline_checks and not without_checks:
        lines.append("🟡 Todos os sites responderam em 100% das checagens, com ocorrências de integridade.")
    else:
        lines.append("Confira as ocorrências e a cobertura das checagens abaixo.")

    lines.append(
        f"{len(sites)} sites · {total_checks} checagens · {offline_checks} falhas de disponibilidade"
        f"\n{affected_sites} sites com ocorrências · {without_checks} sem checagens"
    )
    message = "\n\n".join(lines)
    for index, detail in enumerate(details):
        if len(message) + len(detail) > 3900:
            message += f"\n\nMais {len(details) - index} sites com ocorrências ou sem checagens."
            break
        message += f"\n\n{detail}"
    return message


def send_daily_summary(now, sites, previous, state, send):
    date = now.date() - timedelta(days=1)
    last_sent = previous.get(DAILY_REPORT)
    if last_sent:
        state[DAILY_REPORT] = last_sent
        if last_sent >= date.isoformat():
            return
    if send(daily_summary(date, sites, previous)):
        state[DAILY_REPORT] = date.isoformat()
