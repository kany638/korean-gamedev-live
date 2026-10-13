# V4 BROAD COVERAGE — Korean game-developer vacancy monitor

## What V4 now attempts

- **32 direct official careers-route entries** at first load: the 31 V3 routes plus the verified public 111percent careers page.
- **41 additional company-homepage discovery entries** seeded from publicly cited Korean game-industry member directories, known official company websites, and a few independently researched company sites. Company homepages are **not verified careers portals**; the collector must follow an actual employer-linked job route and verify the individual vacancy before publication.
- **3 official internship/new-graduate program pages** (NexTorial, Com2uS GENIUS, Smilegate).
- **9 declared boards/services** (including GameJob/JobKorea HTML attempts, Saramin approved API if enabled, and honest manual/authorized-only entries for platforms that are not programmatically scraped).
- **84 additional company names** in the company-discovery registry, including 42 without a currently verified website in the seed roster. Names without a verified website feed optional Naver discovery if authorized and enabled; they are *not* claimed as monitored careers websites.
- **Weekly attempts to refresh member directories** from the Korea Association of Game Industry (K-GAMES) and Korea Mobile Game Association (K-MGA). Discovery is evidence of a name or company homepage only; it is not proof of vacancies. Robots/HTTP failures are recorded, and the shipped seeds remain available.
- **Rotation of 18 additional company homepages per scheduled run**, so discovery covers more companies over multiple runs without increasing every run to hundreds of pages. A skipped homepage is explicitly marked as not checked in that run. In the updated seeded roster, 41 extra homepages require up to 3 scheduled turns for a full rotation *if each scheduled source is successfully reached*. Timeouts, access restrictions, and GitHub schedule delays can prevent complete rotation.
- Direct official careers roots remain the first-priority scheduled category; GameJob and JobKorea receive protected early attention in the secondary page/JS-rendering stage, instead of exhausting browser slots on company JS shells first.
- GameJob additionally attempts two publicly documented general/category listing URLs; JobKorea and other public HTML boards have limited JS-rendering fallback only after a successful permitted page fetch. Corporate-discovery sites have the same bounded permitted-page rendering fallback but receive lower priority than the core boards. **This is not every page or all jobs on those boards.**
- All earlier eligibility filters remain: 신입, 경력 0년, 경력무관, mixed 신입/경력, graduate-eligible internships, and clearly marked 1–3-year stretch roles. Older/senior-only requirements remain excluded when unambiguously present.
- Original job history and live calendar subscription URL identity remain intact when the upgrade script is used. V4 does not overwrite `data/state.json` or the generated `*.ics` during installation. GitHub regenerates them from saved state.

## Counts and provenance

An *entry* may share a group ATS with another entry and must not be presented as a distinct successfully monitored company. A corporate website is a discovery target, not a confirmed job listing or verified careers endpoint. Publishing a job still requires individual source/API verification.

Seed company information is based on these publicly identified directories and selected actual employer pages:
- K-GAMES official members: https://www.kgames.or.kr/partnership/partner-list/
- K-MGA members: https://www.k-mga.or.kr/content/27
- GameJob recruitment website: https://www.gamejob.co.kr/Recruit/Main
- Korea Creative Content Agency WelCon public company profiles: https://welcon.kocca.kr/en/directory/company?pageIndex=1
- 111percent's public careers page: https://111percent.career.greetinghr.com/ko/position
- LINE Games company page: https://www.line.games/company
- ESTgames company page: https://estgames.co.kr/company/

Companies and industry associations change over time. Some public association lists include non-developers; irrelevant service providers are excluded where possible, and the remaining entries must not be treated as proof of eligibility or openings.

## What is NOT covered in full

There is no public, complete and current list of *every* game employer in Korea and no authorized universal API for all game jobs. The collector therefore cannot guarantee complete coverage of all Korean game studios, every individual subsidiary, every GameJob/JobKorea page, closed/internal job ads, image-only announcements, or arbitrary external ATS software. It cannot bypass robots.txt, site logins, CAPTCHAs, restricted APIs, or anti-automation measures. Indeed/LinkedIn are authorized-only and Jumpit/RocketPunch remain manual/separate integrations.

Saramin API needs an approved access key and `saramin.enabled: true`. Naver Search API needs credentials and `naver.enabled: true`. Both remain disabled unless enabled by the owner; the upgrade **preserves** existing settings and does not touch GitHub Secrets.

A GitHub green check, 82 configured sources, or 17 published calendar events do **not** prove market-wide coverage. Use the public dashboard's source-health tab and distinguish `company discovery`, `direct careers`, `manual only`, `blocked`, and `scheduled_rotation_skip`. `last_listing_success` and `last_detail_success` matter more than the configuration count.

## Scheduling, budget, security

Scheduled checks target 08:12 / 13:12 / 20:12 KST. They are GitHub Actions schedules, not exact-time guarantees. V4 keeps the 18-minute scan transport budget and existing request and source limits; the roster is rotated so it cannot be scanned exhaustively each run. At default settings it uses only the public GitHub repository, standard runner and static Pages publishing; optional paid scraping/proxy or AI services are not enabled.

The website publishes only public job metadata. Do not add résumés, API keys, passports, private code, personal calendars or iCloud passwords to the public repository.

## How to confirm V4 after upgrading

1. Run the supplied `upgrade_existing_mac.command` **against your existing local recruitment Git repository**. It fetches latest `main`, saves an external backup, applies patches, *preserves original `config.yaml` API settings*, then asks for explicit `PUBLISH` before commit/push. A dirty working tree or unexpected Git remote stops the script.
2. Open `https://github.com/kany638/korean-gamedev-live/actions` and wait for `scan` and `deploy` to succeed. The updated unit suite currently has **207 passing offline tests** on the release source.
3. Open `https://kany638.github.io/korean-gamedev-live/` and inspect the source categories. The new `추가 게임사 홈페이지 발견` category should show new registered companies and rotation status.
4. Inspect actual detailed checks, the verified/blocked statuses, and `https://kany638.github.io/korean-gamedev-live/health.json`. If a source says no extractable links, it is **not** a declaration that no relevant jobs exist.
5. The previously configured Apple Calendar subscription URLs (`entry.ics`, `stretch.ics`, `review.ics`, `secondary.ics`) **remain unchanged** and will refresh after a successful Pages publication according to Apple's refresh schedule. No re-import should be done.

The included tests use simulated public HTML/API data. They do not demonstrate that every configured website will respond successfully to the real GitHub runner. The first live V4 run's source-health report is necessary for that verification.
