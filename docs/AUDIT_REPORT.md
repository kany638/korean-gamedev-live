# V3 audit and validation — 2026-10-08

## Conclusion

Company career sites are explicitly part of the implemented run path, not just prose in a company wish-list. The register contains 31 official career routes, 3 official programme pages and 9 job-board entries. Some routes share a group portal and some are corporate landing-page discovery attempts. The register is neither exhaustive nor proof that all collectors work live.

## Executed tests

- Baseline v2 suite: 116 passed before changes.
- V3 pytest suite: 184 passed (existing experience/calendar/state checks plus 68 new official-source/registry/adapter/navigation/API tests). Exact run output is in `v3_pytest_results.txt` and XML.
- Offline Chromium dashboard checks: 7 passed, using `set_content` and mocked JSON fetch. Exact checks in `v3_browser_results.json`; screenshot in `v3_dashboard_initial.png`.
- Python compilation, shell script syntax and dashboard JavaScript syntax checks performed.
- All five generated feed structures validated; shipped initial feeds deliberately contain zero jobs and health=`not_deployed`.
- The distributable ZIP is extracted to another directory and its Python tests/feed checks rerun before delivery. See `v3_release_validation.txt`.

These are authored fixtures, not official recruitment tests. They do not demonstrate access to the user's GitHub account, real Apple Calendar refresh, every live ATS response or hidden job postings.

## Network and browser limitations actually encountered

Direct requests from the build environment to Pearl Abyss, Com2uS and Greenhouse failed (recorded in `v3_network_probe.json`). External browser navigation was blocked by managed environment policy. Those restrictions were not bypassed. Dashboard QA used a purely local DOM and mocked data; it is not a successful live public-page renderer test.

Public-web research could inspect or follow several official entry points separately, sometimes from cached web results. This is evidence for registry provenance, not proof that the Python/Playwright collector succeeds from GitHub today. Some official sites exposed only a JavaScript shell or returned access errors in research. No real current vacancy has been seeded into the shipped calendar.

## Implemented changes

- Official career sources have explicit mode, domains, priorities, reference URLs, route status, target labels and separate health reporting.
- Company roots are prioritised ahead of job boards; second-page/navigation/render attempts happen after root attempts. Rotation limits starvation within a priority tier.
- Preserved company/job query identifiers rather than dropping `corpCodes=AG` and similar parameters; filters no longer silently switch the source to a generic group list.
- Added explicit employer-linked ATS navigation, embedded JSON lead discovery and nearby-heading extraction for APPLY links. An artist APPLY link cannot reuse a programmer heading from the neighbouring card.
- Corrected Com2uS's current official redirect route and NHN's plural careers hostname; used separate Nexon Games/Neople/Mintrocket routes instead of assuming a group homepage proves full subsidiary coverage.
- Documented Greenhouse public API for 5minlab. Individual candidate details checked; updated_at never becomes a deadline.
- Optional bounded public HTML rendering through robots-aware, domain-restricted GET requests; no login/proxy/CAPTCHA/403 bypass. Missing installation and rendering limits remain visible.
- Evergreen programme material does not create a fabricated 2027 intake. A dated programme root needs an actual parseable non-expired application deadline before publication.
- Persisted source last-success times and a bounded deferred-detail backlog. Existing records retain source/URL identity, first-seen time and deadline revision behaviour.
- Expanded rotating optional Naver company-domain discovery without changing the 24-query per-run maximum.
- All old experience categories and nine board entries retained with explicit modes; no claim that Indeed/Saramin/LinkedIn became unrestricted scrapers.

## Not implemented or not proven

No exhaustive list of every Korean studio; no universal ATS adapter; no full-site infinite crawling; no OCR/image-only notice extraction; no login scraping; no guaranteed matching between duplicate postings across different boards; no employer-confirmed eligibility decision; no auto-applications; no direct write to the five existing iCloud calendars; no update to the separately managed ChatGPT task; no deployment or successful end-to-end iCloud subscription test on the user's account.

A first deployed run must show actual source-health and detailed posting results. A source with errors must remain a manual/reconfiguration item, not silently disappear from the user's understanding of coverage.
