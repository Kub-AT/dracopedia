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
  const params = new URLSearchParams(location.search);
  input.value = params.get('search') || params.get('q') || '';
  update();
}
