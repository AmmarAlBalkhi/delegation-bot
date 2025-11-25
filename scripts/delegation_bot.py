#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
What this script does:
- One fresh parent issue per occurrence: once | daily | weekly | monthly | every:N
- Idempotency via hidden markers in issue bodies (searchable, so re-runs never duplicate)
- Single-task files and multi-task files (top-level `tasks:` array) supported
- Real child issues with backlinks and a checklist in the parent
- Optional Project v2 date fields (best-effort; gracefully skipped if not configured)
- Nested child cadence can be limited to occur only WITHIN the parent window

YAML keys (per task)
  id: string (required)
  title: string (required)
  repository: "owner/repo" or "repo" (required unless REPO env given)
  interval: once | daily | weekly | monthly | every:N
  start: YYYY-MM-DD (optional anchor for every:N)
  date_active: YYYY-MM-DD (optional; also used for Project "Date active")
  due_in_days / due_date: optional
  assign: [logins]   (optional)
  labels: [strings]  (optional)
  project: "Your Project V2 Title" (optional)
  subtasks: [{ id, title, interval?, window? }] (optional)
    - interval on a child defaults to parent's interval if omitted
    - window: "per_parent" (default) or "within_parent"
      * within_parent enumerates child occurrences INSIDE the parent window

File layout examples
  tasks/daily-standup.md         # single task
  tasks/weekly-status.md         # single task with subtasks
  tasks/monthly-retro.md         # parent monthly + child cadence
  tasks/week-01.md               # multi: top-level tasks: [ ... ]

Run modes
  - Dry-run (default) -> logs actions, no changes
  - APPLY=true -> performs create/update via GitHub API
