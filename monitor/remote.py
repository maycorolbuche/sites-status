import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.request import Request, urlopen

from content import capture_scope

CONFIG = "sites.json"
DIST = "refs/heads/dist"
STATE = ".monitor-state.json"


def run(*args, data=None, env=None, check=True):
    result = subprocess.run(
        args, input=data, text=True, encoding="utf-8", capture_output=True, env=env
    )
    if check and result.returncode:
        raise RuntimeError(f"Falha ao executar {args[0]} {args[1]}.")
    return result


def git(*args, **kwargs):
    return run("git", *args, **kwargs).stdout.strip()


def remote_head(ref):
    result = run("git", "ls-remote", "--exit-code", "origin", ref, check=False)
    if result.returncode == 2:
        return ""
    if result.returncode:
        raise RuntimeError("Falha ao consultar a branch remota.")
    return result.stdout.split()[0]


def push(ref, commit, previous):
    git("push", f"--force-with-lease={ref}:{previous}", "origin", f"{commit}:{ref}")


def load_snapshot():
    previous = remote_head(DIST)
    if not previous:
        return previous, {}
    git("fetch", "--no-tags", "origin", DIST)
    return previous, json.loads(git("show", f"{previous}:{STATE}"))


def publish_snapshot(public, state, previous):
    with TemporaryDirectory() as temporary:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        # Populate a fresh index without changing the checkout or chaining snapshots.
        for path in sorted(public.iterdir()):
            blob = git("hash-object", "-w", str(path))
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path.name}", env=env)
        blob = git("hash-object", "-w", "--stdin", data=json.dumps(state, ensure_ascii=False))
        git("update-index", "--add", "--cacheinfo", f"100644,{blob},{STATE}", env=env)
        tree = git("write-tree", env=env)
        commit = git("commit-tree", tree, "-m", "Atualizar painel de status")
    push(DIST, commit, previous)


def approved_history(cutoff):
    """Read dates of replacements, including merges between scheduled runs."""
    approvals = {}
    commits = git(
        "log", "--first-parent", "--full-history", f"--since-as-filter={cutoff.isoformat()}",
        "--format=%H %cI", "--", CONFIG
    )
    for line in reversed(commits.splitlines()):
        commit, stamp = line.split()
        previous = run("git", "show", f"{commit}^1:{CONFIG}", check=False)
        current = run("git", "show", f"{commit}:{CONFIG}", check=False)
        if previous.returncode or current.returncode:
            continue
        sites = {site["id"]: site for site in json.loads(current.stdout)}
        for old in json.loads(previous.stdout):
            new = sites.get(old["id"])
            if new and old["url"] == new["url"] and old["hash"] and old["hash"] != new["hash"]:
                approvals.setdefault((old["id"], old["url"], *capture_scope(old)), {})[old["hash"]] = stamp
    return approvals


def initial_pr(sites, site, digest):
    repository = os.environ["GITHUB_REPOSITORY"]
    owner = repository.split("/")[0]
    branch = f"monitor/hash-inicial/{site['id']}"
    ref = f"refs/heads/{branch}"
    endpoint = f"repos/{repository}/pulls"
    pulls = json.loads(run(
        "gh", "api", "--method", "GET", endpoint, "-f", f"head={owner}:{branch}",
        "-f", "state=all", "-f", "base=main",
    ).stdout)
    for pull in pulls:
        if pull["state"] == "open":
            return pull
    marker = f"Hash: `{digest}`"
    for pull in pulls:
        if marker in (pull["body"] or ""):
            return pull

    contents = [dict(item, hash=digest) if item["id"] == site["id"] else item for item in sites]
    previous = remote_head(ref)
    with TemporaryDirectory() as temporary:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        git("read-tree", "HEAD", env=env)
        blob = git("hash-object", "-w", "--stdin", data=json.dumps(contents, indent=2, ensure_ascii=False) + "\n")
        git("update-index", "--cacheinfo", f"100644,{blob},{CONFIG}", env=env)
        tree = git("write-tree", env=env)
        commit = git("commit-tree", tree, "-p", "HEAD", "-m", f"Registrar hash inicial de {site['name']}")
    push(ref, commit, previous)
    body = (
        f"Primeira referência de integridade para {site['name']}.\n\n"
        f"URL: {site['url']}\n\n{marker}\n\n"
        "Confira o conteúdo do site antes de aprovar a referência."
    )
    return json.loads(run(
        "gh", "api", "--method", "POST", endpoint, "-f", f"head={branch}",
        "-f", "base=main", "-f", f"title=Registrar hash inicial de {site['name']}",
        "-f", f"body={body}",
    ).stdout)


def telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    payload = json.dumps({
        "chat_id": chat, "text": message, "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }).encode()
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response).get("ok", False)
    except (URLError, OSError, ValueError):
        print("::warning::Falha ao enviar alerta ao Telegram. A próxima checagem tentará novamente se o alerta ainda estiver ativo.")
        return False
