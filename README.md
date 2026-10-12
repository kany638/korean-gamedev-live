# Korean GameDev Live iCloud Calendar — V3

**Official-company career checks + job boards. Not deployed by downloading this ZIP.**

- [MacBook Neo setup/upgrade guide (Korean)](시작하기_맥북네오.md)
- [All configured sources and limitations](docs/SOURCE_COVERAGE.md)
- [Tests and limits of verification](docs/AUDIT_REPORT.md)
- [Costs and primary references](docs/COSTS_AND_REFERENCES.md)

## What this version does

It prioritises **31 official employer/group career routes**, then **3 official programme pages**, while retaining **9 job-board entries** with explicit access modes. It is a finite maintained register, not every Korean game company and not 43 confirmed-working collectors.

Candidate priorities remain: C++/Unreal client/gameplay/combat/AI/character-animation/engine/rendering programming, 신입, zero years, 경력무관, already-graduated eligible internships, and minimum 1–3-year jobs as stretch applications. Unity/C#/HTML5/server/tools can appear as labelled secondary opportunities. The code does not count IT work or a portfolio as paid game-programming experience. Location/graduate eligibility can remain unknown; read the original posting.

Company sites are read directly, including declared official ATS destinations. Public HTML and embedded structured links are attempted first; bounded public-page Chromium rendering is available when successfully fetched HTML has no extractable candidates. Access controls and robots are not bypassed. 5minlab has a dedicated adapter for the documented public Greenhouse Job Board API. Listings/search snippets alone do not certify deadlines.

Every configured source has its own health row, actual path attempts, list/detail counts and last successful timestamps. Company, programme and board rows can be filtered separately. A root with no links, a corporate placeholder or a blocked site is not reported as having no vacancies. Some routes still need site-specific maintenance after deployment.

## Schedule and publication

The GitHub Actions workflow targets 08:12, 13:12 and 20:12 Asia/Seoul using UTC cron `12 4,11,23 * * *`. GitHub can delay/drop runs or disable inactive schedules. It does not continuously crawl. Rules/budgets are in config.yaml; per-run ceilings are not exhaustive coverage.

The action saves metadata/state and publishes static Pages files. Apple Calendar subscribes to the hosted feed URL (File → New Calendar Subscription, Location → iCloud). A downloaded/imported ICS file is static. Existing five forecast/portfolio calendars are untouched; the live subscription is separate and read-only. A new opening needs to be discovered, verified, published, and then fetched by Apple's subscription refresh. That entire path has not been deployed/tested on your account here.

## New installation

Extract into a separate folder outside all other Git repositories. Install Git and GitHub CLI locally, then:

```bash
chmod +x setup_mac.command
./setup_mac.command
```

The script asks you to type PUBLIC before publishing a **new public** repository, refuses existing Git repositories/.env files, authenticates through your own local GitHub CLI, and never asks for an Apple password. The registry, suitability rules, public job metadata and source health become public. Do not place résumés, applications, private calendars, passwords or GOW code in the repo.

After an Actions deployment, check source-health results at:

```text
https://YOUR_GITHUB_USERNAME.github.io/korean-gamedev-live/
```

The single feed is `calendar.ics`. Alternatively subscribe to `entry.ics`, `stretch.ics`, `review.ics` and `secondary.ics`. Do not subscribe to both the combined and split versions.

## UPGRADE from a deployed V1/V2

Do not rerun setup_mac.command or rename the repo/feed. Pull the latest repo first. Back up **data/state.json** outside the repo. Replace code, tests, workflow, requirements and documentation; merge config.yaml so any enabled optional APIs and custom sources are retained. Copy only `site/index.html`, `site/dashboard.js`, `site/style.css` and `.nojekyll` from the new website directory. **Do not overwrite your live data/state.json, site/*.ics, jobs.json or health.json with the empty initial files from this ZIP.**

Inspect `git diff` and preserve your existing state. Commit/push code updates, then run the workflow. The next successful scan regenerates health, source_catalog and calendar feeds at the same subscription URL. Existing records retain their first-seen timestamps and canonical-URL event identity. See the Korean guide for step-by-step details.

## Optional provider integrations

Saramin and Naver are disabled until approved/configured. GitHub Actions Secrets: `SARAMIN_ACCESS_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`. Enable the appropriate configuration block after storing credentials securely. Search discovery rotates across the enlarged query list, with 24 queries maximum per run. It does not verify Indeed/LinkedIn postings or authorize scraping. Indeed/LinkedIn are authorization-only; Jumpit/RocketPunch remain manual.

No paid LLM or commercial proxy is used. See costs and primary references. Public standard runners/small Pages hosting are expected to remain free within GitHub's applicable allowances, not an unconditional forever-free guarantee.

## Local checks

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m pytest -q
python tools/validate_output.py .
python tools/browser_smoke.py
```

`browser_smoke.py` checks the dashboard using mocked JSON with offline DOM content; it is not an employer collection test. The GitHub workflow installs Chromium/system dependencies separately before real scans. Live runs use `python -m src.monitor`; API keys belong in environment secrets, not source files.

## State and calendar safety

Known URLs are rechecked even if they disappear from the first listing page. Changed verified deadlines update the same URL-based UID rather than create another event. Transient failures retain stale records; two 404/410 results or explicit closure/expiry can close them. Corrupt JSON state is not silently reset. A `검토` event is not a deadline. Full-year dates/time-zone-aware structured metadata are needed for confidently timed deadlines; unknown times are not changed to 23:59. Cross-board repost duplicates and parser errors remain possible.

Uncollected HTML leads have a bounded, expiring backlog; jobs omitted by inaccessible pages/search indexing still cannot be recovered magically. Site redesigns, JS-only APIs, strict robots and missing individual ATS adapters need maintenance. Neither zero jobs nor a green GitHub action proves complete monitoring.

## Separate ChatGPT task

This package does not change, inspect or depend on the separate ChatGPT scheduled task. `docs/CHATGPT_MONITOR_PROMPT.txt` contains matching official-site-first instructions for a separately managed task. No claim is made that uploading this package edits that task or passes its results into the hosted calendar.