"""

from __future__ import annotations
import os, re, glob, math, html, typing as T
from datetime import datetime, date, timedelta, timezone
import calendar
import requests
import frontmatter

# --------------------------- Env & constants -------------------------------

APPLY = (os.getenv("APPLY", "false").strip().lower() == "true")
GH_TOKEN = os.getenv("GITHUB_TOKEN") or ""
PROJ_TOKEN = os.getenv("PROJECT_TOKEN") or os.getenv("GITHUB_TOKEN") or ""
REPO_ENV = os.getenv("REPO") or os.getenv("GITHUB_REPOSITORY") or ""

API = "https://api.github.com"
ISO = "%Y-%m-%d"

def debug(msg: str) -> None:
    print(("[APPLY] " if APPLY else "[DRY-RUN] ") + msg, flush=True)

# --------------------------- Time & intervals ------------------------------

def today_utc() -> date:
    return datetime.now(timezone.utc).date()

def parse_date(val: T.Optional[str]) -> T.Optional[date]:
    if not val: return None
    s = str(val).strip()
    for fmt in (ISO, "%Y-%m"):
        try:
            dt = datetime.strptime(s, fmt).date()
            if fmt == "%Y-%m":
                return date(dt.year, dt.month, 1)
            return dt
        except Exception:
            pass
    m = re.match(r"^(\d{4})-W(\d{2})$", s)
    if m:
        y, w = int(m.group(1)), int(m.group(2))
        return date.fromisocalendar(y, w, 1)
    return None

def parse_interval(s: T.Optional[str]) -> T.Tuple[str, T.Optional[int]]:
    if not s: return ("once", None)
    s = str(s).strip().lower()
    if s in ("once", "daily", "weekly", "monthly"): return (s, None)
    m = re.match(r"^every\s*:\s*(\d+)$", s)
    if m: return ("every", int(m.group(1)))
    return ("once", None)

def compute_occurrence_id(kind: str, n: T.Optional[int], anchor: T.Optional[date], now: date) -> str:
    if kind == "once": return "once"
    if kind == "daily": return now.strftime(ISO)
    if kind == "weekly":
        iso = now.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if kind == "monthly": return f"{now.year}-{now.month:02d}"
    if kind == "every":
        a = anchor or now
        # we still tag occurrence by current day
        return now.strftime(ISO)
    return now.strftime(ISO)

def parent_window(occ_id: T.Optional[str]) -> T.Optional[T.Tuple[date, date]]:
    if not occ_id or occ_id == "once": return None
    m = re.match(r"^(\d{4})-(\d{2})$", occ_id)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        last = calendar.monthrange(y, mo)[1]
        return date(y, mo, 1), date(y, mo, last)
    m = re.match(r"^(\d{4})-W(\d{2})$", occ_id)
    if m:
        y, w = int(m.group(1)), int(m.group(2))
        return date.fromisocalendar(y, w, 1), date.fromisocalendar(y, w, 7)
    try:
        d = datetime.strptime(occ_id, ISO).date()
        return d, d
    except Exception:
        return None

def enumerate_child_occs(kind: str, start: date, end: date) -> T.List[str]:
    out: T.List[str] = []
    if kind == "daily":
        d = start
        while d <= end:
            out.append(d.strftime(ISO))
            d += timedelta(days=1)
        return out
    if kind == "weekly":
        d = start - timedelta(days=(start.isoweekday()-1) % 7)
        while d <= end:
            if d >= start:
                iso = d.isocalendar()
                out.append(f"{iso.year}-W{iso.week:02d}")
            d += timedelta(days=7)
        return out
    # once or fallback
    if start == end:
        out.append(start.strftime(ISO))
    else:
        # choose a representative (month or week)
        if start.day == 1 and (end - start).days >= 27:
            out.append(start.strftime("%Y-%m"))
        else:
            iso = start.isocalendar()
            out.append(f"{iso.year}-W{iso.week:02d}")
    return out

# --------------------------- Markers & helpers -----------------------------

def family_key(task_id: str) -> str:
    return f"<!-- delegation-key:{task_id} -->"

def occ_tag(task_id: str, occ: T.Optional[str]) -> str:
    occ = occ or "once"
    return f"<!-- delegation-occ:{task_id}:{occ} -->"

def child_tag(parent_id: str, parent_occ: T.Optional[str], child_occ: T.Optional[str], sub_id: str) -> str:
    po = parent_occ or "once"
    co = child_occ or po
    return f"<!-- delegation-sub:{parent_id}:{po}:{co}:{sub_id} -->"

def ensure_list(val) -> T.List[str]:
    if not val: return []
    return list(val) if isinstance(val, (list, tuple)) else [val]

def normalized_repo(s: T.Optional[str]) -> T.Optional[str]:
    if not s: return None
    s = s.strip()
    if not s: return None
    if "/" in s: return s
    if REPO_ENV:
        owner = REPO_ENV.split("/")[0]
        return f"{owner}/{s}"
    return s

# --------------------------- GitHub API -----------------------------------

def gh(method: str, url: str, token: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Accept"] = "application/vnd.github+json"
    headers["Authorization"] = f"Bearer {token}"
    headers["X-GitHub-Api-Version"] = "2022-11-28"
    r = requests.request(method, url, headers=headers, **kwargs)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url} -> {r.status_code} {r.text[:500]}")
    return r

def search_issues(repo: str, query: str, token: str) -> T.List[dict]:
    r = gh("GET", f"{API}/search/issues", token, params={"q": query, "per_page": 10})
    return (r.json().get("items") or [])

def get_issue(repo: str, number: int, token: str) -> dict:
    return gh("GET", f"{API}/repos/{repo}/issues/{number}", token).json()

def create_issue(repo: str, title: str, body: str, assignees: T.List[str], labels: T.List[str], token: str) -> dict:
    payload = {"title": title, "body": body}
    if assignees: payload["assignees"] = assignees
    if labels: payload["labels"] = labels
    return gh("POST", f"{API}/repos/{repo}/issues", token, json=payload).json()

def update_issue_body(repo: str, number: int, body: str, token: str) -> dict:
    return gh("PATCH", f"{API}/repos/{repo}/issues/{number}", token, json={"body": body}).json()

# -------- Projects v2 (optional / best-effort) via GraphQL ----------------

GQL_PROJECTS = """
query GetProjects($first:Int!) {
  viewer { projectsV2(first:$first){ nodes{ id title } } }
}
"""
GQL_FIELDS = """
query GetProjectFields($id:ID!){
  node(id:$id){ ... on ProjectV2 {
    id
    fields(first:50){ nodes{
      ... on ProjectV2Field{ id name dataType }
      ... on ProjectV2DateField{ id name dataType }
    } }
  } }
}
"""
GQL_ADD = """
mutation AddItem($projectId:ID!,$contentId:ID!){
  addProjectV2ItemById(input:{projectId:$projectId,contentId:$contentId}){ item{ id } }
}
"""
GQL_SETDATE = """
mutation SetDate($projectId:ID!,$itemId:ID!,$fieldId:ID!,$value:String!){
  updateProjectV2ItemFieldValue(input:{
    projectId:$projectId,itemId:$itemId,fieldId:$fieldId,value:{date:$value}
  }){ projectV2Item{ id } }
}
"""

def gql(query: str, variables: dict, token: str) -> dict:
    r = gh("POST", f"{API}/graphql", token, json={"query": query, "variables": variables})
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"GraphQL: {data['errors']}")
    return data["data"]

def find_project_id_by_title(title: str, token: str) -> T.Optional[str]:
    data = gql(GQL_PROJECTS, {"first": 50}, token)
    nodes = (((data or {}).get("viewer") or {}).get("projectsV2") or {}).get("nodes") or []
    for n in nodes:
        if (n.get("title") or "").strip() == title.strip():
            return n.get("id")
    return None

def get_project_field_ids(pid: str, token: str) -> dict:
    data = gql(GQL_FIELDS, {"id": pid}, token)
    nodes = ((((data or {}).get("node") or {}).get("fields") or {}).get("nodes") or [])
    out = {}
    for f in nodes:
        name = f.get("name")
        if name in ("Date active", "Due date"):
            out[name] = f.get("id")
    return out

def add_to_project_and_dates(issue_node_id: str, project_title: str, date_active: T.Optional[date], due_date: T.Optional[date], token: str) -> None:
    if not project_title: return
    pid = find_project_id_by_title(project_title, token)
    if not pid: return
    item = gql(GQL_ADD, {"projectId": pid, "contentId": issue_node_id}, token)
    item_id = (((item or {}).get("addProjectV2ItemById") or {}).get("item") or {}).get("id")
    fields = get_project_field_ids(pid, token)
    if date_active and fields.get("Date active"):
        gql(GQL_SETDATE, {"projectId": pid, "itemId": item_id, "fieldId": fields["Date active"], "value": date_active.strftime(ISO)}, token)
    if due_date and fields.get("Due date"):
        gql(GQL_SETDATE, {"projectId": pid, "itemId": item_id, "fieldId": fields["Due date"], "value": due_date.strftime(ISO)}, token)

# --------------------------- Task file handling ----------------------------

def expand_specs(meta: dict) -> T.List[dict]:
    """If the file defines `tasks: [ ... ]`, expand with top-level defaults."""
    if isinstance(meta.get("tasks"), list):
        defaults = {k: v for k, v in meta.items() if k != "tasks"}
        out: T.List[dict] = []
        for t in meta["tasks"]:
            c = defaults.copy()
            if isinstance(t, dict):
                c.update(t)
            out.append(c)
        return out
    return [meta]

def glob_task_files() -> T.List[str]:
    files = []
    for p in ("tasks/**/*.md", "tasks/*.md", "*.md"):
        files.extend(glob.glob(p, recursive=True))
    # keep stable order, de-dup
    return list(dict.fromkeys(sorted(files)))

# --------------------------- Parent / child ops ----------------------------

def search_parent_by_occ(repo: str, task_id: str, occ_id: T.Optional[str], token: str) -> T.Optional[dict]:
    q = f'repo:{repo} is:issue in:body "{occ_tag(task_id, occ_id)}"' if occ_id else f'repo:{repo} is:issue in:body "{family_key(task_id)}"'
    items = search_issues(repo, q, token)
    return items[0] if items else None

def search_issue_by_marker(repo: str, marker: str, token: str) -> T.Optional[dict]:
    q = f'repo:{repo} is:issue in:body "{marker}"'
    items = search_issues(repo, q, token)
    return items[0] if items else None

def ensure_parent_issue(repo: str, spec: dict, body_md: str, now: date, token: str) -> T.Tuple[dict, str]:
    task_id = str(spec["id"]).strip()
    kind, n = parse_interval(spec.get("interval"))
    anchor = parse_date(spec.get("start") or spec.get("date_active"))
    occ_id = compute_occurrence_id(kind, n, anchor, now)

    existing = search_parent_by_occ(repo, task_id, occ_id if kind != "once" else None, token)

    if not APPLY:
        if existing:
            debug(f"[UPDATE] #{existing['number']} {spec['title']} (occ={occ_id})")
            return (existing, occ_id)
        else:
            debug(f"[CREATE] {spec['title']} (occ={occ_id})")
            return ({"number": 0, "title": spec["title"], "node_id": None, "body": ""}, occ_id)

    if existing:
        issue = get_issue(repo, existing["number"], token)
        body = (issue.get("body") or "")
        mk = family_key(task_id)
        ok = occ_tag(task_id, occ_id)
        if mk not in body or ok not in body:
            body = (body.rstrip() + "\n\n" + mk + "\n" + ok + "\n").strip()
            issue = update_issue_body(repo, issue["number"], body, token)
        return issue, occ_id

    # create new
    assignees = ensure_list(spec.get("assign"))
    labels = ensure_list(spec.get("labels"))
    body = (body_md or "").strip()
    if body: body += "\n\n"
    body += family_key(task_id) + "\n" + occ_tag(task_id, occ_id) + "\n"
    issue = create_issue(repo, spec["title"], body, assignees, labels, token)
    return issue, occ_id

def ensure_child_issue(repo: str, parent_issue: dict, parent_spec: dict, parent_occ: str, sub_spec: dict, child_occ: T.Optional[str], token: str) -> dict:
    pid = str(parent_spec["id"]).strip()
    sid = str(sub_spec["id"]).strip()
    tag = child_tag(pid, parent_occ, child_occ, sid)
    found = search_issue_by_marker(repo, tag, token)

    if not APPLY:
        if found:
            debug(f"  [child UPDATE] #{found['number']} {sub_spec['title']} ({child_occ or parent_occ})")
            return found
        else:
            debug(f"  [child CREATE] {sub_spec['title']} ({child_occ or parent_occ})")
            return {"number": 0, "title": sub_spec["title"], "body": ""}
    if found:
        return get_issue(repo, found["number"], token)

    assignees = ensure_list(sub_spec.get("assign") or parent_spec.get("assign"))
    labels = ensure_list(sub_spec.get("labels") or parent_spec.get("labels"))
    body = (sub_spec.get("body") or "").strip()
    backlink = f"Parent: #{parent_issue['number']}"
    occnote = f"Occurrence: **{child_occ or parent_occ}**"
    if body:
        body = body + f"\n\n{occnote}\n\n{backlink}\n{tag}\n"
    else:
        body = f"{occnote}\n\n{backlink}\n{tag}\n"
    return create_issue(repo, sub_spec["title"], body, assignees, labels, token)

def ensure_parent_checklist_has(repo: str, parent: dict, child: dict, title: str, token: str) -> None:
    line = f"- [ ] #{child['number']} {title}".strip()
    cur = (parent.get("body") or "")
    if line in cur: return
    new_body = (cur.rstrip() + "\n\n" + line + "\n").strip() + "\n"
    if not APPLY:
        debug(f"  [parent checklist] add link to #{child.get('number', 0)}")
        return
    update_issue_body(repo, parent["number"], new_body, token)

# --------------------------- Due date helpers ------------------------------

def compute_due_date(spec: dict, now: date) -> T.Optional[date]:
    for key in ("due_date", "due"):
        if spec.get(key):
            d = parse_date(str(spec[key]))
            if d: return d
    if "due_in_days" in spec:
        try: return now + timedelta(days=int(spec["due_in_days"]))
        except Exception: pass
    return None

# --------------------------- Main -----------------------------------------

def main():
    if not GH_TOKEN:
        raise SystemExit("ERROR: GITHUB_TOKEN is required")

    files = glob_task_files()
    if not files:
        debug("No Markdown files found (looked in tasks/**/*.md, tasks/*.md, *.md)")
        return

    now = today_utc()

    for path in files:
        try:
            post = frontmatter.load(path)
        except Exception as e:
            debug(f"[SKIP] {path}: frontmatter error: {e}")
            continue

        meta = dict(post.metadata or {})
        body_md = (post.content or "")

        specs = expand_specs(meta)
        for spec in specs:
            if "id" not in spec or "title" not in spec:
                debug(f"[SKIP] {path}: require id + title")
                continue
            repo = normalized_repo(spec.get("repository")) or REPO_ENV
            if not repo:
                debug(f"[SKIP] {path}: no repository (set spec.repository or REPO env)")
                continue

            # --- Parent for THIS occurrence
            parent, parent_occ = ensure_parent_issue(repo, spec, body_md, now, GH_TOKEN)

            # --- Optional Projects v2 (best-effort; never fail core flow)
            proj_title = spec.get("project")
            if APPLY and parent.get("node_id") and PROJ_TOKEN and isinstance(proj_title, str) and proj_title.strip():
                try:
                    da = parse_date(spec.get("date_active")) or now
                    dd = compute_due_date(spec, now)
                    add_to_project_and_dates(parent["node_id"], proj_title.strip(), da, dd, PROJ_TOKEN)
                except Exception as e:
                    debug(f"[PROJECT] warn: {e}")

            # --- Children (respect window if repeating parent)
            children = list(spec.get("subtasks") or [])
            win = parent_window(parent_occ)
            should_make_children = True
            if win:
                start, end = win
                if not (start <= now <= end):
                    should_make_children = False
                    debug(f"[INFO] outside parent window {start}..{end}; skip child creation")

            created_children: T.List[dict] = []
            if should_make_children:
                for sub in children:
                    if "id" not in sub or "title" not in sub:
                        debug("  [child SKIP] needs 'id' and 'title'")
                        continue
                    cint, _ = parse_interval(sub.get("interval") or spec.get("interval"))
                    winmode = (sub.get("window") or "per_parent").strip().lower()
                    if win and winmode == "within_parent":
                        occs = enumerate_child_occs(cint, win[0], win[1])
                        for co in occs:
                            child = ensure_child_issue(repo, parent, spec, parent_occ, sub, co, GH_TOKEN)
                            ensure_parent_checklist_has(repo, parent, child, f"{sub['title']} ({co})", GH_TOKEN)
                            created_children.append(child)
                    else:
                        child = ensure_child_issue(repo, parent, spec, parent_occ, sub, parent_occ, GH_TOKEN)
                        ensure_parent_checklist_has(repo, parent, child, sub["title"], GH_TOKEN)
                        created_children.append(child)

            # --- Refresh parent body with markers (keeps original body + markers)
            fam = family_key(str(spec["id"]))
            occm = occ_tag(str(spec["id"]), parent_occ)
            body = (parent.get("body") or "").strip()
            for mk in (fam, occm):
                if mk not in body:
                    body = (body + "\n\n" + mk).strip()
            if APPLY:
                update_issue_body(repo, parent["number"], body + "\n", GH_TOKEN)
                debug(f"[UPDATE] #{parent['number']} body refreshed (occ={parent_occ})")

    debug("Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        raise SystemExit(f"FATAL: {ex}")
