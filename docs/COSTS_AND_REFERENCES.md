# Costs and primary references — V3

Default design: a separate public GitHub repository, standard Ubuntu GitHub-hosted runner, small GitHub Pages site, no paid model API or paid scraping proxy. Expected hosting spend is ₩0/month while staying inside the applicable public-repo/free allowances. Account-wide storage/usage, changed terms and user-added paid services can change that. This package neither bills an AI API nor hides one in its dependencies.

The browser fallback increases runtime and dependency download size; it is still the standard runner, not a large paid runner. Caps are in config.yaml. Secrets/API approvals remain the user's responsibility; adding Saramin/Naver credentials is not performed by this ZIP.

Official references checked during the 2026-10-08 rebuild:

- GitHub Actions billing and public standard runner treatment: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub Pages availability: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- Scheduled workflows, delays/drops and inactivity: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Apple subscription/iCloud/refresh support: https://support.apple.com/guide/calendar/subscribe-to-calendars-icl1022/mac
- Greenhouse documented public GET Job Board API: https://developers.greenhouse.io/job-board.html
- Playwright CI installation: https://playwright.dev/python/docs/ci-intro
- Official checkout action: https://github.com/actions/checkout
- Official setup-python action: https://github.com/actions/setup-python
- Saramin Job Search API: https://oapi.saramin.co.kr/guide/job-search
- Naver web search API: https://developers.naver.com/docs/serviceapi/search/web/web.md
- Indeed terms: https://www.indeed.com/legal

No Google Calendar, iCloud app-specific password or personal calendar contents are needed for a read-only public feed subscription. The feed and its suitability filter are public, which is a privacy tradeoff.
