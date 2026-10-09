"""Explainable access review heuristics, never access decisions."""
from datetime import datetime, timezone

ELEVATED = {"admin", "maintain", "write", "push"}


def age_days(value: str | None, now=None):
    if not value:
        return None
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return max(0, ((now or datetime.now(timezone.utc)) - created).days)
    except (ValueError, TypeError):
        return None


def recommend(repo, grants, contributions, owners, *, now=None, evidence_complete=True):
    """Flag elevated grants for *manual review* only when evidence supports it."""
    output = []
    if repo.get("archived") or (age_days(repo.get("created_at"), now) or 0) < 30:
        return output
    for grant in grants:
        login = grant.get("login", "")
        permission = grant.get("permission", "read").lower()
        if not login or login in owners or permission not in ELEVATED:
            continue
        if login.endswith("[bot]") or any(term in login.lower() for term in ("bot", "service", "automation")):
            continue
        evidence = contributions.get(login, {})
        recent = int(evidence.get("commits", 0)) + int(evidence.get("prs", 0)) + int(evidence.get("reviews", 0))
        if recent > 0:
            continue
        outside = bool(grant.get("outside"))
        reason = "Elevated outside access with no recent contribution evidence" if outside else "Elevated access with no recent contribution evidence"
        caveat = "Contribution signals are incomplete; absence of activity is not proof that access is unnecessary." if not evidence_complete else "Work may occur outside this repository or through non-code responsibilities."
        output.append({
            "repo": repo["name"], "login": login, "permission": permission,
            "severity": "high" if outside and permission == "admin" else "medium" if outside else "low",
            "reason": reason, "evidence": f"{recent} observed commits, PRs, or reviews in the collection window",
            "uncertainty": caveat,
            "action": "Confirm role, ownership, and business need with the repository owner before any permission change.",
        })
    return output
