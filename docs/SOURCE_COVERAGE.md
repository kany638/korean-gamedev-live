# V3 — Company career sites and job-board coverage

Audit date: 2026-10-08. This is a **configured source register**, not a claim that all sources have been collected successfully.

31 official company/group career routes + 3 official programme pages + 9 job-board entries = 43 entries. Some routes share a group portal; these are not 43 distinct employers. Naver is an additional optional discovery API, shown separately in runtime health. Group `targets` are monitoring intentions, not an ownership chart or proof that every subsidiary is covered.

## How a run checks official websites

1. Attempt the configured public career roots, with employers before programme pages and boards. Rotate within a priority level between runs.
2. Extract recognisable job-detail links, JSON-LD JobPosting/ItemList links, and `__NEXT_DATA__` job links. Search/list snippets do not verify a vacancy.
3. Follow declared career navigation/ATS domains and bounded pagination. When the official site labels a link APPLY, use only a nearby role heading; do not borrow another role's heading.
4. For successfully received but unextractable public HTML, try bounded Playwright rendering. This is NOT a way around an HTTP/robots/auth/CAPTCHA denial. GET resources must pass the same bounded transport and explicit source/resource domain checks; cross-domain or POST-dependent sites may remain unreadable.
5. 5minlab uses its employer-linked Greenhouse board and the documented public read-only Job Board API. Fetch individual candidate records to check their content/deadline. No application-submission API is used.
6. Re-fetch individual job details or approved API records before classification. Keep first-seen identity and recheck known records, even when they disappear from the first list page.
7. Keep failed/stale/deferred/unverified states visible. A successful deployment is not a successful source check, and no extracted links is not proof of no vacancies.

Configured maximums per scheduled run: 120 detail candidates, 3 pages per official route (2 for programme/board routes), 24 rendered pages total, 900 HTTP requests total, 100 per host, 18 minutes total transport budget, and 12 minutes for list discovery. These are ceilings, not promises; time/rate/access restrictions can stop a scan sooner. At most 1,800 deferred HTML lead identities are retained for up to 14 days. Approved API leads still depend on the provider's returned set. Exact-URL deduplication does not guarantee cross-board deduplication of the same employer's repost.

## Official company/group routes

`Reference status` records what web research could see (often a cached page) or that a linked route was followed. It does not record a successful request by the deployed Python collector. Runtime success appears separately in `site/health.json`.

| # | Source | Configured entry | Reference status | Method |
|---:|---|---|---|---|
| 1 | 펄어비스 | https://www.pearlabyss.com/ko-KR/Company/Careers/List | listing_visible | html / pearlabyss |
| 2 | 넥슨 그룹 | https://careers.nexon.com/recruit | javascript_or_shell | html / official |
| 3 | 넥슨게임즈 · 공식 법인 필터 | https://careers.nexon.com/recruit?corpCodes=AG | official_link_followed | html / official |
| 4 | 네오플 · 공식 채용 경로 | https://www.neople.co.kr/recruit | official_landing | html / official |
| 5 | 민트로켓 · 공식 채용 경로 | https://www.mintrock.et/en/careers/careers.php | official_landing | html / official |
| 6 | 스마일게이트 그룹 | https://rct.smilegate.com/apply/announce | javascript_or_shell | html / official |
| 7 | NC · 그룹 채용 | https://careers.ncsoft.com/apply/list | javascript_or_shell | html / official |
| 8 | 시프트업 | https://shiftup.co.kr/recruit/recruit.php | javascript_or_shell | html / official |
| 9 | 네오위즈 · ROUND8 | https://www.neowiz.com/kr/career/browse-job | web_access_blocked | html / official |
| 10 | 크래프톤 · 스튜디오 채용 | https://recruit.krafton.com/ | web_fetch_failed | html / official |
| 11 | 넷마블 · 개발 스튜디오 | https://career.netmarble.com/ | javascript_or_shell | html / official |
| 12 | 웹젠 | https://webzen.recruiter.co.kr/career/job | javascript_or_shell | html / official |
| 13 | 컴투스 그룹 · 공식 리다이렉트 | https://recruit.com2us.com/ | official_redirect | html / official |
| 14 | 카카오게임즈 | https://recruit.kakaogames.com/ko/joinjuskr | web_access_blocked | html / official |
| 15 | 데브시스터즈 | https://careers.devsisters.com/ko/home | listing_visible | html / official |
| 16 | 라이온하트 스튜디오 | https://career.lionheart.co.kr/recruit | javascript_or_shell | html / official |
| 17 | 위메이드 | https://recruit.wemade.com/oz6xlsi9 | javascript_or_shell | html / official |
| 18 | NHN · 게임 프로그래밍 선별 | https://careers.nhn.com/ | official_link_followed | html / official |
| 19 | 엔픽셀 | https://recruit.npixel.co.kr/recruit | javascript_or_shell | html / official |
| 20 | 5민랩 · 공식 Greenhouse 공고 | https://job-boards.greenhouse.io/5minlab | official_link_followed | public_api / greenhouse |
| 21 | 엑스엘게임즈 | https://xlgames.recruiter.co.kr/appsite/company/index | official_link_followed | html / official |
| 22 | KOG · 근무지 별도 확인 | https://www.kog.co.kr/recruit/info | javascript_or_shell | html / official |
| 23 | 데브캣 | https://devcat.com/careers | official_landing | html / official |
| 24 | 슈퍼캣 | https://apply.supercat.co.kr/ | official_link_followed | html / official |
| 25 | 하운드13 · 회사가 연결한 공고 포함 | https://www.hound13.com/en | employer_links_to_gamejob | html / official |
| 26 | 조이시티 · 공식 채용 경로 탐색 | https://corp.joycity.com/ko/main | official_landing | html / official |
| 27 | 그라비티 | https://www.gravity.co.kr/en/recruit/jobopening/list | official_link_followed | html / official |
| 28 | 플레이위드 | https://www.playwith.co.kr/Recruit | official_link_followed | html / official |
| 29 | 매드엔진 · 채용 경로 재확인 | https://www.madngine.com/ | javascript_or_shell | html / official |
| 30 | 넵튠 · 채용 경로 재확인 | https://www.neptunecompany.kr/ | javascript_or_shell | html / official |
| 31 | 썸에이지 · 공식 채용 경로 탐색 | https://www.thumbage.co.kr/Main | official_landing | html / official |

