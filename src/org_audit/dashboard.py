"""Self-contained, escaped, responsive static dashboard."""
from __future__ import annotations

from html import escape
from urllib.parse import urlparse


def e(value):
    return escape(str(value if value is not None else "—"), quote=True)


def link(value, label):
    parsed = urlparse(value or "")
    if parsed.scheme == "https" and parsed.hostname == "github.com":
        return f'<a href="{e(value)}" rel="noopener noreferrer">{e(label)}</a>'
    return e(label)


def table(headers, rows, empty):
    if not rows:
        return f'<p class="empty">{e(empty)}</p>'
    head = "".join(f"<th scope='col'>{e(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render(data):
    mode = data.get("mode", "unknown")
    repos = data.get("repositories") or []
    alerts = data.get("advisories") or []
    members = data.get("members") or []
    grants = data.get("grants") or []
    recs = data.get("recommendations") or []
    contributors = data.get("contributions") or []
    warnings = data.get("warnings") or []
    notes = data.get("notes") or []
    cards = [("Repositories", len(repos)), ("Open advisories", len(alerts)), ("Members visible", len(members)), ("Review prompts", len(recs))]
    cards_html = "".join(f'<article class="metric"><span>{e(label)}</span><strong>{value}</strong></article>' for label, value in cards)
    repo_rows = [[link(r.get("url"), r.get("name", "?")), e(r.get("visibility")), e("Archived" if r.get("archived") else "Active"), e("Yes" if r.get("fork") else "No"), e(r.get("pushed_at") or "Unknown")] for r in repos]
    alert_rows = [[e(a.get("repo")), f'<span class="pill">{e(a.get("severity"))}</span>', e(a.get("package")), link(a.get("url"), a.get("summary") or "Advisory")] for a in alerts]
    member_rows = [[e(x.get("login")), e(x.get("commits", 0)), e(x.get("prs", 0)), e(x.get("reviews", 0))] for x in contributors]
    grant_rows = [[e(g.get("repo")), e(g.get("login")), e(g.get("permission")), e(g.get("source")), e("Yes" if g.get("outside") else "No")] for g in grants]
    rec_rows = [[f'<span class="pill {e(x.get("severity"))}">{e(x.get("severity"))}</span>', e(x.get("repo")), e(x.get("login")), e(x.get("reason")), e(x.get("evidence")), e(x.get("uncertainty")), e(x.get("action"))] for x in recs]
    warning_html = "".join(f"<li>{e(x)}</li>" for x in warnings) or "<li>No collection warnings.</li>"
    notes_html = "".join(f"<li>{e(x)}</li>" for x in notes) or "<li>No additional notes.</li>"
    style = """
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#090f1b;color:#e5eefb}*{box-sizing:border-box}body{margin:0;line-height:1.55}a{color:#5eead4}a:hover,a:focus{color:#a7f3d0}header{padding:3rem 1rem 2rem;background:radial-gradient(circle at 80% 10%,#123b4a,#111a2c 45%,#090f1b 80%);border-bottom:1px solid #26384a}.wrap{max-width:1240px;margin:auto;padding:0 1.1rem}.eyebrow{color:#5eead4;letter-spacing:.17em;text-transform:uppercase;font-size:.78rem;font-weight:700}h1{font-size:clamp(2rem,5vw,4rem);line-height:1.1;margin:.5rem 0}h2{font-size:1.5rem;margin:0 0 1rem}p{max-width:75ch}.sub{color:#a8b8cb}.mode{display:inline-block;padding:.3rem .7rem;border:1px solid #2dd4bf;border-radius:99px;color:#5eead4;font-size:.8rem;text-transform:uppercase;font-weight:700}nav{position:sticky;top:0;background:#0c1522ed;backdrop-filter:blur(14px);border-bottom:1px solid #26384a;z-index:2;overflow-x:auto}nav .wrap{display:flex;gap:1.5rem;white-space:nowrap;padding-top:.8rem;padding-bottom:.8rem}nav a{text-decoration:none;color:#cbd5e1;font-size:.9rem}nav a:hover{color:#5eead4}main{padding-top:2rem;padding-bottom:4rem}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}.metric,.panel{background:#121d2b;border:1px solid #27384a;border-radius:15px}.metric{padding:1.2rem}.metric span{display:block;color:#9aacc0;font-size:.9rem}.metric strong{display:block;font-size:2.2rem;color:#f8fafc}section{scroll-margin-top:5rem;margin-top:2.5rem}.panel{padding:1.3rem}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:.8rem .7rem;border-bottom:1px solid #28384a;vertical-align:top}th{color:#9cb2c8;font-size:.78rem;text-transform:uppercase;letter-spacing:.08em}tr:hover{background:#1a2a3b}.pill{display:inline-block;border:1px solid #456070;border-radius:99px;padding:.1rem .5rem;text-transform:capitalize}.pill.high{color:#fda4af;border-color:#b33d55}.pill.medium{color:#fcd34d;border-color:#a17b29}.pill.low{color:#86efac;border-color:#337b4b}.empty{color:#9cb2c8;padding:1rem;border:1px dashed #40566a;border-radius:9px}.filter{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;margin-bottom:1rem}.filter input{background:#0b1522;color:#fff;border:1px solid #466176;border-radius:8px;padding:.55rem .7rem;min-width:min(100%,320px)}li{margin:.35rem 0}footer{border-top:1px solid #26384a;padding:2rem 0;color:#9cb2c8}@media(max-width:750px){.grid{grid-template-columns:repeat(2,1fr)}header{padding-top:2rem}th,td{min-width:7rem}}@media(max-width:420px){.grid{grid-template-columns:1fr 1fr}.metric{padding:.9rem}.metric strong{font-size:1.7rem}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""
    js = """const input=document.getElementById('access-filter');if(input){input.addEventListener('input',()=>{const q=input.value.toLocaleLowerCase();for(const row of document.querySelectorAll('#access-table tbody tr'))row.hidden=!row.textContent.toLocaleLowerCase().includes(q)})}"""
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><meta name="description" content="Read-only GitHub organization access and security audit"><title>{e(data.get("organization"))} · Access Audit</title><style>{style}</style></head><body>
<header><div class="wrap"><span class="eyebrow">GitHub organization intelligence</span><h1>Access &amp; security audit</h1><p class="sub">Evidence for a careful human review of <strong>{e(data.get("organization"))}</strong>. This report never changes GitHub access.</p><span class="mode">{e(mode)} data</span><p class="sub">Generated {e(data.get("generated_at"))} · {e(data.get("window_days"))}-day contribution window</p></div></header>
<nav aria-label="Dashboard sections"><div class="wrap"><a href="#overview">Overview</a><a href="#repositories">Repositories</a><a href="#advisories">Advisories</a><a href="#members">Members</a><a href="#access">Access</a><a href="#review">Review prompts</a><a href="#notes">Execution notes</a></div></nav>
<main class="wrap"><section id="overview"><h2>Executive overview</h2><div class="grid">{cards_html}</div><p class="sub">Counts reflect data visible to the supplied token. Read execution notes before interpreting zeroes.</p></section>
<section id="repositories" class="panel"><h2>Repositories</h2>{table(["Repository","Visibility","State","Fork","Last push"],repo_rows,"No repositories were returned.")}</section>
<section id="advisories" class="panel"><h2>Security advisories</h2>{table(["Repository","Severity","Package","Advisory"],alert_rows,"No accessible open advisories were returned. Check execution notes for permission gaps.")}</section>
<section id="members" class="panel"><h2>Members &amp; contribution evidence</h2><p class="sub">Visible organization members: {len(members)}. Commit and authored PR counts are partial signals; reviews are not collected.</p>{table(["Login","Commits","PRs","Reviews"],member_rows,"No contribution evidence was returned.")}</section>
<section id="access" class="panel"><h2>Access inventory</h2><div class="filter"><label for="access-filter">Filter grants</label><input id="access-filter" type="search" placeholder="Repository, login, role…"></div><div id="access-table">{table(["Repository","Login or team","Permission","Source","Outside"],grant_rows,"No grants were visible to this token.")}</div></section>
<section id="review" class="panel"><h2>Access review recommendations</h2><p class="sub">Prompts for investigation only. Low activity alone is never a removal decision. Owners, bots, archived repositories, and new repositories are excluded from these prompts.</p>{table(["Risk","Repository","Login","Reason","Evidence","Uncertainty","Manual action"],rec_rows,"No review prompts met the current conservative rules.")}</section>
<section id="notes" class="panel"><h2>Execution notes</h2><h3>Collection warnings</h3><ul>{warning_html}</ul><h3>Interpretation</h3><ul>{notes_html}</ul></section></main><footer><div class="wrap">Read-only by design · Review with context before changing access elsewhere.</div></footer><script>{js}</script></body></html>'''
