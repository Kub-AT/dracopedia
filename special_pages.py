"""Style locally generated archive pages; recovered article HTML stays intact."""
from html import escape
from pathlib import Path
import json
import unicodedata

from bs4 import BeautifulSoup

CSS = '/* Helper controls only. Wiki layout and typography come from recovered Monobook. */\n:root { color-scheme:light; }\n.archive-helper .skip { position:absolute; top:4px; left:4px; padding:8px; background:white; transform:translateY(-200%); z-index:10; }\n.archive-helper .skip:focus { transform:none; }\n.archive-helper a:focus-visible,.archive-helper input:focus-visible { outline:2px solid #3366a3; outline-offset:2px; }\n.archive-helper #content { min-height:55vh; }\n.archive-helper #bodyContent { font-size:100%; }\n.archive-helper .eyebrow { color:#745015; font-size:85%; margin:.5em 0; }\n.archive-helper .notice { margin:1em 0; padding:.5em .8em; border:1px solid #ccb780; border-left:3px solid #9a6817; background:#fff8dc; }\n.archive-helper .notice p { margin:.3em 0; }\n.archive-helper .search { margin:1em 0; max-width:40em; }\n.archive-helper .search label { display:block; margin-bottom:.3em; font-weight:bold; }\n.archive-helper #article-search { box-sizing:border-box; width:100%; min-height:32px; padding:.35em .5em; border:1px solid #aaa; border-radius:0; background:white; color:black; font:inherit; }\n.archive-helper .help,.archive-helper .results { font-size:90%; color:#625b4d; margin:.4em 0; }\n.archive-helper .results { margin:1em 0 .5em; }\n.archive-helper .article-list { columns:3 18em; column-gap:2em; margin-top:.3em; }\n.archive-helper .article-list li { break-inside:avoid; overflow-wrap:anywhere; }\n.archive-helper .article-list a { padding:.1em 0; }\n.archive-helper .match-context { display:block; color:#625b4d; font-size:90%; line-height:1.5; margin:.2em 0 .7em; }\n.archive-helper .match-context:empty { display:none; }\n.archive-helper .empty { padding:1em; border:1px dashed #aaa; }\n.archive-helper .actions { display:flex; flex-wrap:wrap; gap:.7em; margin:1em 0; }\n.archive-helper .actions a { padding:.4em .7em; border:1px solid #aaa; background:#f2f5f8; }\n.archive-helper .actions .primary { font-weight:bold; }\n.archive-helper .details { max-width:70em; }\n.archive-helper [hidden] { display:none !important; }\n@media(max-width:600px) {\n .archive-helper #column-content { float:none; margin:0; }\n .archive-helper #content { margin:0; border:1px solid #aaa; padding:.6em .8em; }\n .archive-helper #column-one { padding:0; }\n .archive-helper #p-logo { position:relative; width:80px; height:80px; }\n .archive-helper #p-logo a { width:80px; height:80px; background-size:contain; }\n .archive-helper #p-navigation { position:absolute; top:8px; left:90px; width:calc(100% - 100px); }\n .archive-helper #p-navigation h5 { display:none; }\n .archive-helper #p-navigation ul { margin:.3em 0; }\n .archive-helper #p-cactions { position:relative; top:auto; left:auto; margin:1em 0 .5em; padding:0 .5em; width:auto; }\n .archive-helper #p-cactions ul { line-height:2em; }\n .archive-helper #footer { margin:1em 0; }\n .archive-helper #globalWrapper { display:flex; flex-direction:column; }\n .archive-helper #column-one { order:-1; }\n .archive-helper .article-list { columns:1; }\n}\n'

