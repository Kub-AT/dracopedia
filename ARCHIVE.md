# Archive provenance and recovery notes

## Historical source

- Original site: `http://dracopedia.pl/`, including HTTPS and `www` variants.
- Subject: Dracopedia, the Polish-only community wiki for **RedDragon.pl** (also known as **RD** or **RD.pl**).
- Scope: the Polish edition; the Czech and Hungarian editions of RedDragon are outside this archive’s coverage.
- Recovery starting point: [Wayback capture of the main page, 23 September 2012](https://web.archive.org/web/20120923042055/http://dracopedia.pl/Strona_g%C5%82%C3%B3wna).
- Recovery performed: 30–31 October 2026.
- Historical captures supplied by the Internet Archive's Wayback Machine.

`docs/archive-manifest.json` records the source URL, requested capture timestamp, local path, and recovery status for discovered pages. Wayback may redirect a requested timestamp to a nearby capture, so a requested timestamp is not proof of the exact date of the returned response.

## Recovery method

The recovery combined recursive traversal of wiki links with Wayback CDX metadata. Candidate HTML was evaluated using several signals, including MediaWiki structure, Dracopedia/RedDragon references, and signs of unrelated domain parking or archive errors. Captures from different years were allowed.

The domain-wide CDX discovery did not complete successfully. Some discovered pages remain unavailable after network failures. The archive therefore makes no claim to completeness. Counts describe files accepted during recovery and can include duplicate titles, legacy `index.php` aliases, or historical wiki pages that were already empty.

## Changes made for static browsing

- Internal page and asset references were rewritten to relative local paths.
- Wayback toolbar elements, JavaScript, event handlers, and embedded frames were removed.
- Server-dependent actions such as login, editing, and special-page queries lead to a local catalog.
- Unrecovered pages receive an explicit notice rather than invented article text.
- Assets may come from different years than their articles.
- Older pages with missing CSS imports use recovered Monobook stylesheets from another capture.
- The local catalog, its full-text search script and static text index, and missing-page presentation are new helper UI, not historical MediaWiki pages.

Some external resources and images are missing. Historical counters, revision dates, and factual claims are preserved as historical material and should not be interpreted as current information. Local navigation checks validate file destinations, not historical accuracy or section-anchor completeness.

## Credits

- Dracopedia contributors, editors, administrators, and asset creators: the original wiki and its community knowledge.
- RedDragon and respective rights holders: the game, names, and associated materials.
- Internet Archive: preservation infrastructure and access to historical captures.
- MediaWiki/Monobook authors: the original presentation; recovered stylesheet notices are retained, including the credits to Gabriel Wicke and Alexander Limi where present.
- [GeiserX/Wayback-Archive](https://github.com/GeiserX/Wayback-Archive): its downloader implementation and documentation were consulted when reviewing recovery behavior. Its code is not bundled or imported here.

The archive maintainer does not claim authorship of the recovered wiki content. See [RIGHTS.md](RIGHTS.md).
