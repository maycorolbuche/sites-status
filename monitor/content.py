import hashlib
import json
import time
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

VOID = set("area base br col embed hr img input link meta param source track wbr".split())
HIDDEN = {"script", "style", "template", "noscript", "svg"}
HEADINGS = {f"h{level}" for level in range(1, 7)}
MAX_BYTES = 4 * 1024 * 1024


def normalize(text):
    return " ".join(text.split())


def matches(selector, tag, attrs):
    if selector.startswith("#"):
        return attrs.get("id") == selector[1:]
    if selector.startswith("."):
        return selector[1:] in (attrs.get("class") or "").split()
    return selector == tag


class Page(HTMLParser):
    def __init__(self, selector, ignore):
        super().__init__()
        self.selector = selector
        self.ignore = ignore
        self.stack = []
        self.title = []
        self.sections = {"body": [["Conteúdo", []]], "selected": [["Conteúdo", []]]}
        self.found = False
        self.has_body = False
        self.root_text = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        scope, hidden, heading = self.stack[-1][1:] if self.stack else (None, False, None)
        hidden = hidden or tag in HIDDEN or any(matches(rule, tag, attrs) for rule in self.ignore)
        if not hidden and matches(self.selector, tag, attrs):
            scope = "selected"
            self.found = True
        elif tag == "body":
            scope = "body"
            self.has_body = True
        if not hidden and scope:
            if tag in HEADINGS:
                heading = []
                self.sections[scope].append([heading, []])
            elif tag in {"a", "iframe", "form", "object", "embed", "img"}:
                attribute = {
                    "a": "href", "form": "action", "object": "data"
                }.get(tag, "src")
                target = normalize(attrs.get(attribute) or "")
                if target:
                    self.sections[scope][-1][1].append(f"[{tag}: {target}]")
        if tag not in VOID:
            self.stack.append((tag, scope, hidden, heading))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        tag, scope, hidden, heading = self.stack[-1] if self.stack else ("", None, False, None)
        if hidden:
            return
        if tag == "title":
            self.title.append(data)
        elif scope:
            section = self.sections[scope][-1]
            target = heading if heading is section[0] else section[1]
            target.append(data)
        elif not any(frame[0] == "head" for frame in self.stack):
            self.root_text.append(data)

    def fields(self):
        selected = self.sections["selected" if self.found else "body"]
        if not self.found and not self.has_body:
            selected = [["Conteúdo", self.root_text]]
        fields = {"Título": normalize("".join(self.title))}
        for label, parts in selected:
            label = normalize(" ".join(label)) if isinstance(label, list) else label
            label = label or "Seção sem título"
            unique = label
            suffix = 2
            while unique in fields:
                unique = f"{label} ({suffix})"
                suffix += 1
            fields[unique] = normalize(" ".join(parts))
        return fields


def fingerprint(html, site, final_url):
    page = Page(site.get("selector", "main"), site.get("ignore", []))
    page.feed(html)
    page.close()
    fields = page.fields()
    if "selector" in site and not page.found:
        fields["Área monitorada"] = f"Elemento ausente: {site['selector']}"
    if urlsplit(final_url).netloc != urlsplit(site["url"]).netloc:
        fields["Domínio após redirecionamento"] = urlsplit(final_url).netloc
    payload = json.dumps(list(fields.items()), ensure_ascii=False, separators=(",", ":"))
    digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
    sections = {
        name[:180]: {
            "hash": hashlib.sha256(value.encode()).hexdigest(),
            "excerpt": value[:240],
        }
        for name, value in list(fields.items())[:80]
    }
    return digest, sections


def check(site):
    started = time.monotonic()
    try:
        request = Request(site["url"], headers={
            "User-Agent": "SitesStatus/1.0",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        })
        with urlopen(request, timeout=15) as response:
            code = response.status
            elapsed = round((time.monotonic() - started) * 1000)
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                return {"status": "unverified", "ms": elapsed, "reason": "Resposta maior que 4 MiB"}
            html = body.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            digest, sections = fingerprint(html, site, response.geturl())
            return {"hash": digest, "sections": sections, "ms": elapsed, "http": code}
    except URLError as error:
        code = getattr(error, "code", None)
        reason = f"HTTP {code}" if code else "Falha de conexão, DNS ou TLS"
        return {"status": "down", "reason": reason}
    except (OSError, TimeoutError):
        return {"status": "down", "reason": "Falha de conexão ou tempo limite excedido"}
    except LookupError:
        return {"status": "unverified", "reason": "Codificação da resposta desconhecida"}
