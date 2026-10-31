#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27,<1", "beautifulsoup4>=4.12,<5", "lxml>=5,<7", "tinycss2>=1.3,<2"]
# ///
"""One-shot, resumable Wayback mirror. Run: uv run archive_dracopedia.py."""
from __future__ import annotations

import argparse
import hashlib
import fcntl
import html
import json
import logging
import posixpath
import random
import re
import sqlite3
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlsplit

import httpx
import tinycss2
from bs4 import BeautifulSoup

LOG = logging.getLogger("dracopedia")
HOME = "Strona_główna"
STAMP = "20120923042055"
ORIGIN = "http://dracopedia.pl/"
ARCHIVE = "https://web.archive.org"
HOSTS = {"dracopedia.pl", "www.dracopedia.pl"}
STATIC = re.compile(r"\.(?:css|js|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|eot|pdf|ogg|mp3)(?:$|\?)", re.I)


def unwrap(url):
    url = html.unescape(url)
    if url.startswith("//"):
        url = "https:" + url
    m = re.search(r"(?:https?://web\.archive\.org)?/web/(?:\d{1,14}|\*)(?:[a-z_]+)?/(https?://.*)", url)
    return m.group(1) if m else url


def absolute(url, base=ORIGIN):
    return unwrap(urljoin(base, unwrap(url)))


def title_of(url):
    p = urlsplit(unwrap(url))
    if p.hostname not in HOSTS:
        return None
    q = parse_qs(p.query)
    if q.get("action", ["view"])[0] not in ("view", "render") or any(k in q for k in ("diff", "oldid", "printable")):
        return None
    path = unquote(p.path)
    if STATIC.search(path) or path.startswith(("/skins/", "/images/", "/resources/")):
        return None
    if path.rstrip("/").endswith("index.php"):
        title = q.get("title", [HOME])[0]
    elif path in ("/", ""):
        title = HOME
    else:
        title = path.removeprefix("/wiki/").lstrip("/")
    title = unicodedata.normalize("NFC", title.replace("_", " ").strip()).replace(" ", "_")
    if title.lower().startswith(("special:", "specjalna:")) or not title or "\x00" in title:
        return None
    return title


def page_url(title):
    return ORIGIN + quote(title, safe="/:_")


def filename(title):
    safe = re.sub(r'[^\w.() -]', "_", title, flags=re.U).strip(". ")[:100] or "article"
    safe = safe.encode("utf-8")[:180].decode("utf-8", errors="ignore")
    return f"pages/{safe}-{hashlib.sha256(title.encode()).hexdigest()[:12]}.html"