Some entries, notably Madngine, Neptune and Thumbage, begin from a corporate landing page because a distinct current public jobs endpoint was not established. They are **career-route discovery attempts**, not proven job collectors. JavaScript shells and HTTP denial findings are retained rather than hidden.

## Official programme pages

Programme pages may show past-year intake material. Only a recognisable dated intake with an actual parseable non-expired application end date, or a separately verified job posting, can enter the feed. Generic May/November schedules are not official upcoming deadlines. Full-year date extraction is conservative and can miss image-only/abbreviated dates.

| Programme | Entry | Runtime mode |
|---|---|---|
| 넥토리얼 · 공식 프로그램 | https://nexon-tutorial.com/ | html + bounded rendering |
| 컴투스 GENIUS · 공식 프로그램 | https://www.welcom2us.com/ | html + bounded rendering |
| 스마일게이트 · 공식 인턴십 안내 | https://rct.smilegate.com/student/internship?type=job | html + bounded rendering |

## Job boards — retained, not silently removed

| Board | Entry | Configured mode | Meaning |
|---|---|---|---|
| 게임잡 GameJob | https://www.gamejob.co.kr/Recruit/joblist?menucode=searchall | html | Public HTML attempt; no exhaustive or guaranteed JS coverage. |
| 잡코리아 JobKorea | https://www.jobkorea.co.kr/recruit/joblist | html | Public HTML attempt; no exhaustive or guaranteed JS coverage. |
| 사람인 Saramin · 승인 API | https://oapi.saramin.co.kr/guide/job-search | api | Saramin approval and key required; disabled initially. |
| Indeed Korea · 허가된 연동/직접 확인 | https://kr.indeed.com/jobs?q=Unreal+game+developer&l=South+Korea | authorized_only | Not scraped. Explicit provider-authorized integration required. |
| 원티드 Wanted | https://www.wanted.co.kr/wdlist | html | Public HTML attempt; no exhaustive or guaranteed JS coverage. |
| 인크루트 Incruit | https://job.incruit.com/jobdb_list/searchjob.asp?col=all&kw=%EA%B2%8C%EC%9E%84 | html | Public HTML attempt; no exhaustive or guaranteed JS coverage. |
| 점핏 Jumpit · 직접 확인 | https://jumpit.saramin.co.kr/ | manual | Not automatically collected by this version. |
| LinkedIn · 허가된 연동/직접 확인 | https://www.linkedin.com/jobs/ | authorized_only | Not scraped. Explicit provider-authorized integration required. |
| 로켓펀치 · 직접 확인 | https://www.rocketpunch.com/jobs | manual | Not automatically collected by this version. |

Naver discovery remains off until credentials are configured. Its existing per-run cap is 24 queries; the larger query registry now rotates across runs, including targeted company-domain queries. Search results are discovery, not verified deadlines. An Indeed/LinkedIn search hit stays unverified and is not scraped or published as a confirmed deadline.

## Provenance corrections and reference links

- Nexon Games: official careers page https://www.nexongames.co.kr/adopt/job.php and the homepage's linked company-filtered group careers route https://careers.nexon.com/recruit?corpCodes=AG . The URL normalizer now preserves that filter.
- Com2uS: https://recruit.com2us.com/ redirects to https://com2us.recruiter.co.kr/career/career . Do not substitute a different Holdings portal as complete Com2uS coverage.
- 5minlab: https://5minlab.com/ko/careers_kr/ links to https://job-boards.greenhouse.io/5minlab . Greenhouse public Job Board API documentation: https://developers.greenhouse.io/job-board.html . `updated_at` is not a deadline.
- Hound13: https://www.hound13.com/en contains role headings and outbound APPLY links. Such employer-linked board postings are handled as official-origin discoveries, still requiring details verification.
- NHN official jobs entry: https://careers.nhn.com/ (plural careers).
- Research pages can be cached. No live individual vacancy or current deadline is endorsed by this register alone.

## Coverage cannot be exhaustive

This does not cover every Korean studio, private/login-only listing, image-based notice, ATS endpoint or newly renamed company. It does not bypass restrictions, infer missing dates, automatically apply, or treat 1–3-year experience requirements as satisfied by academy/portfolio/IT experience. Use failed-source rows as an explicit manual-check list.
