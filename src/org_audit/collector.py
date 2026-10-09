"""Collect authorized organization metadata; every API request is GET."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from .api import AuditAPIError
from .review import recommend

LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
REPO = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_org(org):
    if not isinstance(org, str) or not LOGIN.fullmatch(org):
        raise ValueError("Invalid GitHub organization login")
    return org


def collect(client, org, *, max_pages=5, window_days=90):
    validate_org(org)
    if not 1 <= window_days <= 365:
        raise ValueError("window_days must be between 1 and 365")
    if not 1 <= max_pages <= 20:
        raise ValueError("max_pages must be between 1 and 20")
    prefix = f"/orgs/{quote(org)}/"
    warnings = []
    notes = []

    def optional(path, label):
        try:
            rows, truncated = client.pages(path, max_pages=max_pages)
            if truncated:
                warnings.append(f"{label}: pagination capped at {max_pages} pages")
            return rows, not truncated
        except AuditAPIError as error:
            warnings.append(f"{label}: {error}")
            return [], False

    # Repository listing is essential. Do not silently render an empty live report on failure.
    raw_repos, capped = client.pages(prefix + "repos?type=all&per_page=100", max_pages=max_pages)
    if capped:
        warnings.append("Repository listing was truncated by max_pages")
    raw_members, members_ok = optional(prefix + "members?per_page=100", "Organization members")
    raw_owners, owners_ok = optional(prefix + "members?role=admin&per_page=100", "Organization owners")
    raw_outside, outside_ok = optional(prefix + "outside_collaborators?per_page=100", "Outside collaborators")
    owners = {x.get("login") for x in raw_owners if x.get("login")}
    outside = {x.get("login") for x in raw_outside if x.get("login")}
    members = {x.get("login") for x in raw_members if x.get("login")}
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat().replace("+00:00", "Z")
    repositories, advisories, grants, recs = [], [], [], []
    contributions = {}
    for item in raw_repos:
        name = item.get("name")
        if not name or not REPO.fullmatch(name):
            warnings.append("Skipped a repository with an invalid name")
            continue
        repo = {
            "name": name, "url": item.get("html_url", ""),
            "visibility": item.get("visibility", "unknown"), "archived": bool(item.get("archived")),
            "fork": bool(item.get("fork")), "created_at": item.get("created_at"),
            "pushed_at": item.get("pushed_at"), "updated_at": item.get("updated_at"),
            "default_branch": item.get("default_branch"),
        }
        repositories.append(repo)
        root = f"/repos/{quote(org)}/{quote(name)}/"
        people, people_ok = optional(root + "collaborators?affiliation=all&per_page=100", f"{name} collaborators")
        teams, teams_ok = optional(root + "teams?per_page=100", f"{name} teams")
        alerts, alerts_ok = optional(root + "dependabot/alerts?state=open&per_page=100", f"{name} Dependabot alerts")
        commits, commits_ok = optional(root + f"commits?since={quote(since)}&per_page=100", f"{name} commits")
        pulls, pulls_ok = optional(root + "pulls?state=all&per_page=100", f"{name} pull requests")
        for person in people:
            login = person.get("login", "")
            permissions = person.get("permissions") or {}
            permission = person.get("role_name") or next((p for p in ("admin", "maintain", "push", "triage", "pull") if permissions.get(p)), "read")
            grants.append({"repo": name, "login": login, "permission": permission, "outside": login in outside, "source": "collaborator", "owner": login in owners})
        for team in teams:
            grants.append({"repo": name, "login": team.get("slug", ""), "permission": (team.get("permission") or "read"), "outside": False, "source": "team", "owner": False})
        for alert in alerts:
            advisory = alert.get("security_advisory") or {}
            dependency = alert.get("dependency") or {}
            package = dependency.get("package") or {}
            advisories.append({"repo": name, "severity": advisory.get("severity", "unknown"), "summary": advisory.get("summary", ""), "package": package.get("name", ""), "url": alert.get("html_url", ""), "created_at": alert.get("created_at")})
        repo_contrib = {}
        for commit in commits:
            login = (commit.get("author") or {}).get("login")
            if login:
                repo_contrib.setdefault(login, {"commits": 0, "prs": 0, "reviews": 0})["commits"] += 1
        for pull in pulls:
            login = (pull.get("user") or {}).get("login")
            if login and (pull.get("created_at") or "") >= since:
                repo_contrib.setdefault(login, {"commits": 0, "prs": 0, "reviews": 0})["prs"] += 1
        for login, evidence in repo_contrib.items():
            total = contributions.setdefault(login, {"login": login, "commits": 0, "prs": 0, "reviews": 0})
            total["commits"] += evidence["commits"]
            total["prs"] += evidence["prs"]
        repo_grants = [g for g in grants if g["repo"] == name and g["source"] == "collaborator"]
        if people_ok and owners_ok and outside_ok:
            recs.extend(recommend(repo, repo_grants, repo_contrib, owners, evidence_complete=commits_ok and pulls_ok))
        else:
            notes.append(f"{name}: access recommendations suppressed because ownership or collaborator data is incomplete")
        if not alerts_ok:
            notes.append(f"{name}: advisory count is unknown, not zero")
        if not teams_ok:
            notes.append(f"{name}: team access inventory is incomplete")
    return {
        "mode": "live", "organization": org, "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days, "repositories": repositories, "members": sorted(members),
        "outside_collaborators": sorted(outside), "owners": sorted(owners), "grants": grants,
        "advisories": advisories, "contributions": sorted(contributions.values(), key=lambda x: (-x["commits"] - x["prs"], x["login"])),
        "recommendations": recs, "warnings": warnings, "notes": notes + ["Pushed-at is a proxy for repository activity; reviews, issue work, and work outside GitHub are not measured."]
    }
