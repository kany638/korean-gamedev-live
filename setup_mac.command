#!/bin/bash
# Creates ONLY a new, separate public repository after explicit local consent.
# Never run from inside the Unreal portfolio repository. No Apple credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
cd "$ROOT"
REPO="korean-gamedev-live"
for f in config.yaml src/monitor.py .github/workflows/update-live-calendar.yml site/index.html; do
  [[ -f "$f" ]] || { printf 'Missing package file: %s\n' "$f"; exit 1; }
done
command -v git >/dev/null || { echo 'Install Apple Command Line Tools (xcode-select --install), then rerun.'; exit 1; }
command -v gh >/dev/null || { echo 'Install GitHub CLI from https://cli.github.com/ . With Homebrew already installed: brew install gh'; exit 1; }
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo 'STOP: This folder is already in a Git repository.'
  echo 'Do not initialize or publish inside your Unreal/private repository.'
  echo 'For an existing live-calendar repo, follow the UPGRADE section in README.md.'
  exit 1
fi
if [[ -e .env ]]; then
  echo 'STOP: .env exists. Move secrets out of this folder before publishing; use GitHub Actions secrets.'; exit 1
fi
cat <<'NOTICE'
This setup will publish a NEW PUBLIC GitHub repository named korean-gamedev-live.
The code, search rules, job metadata, source-health history and calendar feed will be public.
DO NOT put your résumé, private game code, Apple password, API keys or application status here.
Standard public GitHub runners + small Pages site are intended to stay within free allowances.
No paid AI API or commercial crawler is enabled. Additional API integrations remain off.
This is a limited source monitor, NOT complete coverage of every job board.
NOTICE
read -r -p 'Type PUBLIC to approve publishing this separate project: ' consent
[[ "$consent" == PUBLIC ]] || { echo 'Cancelled; nothing created.'; exit 0; }
if ! gh auth status >/dev/null 2>&1; then gh auth login --web --git-protocol https; fi
LOGIN="$(gh api user --jq .login)"
if gh repo view "$LOGIN/$REPO" >/dev/null 2>&1; then
  echo "STOP: $LOGIN/$REPO already exists. Use the upgrade instructions; do not overwrite its state."; exit 1
fi
git init -b main
# Repo-local identity only; do not change the user's global Git configuration.
if ! git config user.name >/dev/null; then git config user.name "$LOGIN"; fi
if ! git config user.email >/dev/null; then git config user.email "$LOGIN@users.noreply.github.com"; fi
# Explicit allowlist avoids accidentally including unrelated files or .env credentials.
git add .github .gitignore .env.example config.yaml requirements.txt src tests tools site data docs README.md 시작하기_맥북네오.md setup_mac.command
git commit -m 'Deploy source-aware live recruitment calendar v3'
gh repo create "$LOGIN/$REPO" --public --source=. --remote=origin --push --description 'Personal, source-aware Korean game-programming vacancy calendar'
if gh api --method POST "repos/$LOGIN/$REPO/pages" -f build_type=workflow >/dev/null 2>&1; then
  echo 'GitHub Pages enabled for Actions.'
else
  echo 'Pages automatic setup did not complete. In GitHub: Settings > Pages > Source > GitHub Actions.'
fi
if ! gh workflow run update-live-calendar.yml --repo "$LOGIN/$REPO" >/dev/null 2>&1; then
  echo 'Manual workflow dispatch not yet available. Open Actions and choose Run workflow after the repository is ready.'
fi
printf '\nRepository: https://github.com/%s/%s\n' "$LOGIN" "$REPO"
printf 'Actions: https://github.com/%s/%s/actions\n' "$LOGIN" "$REPO"
printf 'After a successful Pages deployment, dashboard: https://%s.github.io/%s/\n' "$LOGIN" "$REPO"
printf 'After verifying collection health, calendar subscription URL: https://%s.github.io/%s/calendar.ics\n' "$LOGIN" "$REPO"
echo 'Deployment != collection success. Inspect verified-detail counts and each source status.'
echo 'Use File > New Calendar Subscription on Mac, NOT File > Import. Location: iCloud.'
