# Recovery tools

The archive can be browsed without running these tools. They are included to document and resume the recovery process.

## Requirements

- Python 3.11 or newer.
- Linux, macOS, or WSL: the crawler uses `fcntl` for its single-process lock.
- [uv](https://docs.astral.sh/uv/) for the simplest dependency setup.

The script declares its dependencies inline: `httpx`, `beautifulsoup4`, `lxml`, and `tinycss2`. No Wayback credentials or API keys are required. No language-model API is used.

## Download and resume

Run from the repository root:

```sh
uv run archive_dracopedia.py
```

This discovers pages, evaluates historical captures, downloads accepted HTML and assets, rewrites local paths, builds the helper interface and search index, and writes `output/dracopedia/report.json`.

The generated site is stored in `output/dracopedia/`. The response cache, queue, and original HTML are stored in its `.state/` directory. Both are ignored by Git. Rerunning the command resumes from local state; a fresh clone does not contain the maintainer's recovery database and starts a new recovery.

Ctrl+C stops downloading and builds the site from saved progress. Keep `.state/` to resume. Only one crawler can use a given output directory at a time.

A limited session:

```sh
uv run archive_dracopedia.py --max-seconds 600 --max-pages 20
```

An unattended session, independent of the terminal:

```sh
nohup uv run archive_dracopedia.py --max-seconds 28800 > archive-night.log 2>&1 < /dev/null &
```

The computer must stay awake and online. The time budget stops new network operations; final rendering may take additional time. `--max-pages` applies to the main crawl batch, with up to one additional page processed before CDX discovery.

| Option | Purpose |
| --- | --- |
| `--output PATH` | Output and state directory; default `output/dracopedia` |
| `--delay 1.5` | Minimum delay between top-level HTTP requests |
| `--timeout 35` | HTTP timeout in seconds |
| `--retries 4` | Maximum attempts per request |
| `--max-seconds N` | Network time budget; `0` means unlimited |
| `--max-pages N` | Main crawl batch limit; `0` means unlimited |
| `--build-only` | Render saved pages without new downloads |
| `--retry-missing` | Also retry pages whose available captures were rejected |

Network failures are automatically retried on the next run. A `missing` status differs from `retry`: the former means no candidate was accepted, while the latter records failed requests that may succeed later. Authenticity checks are heuristic and do not guarantee that every accepted page is a substantive article. See [ARCHIVE.md](ARCHIVE.md).

## Rebuild the interface

`special_pages.py` supplies the shared helper-page layout, repairs missing legacy Monobook imports when the recovered stylesheets are available, generates the text search index, and provides the browser-side search and random-page behavior. The crawler invokes it after rendering HTML.

To apply it separately to an existing generated site:

```sh
uv run --with beautifulsoup4 --with lxml python special_pages.py output/dracopedia
```

To rebuild saved crawler HTML and the report:

```sh
uv run archive_dracopedia.py --build-only
```

Rebuilding requires local state; this is not a command to reconstruct the published site from the Git repository alone. Some style and logo fallbacks refer to the specific assets recovered for this archive, and only apply when those assets exist.

## Review and publish a recovered update

Preview the generated result, inspect `report.json`, and review the changes before updating the published copy. Do not point a fresh crawl directly at `docs/`: failed downloads could replace published content with missing-page notices.

After review, copy the static files into the Pages directory:

```sh
cp output/dracopedia/index.html output/dracopedia/catalog.html docs/
cp -R output/dracopedia/pages output/dracopedia/assets docs/
touch docs/.nojekyll
```

The checked-in `docs/archive-manifest.json` documents the initial recovery. Update it from the new report when publishing a new recovery; copying the static files alone does not refresh provenance metadata. Keep `.state/`, local logs, and the raw failure report out of the published directory.

Commit the reviewed `docs/` changes. GitHub Pages continues to publish **`main` → `/docs`**; no separate crawler workflow is needed.

## Rights

The recovery scripts do not establish permission to redistribute archived third-party material. Existing copyright notices and any applicable terms must be respected. See [RIGHTS.md](RIGHTS.md) and [LICENSE.md](LICENSE.md).