JS = "'use strict';\nconst input = document.querySelector('#article-search');\nif (input) {\n  const normalize = text => text.toLocaleLowerCase('pl').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/ł/g, 'l');\n  const source = new Map((window.DRACOPEDIA_SEARCH_INDEX || []).map(record => [record.url, record.text]));\n  const items = [...document.querySelectorAll('.article-list li')].map(item => {\n    const link = item.querySelector('a');\n    const text = source.get(link.getAttribute('href')) || '';\n    const snippet = document.createElement('span');\n    snippet.className = 'match-context';\n    item.append(snippet);\n    return {item, title:normalize(link.textContent), text, normalized:normalize(text), snippet};\n  });\n\n  // Reuse the search index; aliases must not bias the random selection.\n  const params = new URLSearchParams(location.search);\n  if (params.get('random') === '1') {\n    const candidates = new Map();\n    for (const record of items) {\n      const link = record.item.querySelector('a');\n      const title = link.textContent.replace(/^index\\.php\\//i, '').replace(/_/g, ' ').trim();\n      const key = normalize(title);\n      if (!record.text.trim() || title.includes(':') || key === 'strona glowna' ||\n          /nie ma jeszcze artykułu o tym tytule/i.test(record.text)) continue;\n      const existing = candidates.get(key);\n      if (!existing || !/^index\\.php\\//i.test(link.textContent)) candidates.set(key, link.getAttribute('href'));\n    }\n    const urls = [...candidates.values()];\n    if (urls.length) location.replace(new URL(urls[Math.floor(Math.random() * urls.length)], location.href).href);\n  }\n\n  const status = document.querySelector('#result-count');\n  const empty = document.querySelector('#no-results');\n  const update = () => {\n    const words = normalize(input.value.trim()).split(/\\s+/).filter(Boolean);\n    let count = 0;\n    for (const record of items) {\n      const matches = words.every(word => record.title.includes(word) || record.normalized.includes(word));\n      record.item.hidden = !matches;\n      record.snippet.textContent = '';\n      if (matches) {\n        count++;\n        if (words.length && !words.every(word => record.title.includes(word))) {\n          const found = record.normalized.indexOf(words.find(word => record.normalized.includes(word)) || '');\n          const start = Math.max(0, found - 50);\n          record.snippet.textContent = (start ? '…' : '') + record.text.slice(start, start + 180) + (record.text.length > start + 180 ? '…' : '');\n        }\n      }\n    }\n    status.textContent = words.length ? `Wyniki wyszukiwania: ${count} z ${items.length}` : `Dostępne hasła: ${items.length}`;\n    empty.hidden = count !== 0;\n  };\n  let timer;\n  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(update, 120); });\n  input.addEventListener('keydown', event => { if (event.key === 'Escape') { clearTimeout(timer); input.value = ''; update(); } });\n  input.value = params.get('search') || params.get('q') || '';\n  update();\n}\n"


def shell(title, content, prefix, catalog=False, logo=None):
    logo_style = f'background-image:url("{prefix}{escape(logo)}")' if logo else ''
    scripts = f'<script src="{prefix}assets/js/archive-search-index.js" defer></script><script src="{prefix}assets/js/archive-catalog.js" defer></script>' if catalog else ''
    return f'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} — Dracopedia · kopia archiwalna</title>
<link rel="stylesheet" href="{prefix}assets/css/660a05da2f82546c67c53b97.css" media="screen">
<link rel="stylesheet" href="{prefix}assets/css/3208557d4367920b100e321c.css" media="screen">
<link rel="stylesheet" href="{prefix}assets/css/bc4ec60cab5dfb567309a8e0.css" media="print">
<link rel="stylesheet" href="{prefix}assets/css/archive-pages.css">{scripts}
</head><body class="mediawiki ns-0 ltr archive-helper"><a class="skip" href="#bodyContent">Przejdź do treści</a>
<div id="globalWrapper"><div id="column-content"><main id="content">
<h1 class="firstHeading" id="firstHeading">{escape(title)}</h1><div id="bodyContent"><h3 id="siteSub">Z Dracopedia</h3>
<div id="contentSub">Kopia archiwalna · strona pomocnicza</div>{content}
</div></main></div>
<div id="column-one"><nav class="portlet" id="p-cactions" aria-label="Rodzaj strony"><ul>
<li><a href="{prefix}index.html">Wiki</a></li><li class="selected"><a href="{prefix}catalog.html" aria-current="page">{'Katalog archiwum' if catalog else 'Brak w archiwum'}</a></li>
</ul></nav>
<div class="portlet" id="p-logo"><a href="{prefix}index.html" style='{logo_style}' title="Dracopedia — strona główna" aria-label="Dracopedia — strona główna"></a></div>
<nav class="portlet" id="p-navigation" aria-label="Nawigacja Dracopedii"><h5>nawigacja</h5><div class="pBody"><ul>
<li><a href="{prefix}index.html">Strona główna</a></li><li><a href="{prefix}catalog.html">Katalog artykułów</a></li><li><a href="{prefix}catalog.html?random=1">Losuj stronę</a></li></ul></div></nav>
</div><div class="visualClear"></div><footer id="footer">Strona pomocnicza kopii archiwalnej. Jej układ i komunikaty dodano podczas odzyskiwania wiki. <a href="https://github.com/Kub-AT/dracopedia/blob/main/RIGHTS.md">Prawa autorskie i źródła</a>.</footer>
</div></body></html>'''


def repair_article_styles(root):
    """Use recovered Monobook CSS when an older capture lost inline imports."""
    main = 'assets/css/3208557d4367920b100e321c.css'
    shared = 'assets/css/660a05da2f82546c67c53b97.css'
    printing = 'assets/css/bc4ec60cab5dfb567309a8e0.css'
    if not (root / main).exists():
        return 0
    fixed = 0
    for page in (root / 'pages').glob('*.html'):
        raw = page.read_text(encoding='utf-8')
        if 'id="bodyContent"' not in raw or 'archive-pages.css' in raw:
            continue
        soup = BeautifulSoup(raw, 'lxml')
        if not soup.head:
            continue
        existing = [a.get('href', '') for a in soup.select('link[rel=stylesheet]')]
        if any(path.endswith(('3208557d4367920b100e321c.css', '0bbd3c433cd4bc8d62bbaab0.css')) for path in existing):
            continue
        for path, media in ((shared, 'screen'), (main, 'screen'), (printing, 'print')):
            if (root / path).exists():
                soup.head.append(soup.new_tag('link', rel='stylesheet', href='../' + path, media=media))
        logo = soup.select_one('#p-logo a')
        if logo and ('data:,' in logo.get('style', '') or not logo.get('style')):
            logo['style'] = 'background-image:url("../assets/images/3c3b513c3369266b6113bc5f.png")'
        page.write_text(str(soup), encoding='utf-8')
        fixed += 1
    return fixed


def style_special_pages(directory):
    root = Path(directory)
    repaired = repair_article_styles(root)
    catalog = root / 'catalog.html'
    if not catalog.is_file():
        return
    soup = BeautifulSoup(catalog.read_text(encoding='utf-8'), 'lxml')
    entries = [(a.get_text(' ', strip=True), a['href']) for a in soup.select('li a[href]') if a['href'].startswith('pages/')]
    entries.sort(key=lambda pair: unicodedata.normalize('NFD', pair[0].casefold()))
    logo_file = root / 'assets/images/3c3b513c3369266b6113bc5f.png'
    logo = str(logo_file.relative_to(root)) if logo_file.exists() else None
    css = root / 'assets/css/archive-pages.css'
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text(CSS, encoding='utf-8')
    js = root / 'assets/js/archive-catalog.js'
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(JS, encoding='utf-8')
    records = []
    for name, url in entries:
        from urllib.parse import unquote, urlsplit
        page = root / unquote(urlsplit(url).path)
        if not page.is_file():
            continue
        article = BeautifulSoup(page.read_text(encoding='utf-8'), 'lxml')
        body = article.select_one('#mw-content-text, #bodyContent, .mw-parser-output')
        if body:
            for unwanted in body.select('script, style, #catlinks, .printfooter'):
                unwanted.decompose()
        text = body.get_text(' ', strip=True) if body else ''
        records.append({'url': url, 'text': text})
    (root / 'assets/js/archive-search-index.js').write_text('window.DRACOPEDIA_SEARCH_INDEX = ' + json.dumps(records, ensure_ascii=False) + ';\n', encoding='utf-8')
    links = ''.join(f'<li><a href="{escape(url, quote=True)}">{escape(name)}</a></li>' for name, url in entries)
    content = f'''<div class="notice"><strong>Katalog odzyskanej wiki</strong><p>To pomocnicza lista haseł, a nie oryginalna strona specjalna MediaWiki. Edycja, logowanie i funkcje serwera wiki nie są dostępne w kopii.</p></div>
