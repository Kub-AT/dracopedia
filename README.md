# Dracopedia Archive

A static preservation copy of **Dracopedia**, the former Polish community wiki about the browser strategy game **RedDragon**.

**[Browse the archive](https://kub-at.github.io/dracopedia/)** · **[Article catalog](https://kub-at.github.io/dracopedia/catalog.html)**

This project preserves historical game knowledge that was published at `dracopedia.pl`: races, buildings, magic, warfare, guides, community pages, and related material. It is an unofficial historical archive, maintained independently of the original wiki, the game's operators, and the Internet Archive.

## What is preserved

The initial recovery accepted **978 archived HTML pages**, alongside **6 recovered wiki stylesheets and 25 images**. These are recovery counts, not a guarantee of 978 distinct, complete articles: aliases, wiki stubs, and administrative or community pages are included. Some links lead to clearly marked missing-content notices.

Pages were recovered from different Wayback Machine capture dates. The result is a collection of historical material, not a consistent snapshot of the wiki on one date. Article text remains in Polish.

The archive includes local navigation between pages, recovered MediaWiki/Monobook presentation, a full-text searchable article catalog, random article navigation, and explanatory pages for content that could not be recovered. Newly written helper pages are explicitly marked **Kopia archiwalna · strona pomocnicza**.

## Browse locally

Open [`docs/index.html`](docs/index.html) directly in your browser, or optionally serve it:

```sh
python -m http.server 8000 --directory docs
```

Then visit `http://localhost:8000`. Browsing the copy does not require the original domain or a MediaWiki server.

## Repository layout

| Path | Purpose |
| --- | --- |
| `docs/index.html` | Archive entry point |
| `docs/pages/` | Recovered pages and missing-content notices |
| `docs/catalog.html` | Searchable catalog of recovered pages |
| `docs/assets/` | Recovered assets and new helper-page CSS/JavaScript |
| `docs/archive-manifest.json` | Page-level source URLs, requested captures, and recovery status |
| [ARCHIVE.md](ARCHIVE.md) | Sources, recovery process, modifications, and limitations |
| [RIGHTS.md](RIGHTS.md) | Attribution, copyright status, and rights inquiries |
| [LICENSE.md](LICENSE.md) | Licensing notice; archived material is not relicensed |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Reporting errors and contributing archival evidence |

The crawler, its response cache, local database, and machine logs are not included in this repository. No AI service or API is used when browsing the published archive.

## GitHub Pages

The site is published from **`main` → `/docs`** using GitHub Pages' **Deploy from a branch** setting. All internal paths are relative, including when served below `/dracopedia/`. No build step is required. Sidebar search forms pass their query to the catalog; its JavaScript searches a bundled index of recovered article titles and text, including when opened from disk. The index is about 2.1 MB and loads only on the catalog page. `.nojekyll` preserves the static file layout.

## Provenance and rights

The original wiki contributors and respective rights holders retain their rights in the archived text, images, branding, and other materials. Internet Archive provided access to historical captures; it is not the author or licensor of the original wiki content.

**No blanket permission to reuse the archived materials is granted by this repository.** A wiki's collaborative nature does not establish a free-content license. A general content license could not be verified in the recovered legal notice. See [RIGHTS.md](RIGHTS.md) before reusing material.

Preservation intent and attribution are not substitutes for permission. If you are a rights holder or can document the original license, please [open an issue](https://github.com/Kub-AT/dracopedia/issues/new). You can also use [GitHub's private copyright process](https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy).
