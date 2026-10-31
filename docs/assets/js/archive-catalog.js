'use strict';
const input = document.querySelector('#article-search');
if (input) {
  const normalize = text => text.toLocaleLowerCase('pl').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
  const source = new Map((window.DRACOPEDIA_SEARCH_INDEX || []).map(record => [record.url, record.text]));
  const items = [...document.querySelectorAll('.article-list li')].map(item => {
    const link = item.querySelector('a');
    const text = source.get(link.getAttribute('href')) || '';
    const snippet = document.createElement('span');
    snippet.className = 'match-context';
    item.append(snippet);
    return {item, title:normalize(link.textContent), text, normalized:normalize(text), snippet};
  });

  // Reuse the search index; aliases must not bias the random selection.
  const params = new URLSearchParams(location.search);
  if (params.get('random') === '1') {
    const candidates = new Map();
    for (const record of items) {
      const link = record.item.querySelector('a');
      const title = link.textContent.replace(/^index\.php\//i, '').replace(/_/g, ' ').trim();
      const key = normalize(title);
      if (!record.text.trim() || title.includes(':') || key === 'strona glowna' ||
          /nie ma jeszcze artykułu o tym tytule/i.test(record.text)) continue;
      const existing = candidates.get(key);
      if (!existing || !/^index\.php\//i.test(link.textContent)) candidates.set(key, link.getAttribute('href'));
    }
    const urls = [...candidates.values()];
    if (urls.length) location.replace(new URL(urls[Math.floor(Math.random() * urls.length)], location.href).href);
  }

  const status = document.querySelector('#result-count');
  const empty = document.querySelector('#no-results');
  const update = () => {
    const words = normalize(input.value.trim()).split(/\s+/).filter(Boolean);
    let count = 0;
    for (const record of items) {
      const matches = words.every(word => record.title.includes(word) || record.normalized.includes(word));
      record.item.hidden = !matches;
      record.snippet.textContent = '';
      if (matches) {
        count++;
        if (words.length && !words.every(word => record.title.includes(word))) {
          const found = record.normalized.indexOf(words.find(word => record.normalized.includes(word)) || '');
          const start = Math.max(0, found - 50);
          record.snippet.textContent = (start ? '…' : '') + record.text.slice(start, start + 180) + (record.text.length > start + 180 ? '…' : '');
        }
      }
    }
    status.textContent = words.length ? `Wyniki wyszukiwania: ${count} z ${items.length}` : `Dostępne hasła: ${items.length}`;
    empty.hidden = count !== 0;
  };
  let timer;
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(update, 120); });
  input.addEventListener('keydown', event => { if (event.key === 'Escape') { clearTimeout(timer); input.value = ''; update(); } });
  input.value = params.get('search') || params.get('q') || '';
  update();
}