<div class="search"><label for="article-search">Znajdź artykuł</label><input id="article-search" type="search" placeholder="Np. rasy, magia, wojna…" aria-describedby="search-help" autocomplete="off">
<p id="search-help" class="help">Wyszukuje tytuły i treść odzyskanych artykułów. Możesz pominąć polskie znaki.</p></div>
<noscript><p>Bez JavaScript wyszukasz hasło przez Ctrl+F lub funkcję „Znajdź na stronie”.</p></noscript>
<p id="result-count" class="results" role="status" aria-live="polite">Liczba haseł: {len(entries)}</p>
<p id="no-results" class="empty" hidden>Nie znaleziono pasujących haseł. Spróbuj krótszej nazwy.</p>
<ul class="article-list">{links}</ul>'''
    catalog.write_text(shell('Katalog artykułów', content, '', catalog=True, logo=logo), encoding='utf-8')
    count = 0
    for page in (root / 'pages').glob('*.html'):
        raw = page.read_text(encoding='utf-8')
        if 'Nie odzyskano tego artykułu z archiwum.' not in raw:
            continue
        soup = BeautifulSoup(raw, 'lxml')
        heading = soup.find('h1')
        title = heading.get_text() if heading else page.stem
        content = '''<div class="notice"><strong>Brak odzyskanej treści</strong><p>Nie odzyskano tego artykułu z archiwum.</p></div>
<p>Odnośnik prowadził do tego hasła w dawnej Dracopedii, ale w obecnej kopii nie ma jego treści. Nie została ona odtworzona ani uzupełniona.</p>
<div class="actions"><a class="primary" href="../catalog.html">Przeglądaj odzyskane artykuły</a><a href="../index.html">Strona główna</a></div>
<section class="details"><h2>Co oznacza ten komunikat?</h2><p>Strona mogła nie zostać zarchiwizowana, pobieranie mogło się nie udać lub dostępne wersje nie przeszły weryfikacji. Ten komunikat nie przesądza, czy hasło da się jeszcze odzyskać.</p></section>'''
        page.write_text(shell(title.replace('_', ' '), content, '../', logo=logo), encoding='utf-8')
        count += 1
    return {'catalog_entries': len(entries), 'missing_pages_styled': count, 'article_styles_repaired': repaired}


if __name__ == '__main__':
    import sys
    print(style_special_pages(sys.argv[1] if len(sys.argv) > 1 else 'docs'))
