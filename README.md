# GitHub Organization Access Audit

A read-only Python collector and responsive static dashboard for a **human** organization access review. It inventories repositories, visible access grants, open Dependabot alerts, and recent code contributions, then produces cautious, explainable review prompts. It never changes permissions.

![CI](https://github.com/Gaurav598/GitHub-Org-Access-Audit-Dashboard/actions/workflows/ci.yml/badge.svg)

## What it does

- Discovers organization repositories through the GitHub REST API with pagination, timeouts, bounded retries, and rate-limit errors.
- Inventories repository visibility, archived/fork status, last push, direct collaborators, teams, members, and outside collaborators when the token permits.
- Reads accessible open Dependabot alerts and recent commits and authored PRs.
- Flags elevated access for **manual review** only after excluding organization owners, bots, new repositories, and archived repositories. Missing access evidence suppresses recommendations.
- Generates a self-contained HTML dashboard with overview, inventory, advisories, contribution evidence, review prompts, filters, and execution notes.
- Runs a synthetic demo without credentials. No real organization information is bundled.

## Architecture

```text
GitHub REST API (GET only) → api.py → collector.py → review.py → dashboard.py
                                                         ↓
                                             local out/dashboard.html
```

The collector keeps partial-access warnings in the report. Private live results stay in local `out/`, which is Git-ignored. The browser view is static and makes no GitHub API calls.

## Prerequisites

Python 3.11+. No runtime dependencies or frontend build step are required.

## Quick start: synthetic demo

```bash
python3 -m pip install -e .
python3 -m org_audit mock --out out
python3 -m org_audit serve --out out
```

Open `http://127.0.0.1:8765/dashboard.html`, or open `out/dashboard.html` directly. The bundled `src/org_audit/data/mock.json` organization `northstar-demo` and its people are fictional.

## Authorized live mode

Create a read-only fine-grained GitHub token approved for the organization. Configure it in your shell environment; do not place it on the command line or in Git:

```bash
export GITHUB_ORG="your-org"
export GITHUB_TOKEN="your-read-only-token"
python3 -m org_audit live --out out --window-days 90 --max-pages 5
python3 -m org_audit serve --out out
```

The tool never attempts to access a private organization without an org name and token. `--max-pages` is capped at 20; `--window-days` must be 1–365. A capped listing is reported as incomplete.

### GitHub permissions

The exact fine-grained token permissions depend on organization policy and endpoint visibility. Start with **read-only** organization members and repository metadata. For full inventory, grant read-only access to repository administration/collaborator and team metadata, contents/commits, pull requests, and Dependabot alerts. Organization approval may be required. A classic token may require broader `read:org` and `repo` scopes for private resources; assess that tradeoff before using one. The collector reports inaccessible optional endpoints and suppresses access recommendations when collaborator, outside-collaborator, or owner data is missing.

All network requests in `api.py` use `GET`. No workflow runs live audits automatically, and CI uses synthetic data only. The local server binds to `127.0.0.1`.

## Dashboard sections

- **Executive overview:** counts and mock/live provenance.
- **Repositories:** visibility, state, fork status, and last push.
- **Security advisories:** accessible open Dependabot alerts.
- **Members and contributions:** visible member count and partial commit/PR evidence.
- **Access inventory and review:** direct grants, team grants, conservative recommendations with uncertainty and manual next steps.
- **Execution notes:** permission gaps, pagination limits, and interpretation caveats.

`pushed_at` is only a proxy for activity. The tool does not measure issues, every review, work outside GitHub, or business responsibilities. A low or absent contribution count is **never** proof that someone should lose access. Team grants are inventoried but the recommendation engine currently reviews direct grants only. Generated reports may contain sensitive private organization data; keep them local and do not upload them as CI artifacts.

## Tests and checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src
python3 -m org_audit mock --out out
```

Tests mock API transport and cover pagination, auth failures, bounded retries, owner/bot safeguards, incomplete data, escaping, mock execution, missing-token behavior, and GET-only requests. CI runs these checks on push and pull requests. No live token is used in CI.

## Troubleshooting

- **Missing `GITHUB_TOKEN`:** set a token in your shell before `live`. Mock mode needs none.
- **403/404 on optional endpoints:** check the token’s read permissions and organization approval. The dashboard records gaps rather than interpreting unknown as zero.
- **Rate limit:** retry after the GitHub rate-limit window resets or reduce `--max-pages`.
- **Empty recommendations:** this can be normal, or it may mean ownership/collaborator visibility was incomplete. Read Execution notes.
- **Do not see a page:** run `mock` or `live` before `serve`, and open the loopback URL printed by the server.

API behavior follows [GitHub REST pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api), [organization members](https://docs.github.com/en/rest/orgs/members), [repository collaborators](https://docs.github.com/en/rest/collaborators/collaborators), and [Dependabot alerts](https://docs.github.com/en/rest/dependabot/alerts).