def authenticity(body):
    soup = BeautifulSoup(body, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True).lower()
    negative = [s for s in ("domain for sale", "buy this domain", "domena na sprzedaż", "sedo", "afternic", "verify you are human", "wayback machine has not archived", "robot check", "captcha", "casino", "payday loan") if s in text]
    structure = sum(bool(soup.select_one(s)) for s in ("#mw-content-text", "#content", "#bodyContent", "#p-logo", "#p-navigation", "#column-one", ".mw-parser-output", "#catlinks"))
    generator = bool(soup.find("meta", attrs={"name": re.compile("generator", re.I), "content": re.compile("mediawiki", re.I)}))
    brand = sum(s in text for s in ("dracopedia", "reddragon", "red dragon", "z dracopedia"))
    topics = sum(s in text for s in ("rasy", "budynki", "wojsko", "magia", "księstw", "koalicj"))
    content = soup.select_one("#mw-content-text, #bodyContent, .mw-parser-output, #content")
    size = len(content.get_text(" ", strip=True)) if content else len(text)
    score = structure * 3 + generator * 5 + brand * 3 + min(topics, 3) - len(negative) * 15
    valid = score >= 10 and size >= 60 and (structure >= 2 or (generator and brand) or (brand >= 2 and topics >= 2))
    return valid, score + min(size // 500, 10), {"structure": structure, "brand": brand, "negative": negative, "text_length": size}


class Mirror:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.output)
        self.out.mkdir(parents=True, exist_ok=True)
        self.state = self.out / ".state"
        self.state.mkdir(exist_ok=True)
        self.lock = (self.state / "run.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Crawler już działa dla tego katalogu wyjściowego.")
        self.db = sqlite3.connect(self.state / "progress.sqlite")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS pages(title TEXT PRIMARY KEY, status TEXT DEFAULT 'pending', snapshot TEXT, raw BLOB, evidence TEXT);
        CREATE TABLE IF NOT EXISTS captures(title TEXT, url TEXT, stamp TEXT, mime TEXT, digest TEXT, PRIMARY KEY(title,url,stamp));
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS assets(url TEXT PRIMARY KEY,path TEXT,stamp TEXT,status TEXT);
        CREATE TABLE IF NOT EXISTS failures(url TEXT PRIMARY KEY,error TEXT);
        """)
        self.client = httpx.Client(timeout=args.timeout, follow_redirects=True, headers={"User-Agent": "DracopediaRecovery/1.0 (personal historical preservation)"})
        self.last_request = 0.0
        self.deadline = time.monotonic() + args.max_seconds if args.max_seconds else float("inf")
        self.asset_active = set()
        self.asset_failed = set()
        self.add(HOME)
        self.db.execute("INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?)", (HOME, page_url(HOME), STAMP, "text/html", "seed"))
        self.db.commit()

    def add(self, title):
        if title:
            self.db.execute("INSERT OR IGNORE INTO pages(title) VALUES(?)", (title,))

    def get(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        cache = self.state / key
        meta = self.state / (key + ".json")
        if cache.exists() and meta.exists():
            return cache.read_bytes(), json.loads(meta.read_text())["type"]
        for attempt in range(self.args.retries):
            if time.monotonic() > self.deadline:
                raise TimeoutError("Osiągnięto limit czasu sesji")
            time.sleep(max(0, self.args.delay - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                r = self.client.get(url)
                if urlsplit(str(r.url)).hostname not in {"web.archive.org", "archive.org"}:
                    raise ValueError("Przekierowanie poza archiwum: " + str(r.url))
                r.raise_for_status()
                if "/web/" in url and title_of(unwrap(url)) and title_of(unwrap(str(r.url))) != title_of(unwrap(url)):
                    raise ValueError("Snapshot przekierował do innego artykułu: " + str(r.url))
                body, kind = r.content, r.headers.get("content-type", "").split(";")[0].lower()
                temporary = cache.with_suffix(".tmp")
                temporary.write_bytes(body)
                temporary.replace(cache)
                meta.write_text(json.dumps({"type": kind}), encoding="utf-8")
                self.db.execute("DELETE FROM failures WHERE url=?", (url,))
                self.db.commit()
                return body, kind
            except httpx.HTTPError as e:
                LOG.warning("Żądanie %s: %s", url, e)
                self.db.execute("INSERT OR REPLACE INTO failures VALUES(?,?)", (url, str(e)))
                self.db.commit()
                retryable = not isinstance(e, httpx.HTTPStatusError) or e.response.status_code in (429, 500, 502, 503, 504)
                archived_error = isinstance(e, httpx.HTTPStatusError) and bool(e.response.headers.get("memento-datetime"))
                if archived_error or not retryable or attempt + 1 == self.args.retries:
                    raise
                retry_after = e.response.headers.get("retry-after", "0") if isinstance(e, httpx.HTTPStatusError) else "0"
                pause = max(float(retry_after) if retry_after.isdigit() else 0, 2 ** (attempt + 1) + random.random())
                time.sleep(min(pause, 60))
        raise RuntimeError(url)

    def cdx(self, url, **extra):
        params = {"url": url, "output": "json", "fl": "timestamp,original,mimetype,statuscode,digest", "filter": "statuscode:200", **extra}
        return self.get(ARCHIVE + "/cdx/search/cdx?" + urlencode(params))[0].decode("utf-8")

    def discover(self):
        if self.db.execute("SELECT value FROM meta WHERE key='cdx_done'").fetchone():
            return
        sources = [("domain", "dracopedia.pl", {"matchType": "domain"}),
                   ("plain", "dracopedia.pl/*", {}),
                   ("www", "www.dracopedia.pl/*", {})]
        completed = set()
        for name, pattern, extra in sources:
            if self.db.execute("SELECT 1 FROM meta WHERE key=?", (name + '_done',)).fetchone():
                completed.add(name)
                continue
            row = self.db.execute("SELECT value FROM meta WHERE key=?", (name + '_cursor',)).fetchone()
            cursor = row[0] if row else ""
            try:
                while True:
                    text = self.cdx(pattern, collapse="urlkey", limit=1000, showResumeKey="true", **extra, **({"resumeKey": cursor} if cursor else {}))
                    rows, end = json.JSONDecoder().raw_decode(text.lstrip())
                    rest = text.lstrip()[end:].strip()
                    for stamp, url, mime, status, digest in rows[1:]:
                        title = title_of(url)
                        if title and mime in ("text/html", "application/xhtml+xml", "warc/revisit"):
                            self.add(title)
                            self.db.execute("INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?)", (title, url, stamp, mime, digest))
                    if not rest:
                        self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,'1')", (name + '_done',))
                        completed.add(name)
                    else:
                        cursor = rest.splitlines()[-1].strip()
                        self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (name + '_cursor', cursor))
                    self.db.commit()
                    LOG.info("CDX %s: %s stron", name, self.db.execute("SELECT count(*) FROM pages").fetchone()[0])
                    if not rest:
                        break
            except (httpx.HTTPError, ValueError, TimeoutError) as e:
                LOG.warning("Indeks %s niedostępny, próbuję następnego wariantu: %s", name, e)
            if 'domain' in completed or {'plain', 'www'} <= completed:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES('cdx_done','1')")
                self.db.commit()
                return

    def candidates(self, title, asset=False):
        urls = [title] if asset else [page_url(title), ORIGIN + "index.php?" + urlencode({"title": title})]
        urls += [u.replace("://dracopedia.pl", "://www.dracopedia.pl") for u in list(urls) if "://dracopedia.pl" in u]
        found = [] if asset else [r for r in self.db.execute("SELECT stamp,url,digest FROM captures WHERE title=?", (title,)) if title_of(r[1]) == title]
        for url in urls:
            # Match all schemes and www by URL pattern, keep distinct digests across all years.
            p = urlsplit(url)
            pattern = p.netloc + p.path + ("?" + p.query if p.query else "")
            try:
                rows = []
                cursor = ""
                while True:
                    text = self.cdx(pattern, collapse="digest", limit=1000, showResumeKey="true", **({"resumeKey": cursor} if cursor else {}))
                    batch, end = json.JSONDecoder().raw_decode(text.lstrip())
                    rows.extend(batch[1:])
                    rest = text.lstrip()[end:].strip()
                    if not rest:
                        break
                    cursor = rest.splitlines()[-1].strip()
                for stamp, original, mime, status, digest in rows:
                    if not asset and title_of(original) != title:
                        continue
                    if asset and unquote(urlsplit(original).path) != unquote(urlsplit(url).path):
                        continue
                    found.append((stamp, original, digest))
                    if not asset:
                        self.db.execute("INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?)", (title, original, stamp, mime, digest))
                self.db.commit()
            except (httpx.HTTPError, ValueError, TimeoutError) as e:
                LOG.warning("Brak metadanych dla %s: %s", url, e)
        # Anchor year first, then spread dates; do not assume newest is genuine.
        found.sort(key=lambda r: (abs(int(r[0][:4]) - 2012), abs(int(r[0]) - int(STAMP))))
        seen = set()
        result = []
        for stamp, url, digest in found:
            if digest not in seen or digest == "-":
                seen.add(digest)
                result.append((stamp, url))
        if not result:
            result = [(STAMP, urls[0])]
        return result

    def crawl(self):
        count = 0
        while time.monotonic() < self.deadline:
            row = self.db.execute("SELECT title FROM pages WHERE status='pending' ORDER BY title<>?,rowid LIMIT 1", (HOME,)).fetchone()
            if not row or (self.args.max_pages and count >= self.args.max_pages):
                break
            title = row[0]
            best = None
            errors = False
            for stamp, url in self.candidates(title):
                try:
                    body, mime = self.get(f"{ARCHIVE}/web/{stamp}id_/{url}")
                    valid, score, evidence = authenticity(body)
                    if valid and (best is None or score > best[0]):
                        best = (score, body, stamp, url, evidence)
                    if valid and score >= 25:
                        break
                except (httpx.HTTPError, TimeoutError, ValueError) as e:
                    errors = True
                    LOG.warning("Snapshot %s %s: %s", stamp, title, e)
                if time.monotonic() > self.deadline:
                    break
            if best:
                _, body, stamp, url, evidence = best
                self.db.execute("UPDATE pages SET status='ok',snapshot=?,raw=?,evidence=? WHERE title=?", (stamp + "/" + url, body, json.dumps(evidence), title))
                soup = BeautifulSoup(body, "lxml")
                for a in soup.select("a[href]"):
                    self.add(title_of(absolute(a["href"], url)))
                LOG.info("Odzyskano: %s", title)
            else:
                self.db.execute("UPDATE pages SET status=? WHERE title=?", ("retry" if errors else "missing", title))
                LOG.warning("Nie odzyskano: %s", title)
            self.db.commit()
            count += 1
            if count % 25 == 0:
                self.build()

    def css(self, text, base, local):
        # Parse CSS tokens, including quoted @import and nested url() functions.
        tokens = tinycss2.parse_stylesheet(text, skip_comments=False, skip_whitespace=False)
        def rewrite(value):
            target = absolute(value, base)
            if value.startswith(("data:", "#")):
                return value
            path = self.asset(target)
            return posixpath.relpath(path, posixpath.dirname(local)) if path else "data:,"
        def walk(items):
            items[:] = [t for t in items if t.type != "error"]
            for token in items:
                if token.type == "url":
                    token.value = rewrite(token.value)
                    token.representation = 'url("' + token.value + '")'
                elif token.type == "function" and token.lower_name == "url":
                    value = tinycss2.serialize(token.arguments).strip().strip("\"'")
                    token.arguments = tinycss2.parse_component_value_list('"' + rewrite(value) + '"')
                elif token.type == "at-rule" and token.lower_at_keyword == "import":
                    for child in token.prelude:
                        if child.type == "string":
                            child.value = rewrite(child.value)
                            child.representation = '"' + child.value + '"'
                            break
                for attr in ("content", "arguments", "prelude"):
                    children = getattr(token, attr, None)
                    if children:
                        walk(children)
        walk(tokens)
        return tinycss2.serialize(tokens)

    def asset(self, url):
        url = unwrap(url).split("#")[0]
        if url in self.asset_failed:
            return None
        if urlsplit(url).hostname not in HOSTS:
            return None
        row = self.db.execute("SELECT path,status FROM assets WHERE url=?", (url,)).fetchone()
        if row and row[1] == "ok" and (self.out / row[0]).exists():
            return row[0]
        if url in self.asset_active or time.monotonic() > self.deadline:
            return row[0] if row else None
        self.asset_active.add(url)
        try:
            def options():
                yield STAMP, url
                yield from self.candidates(url, asset=True)
            for stamp, original in options():
                if time.monotonic() > self.deadline:
                    break
                try:
                    body, mime = self.get(f"{ARCHIVE}/web/{stamp}id_/{original}")
                    kind = None
                    ext = ".bin"
                    signatures = [(b'\x89PNG\r\n\x1a\n', '.png'), (b'\xff\xd8\xff', '.jpg'), (b'GIF8', '.gif'), (b'wOFF', '.woff'), (b'wOF2', '.woff2'), (b'\x00\x01\x00\x00', '.ttf'), (b'\x00\x00\x01\x00', '.ico')]
                    for magic, suffix in signatures:
                        if body.startswith(magic):
                            ext, kind = suffix, "fonts" if suffix in (".woff", ".woff2", ".ttf") else "images"
                            break
                    if body.startswith(b'RIFF') and body[8:12] == b'WEBP':
                        ext, kind = '.webp', 'images'
                    if b'<svg' in body[:1000] and b'<html' not in body[:1000].lower():
                        ext, kind = '.svg', 'images'
                    if mime == 'text/css' and b'<html' not in body[:1000].lower() and (b'{' in body or b'@import' in body):
                        ext, kind = '.css', 'css'
                    if not kind:
                        continue
                    path = f"assets/{kind}/{hashlib.sha256(url.encode()).hexdigest()[:24]}{ext}"
                    self.db.execute("INSERT OR REPLACE INTO assets VALUES(?,?,?,?)", (url, path, stamp, "pending"))
                    self.db.commit()
                    if kind == 'css':
                        body = self.css(body.decode('utf-8-sig', errors='replace'), original, path).encode()
                    target = self.out / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(body)
                    self.db.execute("UPDATE assets SET status='ok' WHERE url=?", (url,))
                    self.db.commit()
                    return path
                except (httpx.HTTPError, TimeoutError, ValueError) as e:
                    LOG.warning("Zasób %s: %s", url, e)
            self.asset_failed.add(url)
            self.db.execute("INSERT OR REPLACE INTO assets VALUES(?,NULL,NULL,'missing')", (url,))
            self.db.commit()
        finally:
            self.asset_active.discard(url)
        return None

    def build(self):
        rows = list(self.db.execute("SELECT title,status,snapshot,raw FROM pages"))
        mapping = {r[0]: filename(r[0]) for r in rows}
        (self.out / 'pages').mkdir(exist_ok=True)
        for title, status, snapshot, raw in rows:
            path = mapping[title]
            if status != 'ok':
                content = f'<!doctype html><meta charset="utf-8"><h1>{html.escape(title)}</h1><p>Nie odzyskano tego artykułu z archiwum.</p><a href="../index.html">Strona główna</a>'
            else:
                base = snapshot.split('/', 1)[1]
                soup = BeautifulSoup(raw, 'lxml')
                for tag in soup.select('script, base, #wm-ipp-base, #wm-ipp, .wb-autocomplete-suggestions, iframe, object, embed'):
                    tag.decompose()
                for tag in soup.find_all(True):
                    for attr in list(tag.attrs):
                        if attr.startswith('on') or attr in ('integrity', 'crossorigin', 'srcset', 'ping'):
                            del tag[attr]
                for tag in soup.select('meta[http-equiv]'):
                    if tag.get('http-equiv', '').lower() in ('refresh', 'content-security-policy', 'content-type'):
                        tag.decompose()
                if soup.head:
                    for meta in soup.select('meta[charset]'):
                        meta.decompose()
                    soup.head.insert(0, soup.new_tag('meta', charset='utf-8'))
                for a in soup.select('a[href], area[href]'):
                    href = a['href']
                    if href.startswith('#'):
                        continue
                    url = absolute(href, base)
                    target = title_of(url)
                    if target in mapping:
                        fragment = urlsplit(url).fragment
                        a['href'] = quote(posixpath.relpath(mapping[target], 'pages'), safe='/') + ('#' + fragment if fragment else '')
                    elif urlsplit(url).hostname in HOSTS:
                        a['href'] = '../catalog.html'
                    elif urlsplit(url).scheme in ('http', 'https', 'mailto'):
                        a['href'] = url
                    else:
                        a.attrs.pop('href', None)
                for tag in soup.select('img[src], input[src], link[href], [background]'):
                    attr = 'src' if tag.has_attr('src') else 'background' if tag.has_attr('background') else 'href'
                    if tag.name == 'link' and not set(tag.get('rel', [])).intersection({'stylesheet', 'icon', 'shortcut'}):
                        tag.decompose()
                        continue
                    asset = self.asset(absolute(tag[attr], base))
                    if asset:
                        tag[attr] = '../' + asset
                    else:
                        tag.attrs.pop(attr, None)
                        if tag.name == 'link':
                            tag.decompose()
                for style in soup.select('style'):
                    style.string = self.css(style.get_text(), base, path)
                for tag in soup.select('[style]'):
                    tag['style'] = self.css('x{' + tag['style'] + '}', base, path)[2:-1]
                for random_link in soup.select('#n-randompage a'):
                    random_link['href'] = '../catalog.html?random=1'
                for form in soup.select('form'):
                    form['action'] = '../catalog.html'
                    form['method'] = 'get'
                content = str(soup)
            (self.out / path).write_text(content, encoding='utf-8')
        links = ''.join(f'<li><a href="{quote(mapping[t])}">{html.escape(t.replace("_", " "))}</a></li>' for t, s, _, _ in rows if s == 'ok')
        (self.out / 'catalog.html').write_text('<!doctype html><meta charset="utf-8"><title>Katalog Dracopedii</title><h1>Odzyskane artykuły</h1><p>Wyszukaj hasło przez Ctrl+F.</p><ul>' + links + '</ul>', encoding='utf-8')
        (self.out / 'index.html').write_text(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={quote(mapping[HOME])}"><a href="{quote(mapping[HOME])}">Dracopedia — strona główna</a>', encoding='utf-8')
        from special_pages import style_special_pages
        style_special_pages(self.out)
        self.verify()

    def verify(self):
        broken, archive = [], []
        for file in self.out.rglob('*.html'):
            soup = BeautifulSoup(file.read_text(encoding='utf-8'), 'lxml')
            for tag in soup.select('[href], [src], [background]'):
                for attr in ('href', 'src', 'background'):
                    value = tag.get(attr)
                    if not value:
                        continue
                    p = urlsplit(value)
                    if p.hostname == 'web.archive.org':
                        archive.append({'file': str(file.relative_to(self.out)), 'url': value})
                    if not p.scheme and not p.netloc and p.path:
                        target = (file.parent / unquote(p.path)).resolve()
                        if not target.is_file():
                            broken.append({'file': str(file.relative_to(self.out)), 'url': value})
        def check_css(tokens, file):
            for token in tokens:
                value = None
                if token.type == 'url':
                    value = token.value
                elif token.type == 'function' and token.lower_name == 'url':
                    value = tinycss2.serialize(token.arguments).strip().strip("\"'")
                if value:
                    parsed = urlsplit(value)
                    if not parsed.scheme and not parsed.netloc and parsed.path and not (file.parent / unquote(parsed.path)).is_file():
                        broken.append({'file': str(file.relative_to(self.out)), 'url': value})
                for attr in ('content', 'arguments', 'prelude'):
                    children = getattr(token, attr, None)
                    if children:
                        check_css(children, file)
        for file in self.out.rglob('*.css'):
            check_css(tinycss2.parse_stylesheet(file.read_text(encoding='utf-8')), file)
        counts = dict(self.db.execute('SELECT status,count(*) FROM pages GROUP BY status'))
        assets = dict(self.db.execute('SELECT status,count(*) FROM assets GROUP BY status'))
        report = {'index_exists': (self.out / 'index.html').exists(), 'css_files': len(list((self.out / 'assets/css').glob('*.css'))), 'image_files': len(list((self.out / 'assets/images').glob('*'))), 'articles': counts.get('ok', 0), 'missing_pages': counts.get('missing', 0), 'pending_pages': counts.get('pending', 0), 'retry_pages': counts.get('retry', 0), 'assets': assets.get('ok', 0), 'missing_assets': assets.get('missing', 0), 'broken_links_count': len(broken), 'broken_links': broken, 'wayback_links': archive, 'cdx_complete': bool(self.db.execute("SELECT 1 FROM meta WHERE key='cdx_done'").fetchone()), 'failures': list(self.db.execute('SELECT url,error FROM failures')), 'pages': [{'title': t, 'status': s, 'snapshot': snap} for t, s, snap in self.db.execute('SELECT title,status,snapshot FROM pages')]}
        (self.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        LOG.info('Wynik: %s artykułów, %s zasobów, %s uszkodzonych linków', report['articles'], report['assets'], len(broken))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='output/dracopedia')
    p.add_argument('--delay', type=float, default=1.5)
    p.add_argument('--timeout', type=float, default=35)
    p.add_argument('--retries', type=int, default=4)
    p.add_argument('--max-pages', type=int, default=0, help='Limit na sesję; 0 = bez limitu')
    p.add_argument('--max-seconds', type=int, default=0, help='Budżet sieci na sesję; 0 = bez limitu')
    p.add_argument('--build-only', action='store_true')
    p.add_argument('--retry-missing', action='store_true')
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    mirror = Mirror(args)
    if args.build_only:
        mirror.deadline = 0
    try:
        if not args.build_only:
            mirror.db.execute("UPDATE pages SET status='pending' WHERE status='retry'")
            if args.retry_missing:
                mirror.db.execute("UPDATE pages SET status='pending' WHERE status='missing'")
            mirror.db.commit()
            # Recover the seed before a possibly expensive domain-wide inventory.
            original_limit = args.max_pages
            args.max_pages = 1
            mirror.crawl()
            args.max_pages = original_limit
            try:
                mirror.discover()
            except (httpx.HTTPError, ValueError, TimeoutError) as e:
                LOG.error('CDX niedostępne; kontynuuję z kolejki: %s', e)
            mirror.crawl()
    except KeyboardInterrupt:
        LOG.warning('Przerwano; buduję wynik z dotychczasowego postępu')
        mirror.deadline = 0  # No new network requests while finalizing after Ctrl+C.
    finally:
        try:
            mirror.build()
        finally:
            mirror.client.close()
            mirror.db.close()


if __name__ == '__main__':
    main()
