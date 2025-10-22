#!/usr/bin/env python3
"""
Delegation Bot — Intervals + occurrence-aware sub-issues (incl. per-subtask intervals)

Fixes vs v9:
- Hard guarantee that a parent for *this* occurrence exists before creating children.
- Each child body includes an explicit "Parent: #<number>" backlink (plus hidden markers),
  so GitHub shows a first-class issue reference both ways.

Features
--------
- Parent intervals: once | daily | weekly | monthly | every:N
- Subtasks can override interval (e.g., monthly parent with weekly/daily children)
- One OPEN parent per "task family"; one parent per period (occurrence)
- Child issues are REAL GitHub issues; parent shows a tracked list (- [ ] #123 Title)
- Parent checklist auto-reticks from child issue state on each run
- ProjectV2 dates ("Date active", "Due date") written if PROJECT_TOKEN + project spec

Env
---
GITHUB_TOKEN  (required; Actions default ok for issues)
PROJECT_TOKEN (optional PAT with project scope; falls back to GITHUB_TOKEN)
REPO          (optional owner/name; defaults to current repo)
APPLY         ("true" to perform writes; anything else is dry-run)
"""

import os, re, sys, glob, datetime as dt
from typing import Dict, Any, List, Tuple, Optional

import requests
import frontmatter

REST = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
ISO = "%Y-%m-%d"

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})

# ---------------- small utils ----------------

def getenv(name, default=None):
    v = os.getenv(name, default)
    return v if v not in ("", None) else default

def today() -> dt.date:
    return dt.date.today()

def parse_date(s: Optional[str]) -> Optional[dt.date]:
    if not s: return None
    return dt.datetime.strptime(str(s), ISO).date()

def ensure_list(x):
    if x is None: return []
    return x if isinstance(x, list) else [x]

def debug(msg: str):
    print(msg, flush=True)

def normalized_repo(repo_opt: Optional[str]) -> str:
    if repo_opt: return repo_opt
    return getenv("REPO") or getenv("GITHUB_REPOSITORY") or ""

# ---------------- GitHub helpers ----------------

def gh_rest(method, url, token, **kw):
    h = kw.pop("headers", {})
    h["Authorization"] = f"Bearer {token}"
    return SESSION.request(method, url, headers=h, **kw)

def gh_gql(query: str, variables: Dict[str, Any], token: str) -> Dict[str, Any]:
    r = gh_rest("POST", GRAPHQL, token, json={"query": query, "variables": variables})
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]

def search_issues(repo: str, q: str, token: str):
    r = gh_rest("GET", f"{REST}/search/issues", token, params={"q": q})
    r.raise_for_status()
    return r.json().get("items", [])

def get_issue(repo: str, number: int, token: str) -> Dict[str, Any]:
    r = gh_rest("GET", f"{REST}/repos/{repo}/issues/{number}", token)
    r.raise_for_status()
    return r.json()

def create_issue(repo: str, title: str, body: str, assignees: List[str], labels: List[str], token: str) -> Dict[str, Any]:
    payload = {"title": title, "body": body}
    if assignees: payload["assignees"] = assignees
    if labels: payload["labels"] = labels
    r = gh_rest("POST", f"{REST}/repos/{repo}/issues", token, json=payload)
    r.raise_for_status()
    return r.json()

def update_issue(repo: str, number: int, fields: Dict[str, Any], token: str) -> Dict[str, Any]:
    r = gh_rest("PATCH", f"{REST}/repos/{repo}/issues/{number}", token, json=fields)
    r.raise_for_status()
    return r.json()

# ---------------- Markers (family key / occurrence / child) ----------------

def family_key(task_id: str) -> str:
    return f"<!-- delegation-key:{task_id} -->"

def occ_tag(task_id: str, occ_id: str) -> str:
    return f"<!-- delegation-occ:{task_id}:{occ_id} -->"

def sub_marker(parent_id: str,
               parent_occ: Optional[str],
               sub_occ: Optional[str],
               sub_id: str) -> str:
    """
    Occurrence-aware child identity:
      <!-- delegation-sub:{parent_id}:{parent_occ}:{sub_occ}:{sub_id} -->
    Missing parent_occ or sub_occ are omitted, but order is preserved.
    """
    parts = [parent_id]
    if parent_occ: parts.append(parent_occ)
    if sub_occ: parts.append(sub_occ)
    parts.append(sub_id)
    return f"<!-- delegation-sub:{':'.join(parts)} -->"

# ---------------- Interval logic ----------------

def parse_interval(s: Optional[str]):
    """
    Returns (kind, n) where kind in {"once","daily","weekly","monthly","every"}
    and n is only used for "every".
    """
    if not s: return ("once", None)
    s = str(s).strip().lower()
    if s in {"once","daily","weekly","monthly"}: return (s, None)
    m = re.match(r"every:(\d+)", s)
    if m: return ("every", int(m.group(1)))
    return ("once", None)

def compute_occurrence_id(kind: str, n: Optional[int], base: Optional[dt.date], now: dt.date) -> Optional[str]:
    """
    Period id:
      daily   -> YYYY-MM-DD
      weekly  -> YYYY-Www  (ISO week)
      monthly -> YYYY-MM
      every:N -> start date of current N-day bucket (base=base or today)
      once    -> None
    """
    if kind == "once": return None
    if kind == "daily": return now.strftime(ISO)
    if kind == "weekly":
        y, w, _ = now.isocalendar()
        return f"{y}-W{w:02d}"
    if kind == "monthly": return f"{now.year:04d}-{now.month:02d}"
    if kind == "every" and n and n > 0:
        base = base or now
        if now < base: return base.strftime(ISO)
        delta = (now - base).days
        start = base + dt.timedelta(days=(delta // n) * n)
        return start.strftime(ISO)
    return None

def find_open_parent_by_family(repo: str, task_id: str, token: str):
    q = f'repo:{repo} is:issue is:open in:body "{family_key(task_id)}"'
    items = search_issues(repo, q, token)
    return items[0] if items else None

def any_parent_exists(repo: str, task_id: str, token: str):
    q = f'repo:{repo} is:issue in:body "{family_key(task_id)}"'
    items = search_issues(repo, q, token)
    return len(items) > 0

def occurrence_exists(repo: str, task_id: str, occ_id: str, token: str):
    q = f'repo:{repo} is:issue in:body "{occ_tag(task_id, occ_id)}"'
    items = search_issues(repo, q, token)
    return len(items) > 0

def should_create_parent_now(repo: str, spec: Dict[str, Any], token: str) -> Tuple[bool, Optional[str]]:
    tid = spec["id"]
    parent_kind, parent_n = parse_interval(spec.get("interval"))
    da = parse_date(spec.get("date_active"))
    now = today()

    if da and now < da:
        return (False, None)

    if find_open_parent_by_family(repo, tid, token):
        return (False, None)

    if parent_kind == "once":
        return (False, None) if any_parent_exists(repo, tid, token) else (True, None)

    # recurring
    parent_occ = compute_occurrence_id(parent_kind, parent_n, da, now)
    if not parent_occ: return (False, None)
    return (False, parent_occ) if occurrence_exists(repo, tid, parent_occ, token) else (True, parent_occ)

# ---------------- ProjectV2 date writing (best-effort) ----------------

GQL_FIND_USER_PROJECT = """
query($login:String!, $title:String!){
  user(login:$login){
    projectsV2(first:50, query:$title){ nodes{ id title } }
  }
}"""

GQL_FIND_ORG_PROJECT = """
query($login:String!, $title:String!){
  organization(login:$login){
    projectsV2(first:50, query:$title){ nodes{ id title } }
  }
}"""

GQL_ADD_ITEM = """
mutation($pid:ID!,$cid:ID!){
  addProjectV2ItemById(input:{projectId:$pid, contentId:$cid}){ item{ id } }
}"""

GQL_FIELDS = """
query($pid:ID!){
  node(id:$pid){
    ... on ProjectV2{ fields(first:100){ nodes{ ... on ProjectV2Field{ id name dataType } } } }
  }
}"""

GQL_SET_DATE = """
mutation($pid:ID!,$iid:ID!,$fid:ID!,$val:Date!){
  updateProjectV2ItemFieldValue(input:{
    projectId:$pid, itemId:$iid, fieldId:$fid, value:{ date:$val }
  }){ projectV2Item{ id } }
}"""

def find_project_id(owner_login: str, title: str, token: str) -> Optional[str]:
    # Try USER scope
    try:
        data = gh_gql(GQL_FIND_USER_PROJECT, {"login": owner_login, "title": title}, token)
        nodes = (data.get("user") or {}).get("projectsV2", {}).get("nodes", []) or []
        for p in nodes:
            if p["title"].lower() == title.lower():
                return p["id"]
    except Exception:
        pass
    # Try ORG scope
    try:
        data = gh_gql(GQL_FIND_ORG_PROJECT, {"login": owner_login, "title": title}, token)
        nodes = (data.get("organization") or {}).get("projectsV2", {}).get("nodes", []) or []
        for p in nodes:
            if p["title"].lower() == title.lower():
                return p["id"]
    except Exception:
        pass
    return None

def write_project_dates(repo: str, issue_num: int,
                        date_active: Optional[dt.date],
                        due_date: Optional[dt.date],
                        project: Optional[Dict[str, Any]],
                        token: str):
    if not project:
        return
    owner_default = repo.split("/")[0]
    pid = find_project_id(project.get("owner", owner_default), project["title"], token)
    if not pid:
        debug("[PROJECT] Not found; skip")
        return

    issue = get_issue(repo, issue_num, token)
    content_id = issue["node_id"]

    # Ensure project item exists
    try:
        gh_gql(GQL_ADD_ITEM, {"pid": pid, "cid": content_id}, token)
    except Exception as e:
        debug(f"[PROJECT] add warn: {e}")

    # Resolve the item id on that project
    q_items = """query($iid:ID!){ node(id:$iid){ ... on Issue {
        projectItems(first:50){ nodes{ id project{ id title } } }
    }}}"""
    try:
        items = gh_gql(q_items, {"iid": content_id}, token)["node"]["projectItems"]["nodes"]
    except Exception as e:
        debug(f"[PROJECT] item lookup warn: {e}")
        items = []

    item_id = None
    for it in items:
        if it["project"]["id"] == pid:
            item_id = it["id"]; break
    if not item_id:
        debug("[PROJECT] no item id; skip date writes")
        return

    # Fetch date fields and write values
    try:
        fields = gh_gql(GQL_FIELDS, {"pid": pid}, token)["node"]["fields"]["nodes"]
    except Exception as e:
        debug(f"[PROJECT] fields warn: {e}")
        fields = []
    f_map = {f["name"]: f for f in fields if f.get("dataType") == "DATE"}

    def set_date(name, d: Optional[dt.date]):
        if not d or name not in f_map: return
        gh_gql(GQL_SET_DATE, {"pid": pid, "iid": item_id, "fid": f_map[name]["id"], "val": d.strftime(ISO)}, token)
        debug(f"[PROJECT] {name} set => {d.strftime(ISO)}")

    set_date("Date active", date_active)
    set_date("Due date",   due_date)

# ---------------- Parent body (Subtasks section + retick) ----------------

SUBSECTION_RE = re.compile(r"(?ms)^### Subtasks\s*\n.*?(?=^### |\Z)")

def render_parent_body(orig_md: str,
                       family_marker: str,
                       occ_marker: Optional[str],
                       child_pairs: List[Tuple[int, str]]) -> str:
    base = (orig_md or "").strip()
    marks = [family_marker]
    if occ_marker: marks.append(occ_marker)
    base = (base + "\n\n" + "\n".join(marks)).strip() + "\n"
    if child_pairs:
        lines = "\n".join([f"- [ ] #{n} {t}" for n, t in child_pairs])
        block = f"### Subtasks\n{lines}\n"
        if SUBSECTION_RE.search(base):
            return SUBSECTION_RE.sub(block, base)
        return base + "\n" + block
    return base

def retick_from_children(body: str, repo: str, token: str) -> str:
    changed = False
    out = []
    for line in (body or "").splitlines():
        m = re.match(r"^-\s*\[( |x)\]\s*#(\d+)\b(.*)$", line.strip())
        if not m:
            out.append(line); continue
        cur = m.group(1); num = int(m.group(2)); rest = m.group(3)
        st = get_issue(repo, num, token)["state"]
        want = "x" if st == "closed" else " "
        if want != cur:
            changed = True
            out.append(f"- [{want}] #{num}{rest}")
        else:
            out.append(line)
    if changed:
        debug("[UPDATE] reticked checklist from child states")
    return "\n".join(out)

# ---------------- Child issues (occurrence-aware, incl. per-subtask interval) ----------------

def search_children_for_parent_occ(repo: str, parent_id: str, parent_occ: Optional[str], token: str):
    """
    Return all child issues for the current parent occurrence by prefix search.
    """
    if parent_occ:
        prefix = f'<!-- delegation-sub:{parent_id}:{parent_occ}:'
    else:
        prefix = f'<!-- delegation-sub:{parent_id}:'
    q = f'repo:{repo} in:body "{prefix}'
    items = search_issues(repo, q, token)
    pairs = []
    for it in items:
        pairs.append((it["number"], it.get("title","")))
    pairs.sort(key=lambda x: x[0])
    return pairs

def ensure_subissues(repo: str,
                     parent_issue_num: int,
                     parent_id: str,
                     parent_occ: Optional[str],
                     parent_date_active: Optional[dt.date],
                     parent_labels: List[str],
                     parent_assign: List[str],
                     subspecs: List[Dict[str, Any]],
                     token: str) -> List[Tuple[int, str]]:
    """
    For each subtask spec:
      - compute its own occurrence (from its 'interval', default 'once')
      - create child for *this* parent occurrence + *this* sub-occurrence, if missing
      - decorate child title with [<sub_occ>] for clarity
      - include a visible backlink 'Parent: #<parent_issue_num>' in the child body
    Then return ALL child issues belonging to this parent occurrence.
    """
    now = today()
    for s in subspecs or []:
        sid   = s["id"]
        title = s["title"]
        skind, sn = parse_interval(s.get("interval"))  # per-subtask interval (default once)
        sub_occ = compute_occurrence_id(skind, sn, parent_date_active, now)
        fp = sub_marker(parent_id, parent_occ, sub_occ, sid)
        q = f'repo:{repo} in:body "{fp}"'
        items = search_issues(repo, q, token)
        if items:
            continue
        labels    = ensure_list(s.get("labels") or parent_labels)
        assignees = ensure_list(s.get("assign")  or parent_assign)
        final_title = f"{title} [{sub_occ}]" if sub_occ else title
        # ---- backlink to parent + hidden marker
        body = f"Parent: #{parent_issue_num}\n\n{final_title}\n\n{fp}\n"
        child = create_issue(repo, final_title, body, assignees, labels, token)
        debug(f"[CREATE] sub-issue #{child['number']} {final_title}")

    # After ensuring children exist for this occurrence, list *all* children for this parent occurrence
    return search_children_for_parent_occ(repo, parent_id, parent_occ, token)

# ---------------- Due date (explicit only) ----------------

def compute_due_date(spec: Dict[str, Any]) -> Optional[dt.date]:
    return parse_date(spec.get("due_date"))

# ---------------- Main ----------------

def main():
    APPLY = (getenv("APPLY", "false").lower() == "true")
    GH_TOKEN = getenv("GITHUB_TOKEN")
    if not GH_TOKEN:
        print("GITHUB_TOKEN missing", file=sys.stderr); sys.exit(1)
    PROJ_TOKEN = getenv("PROJECT_TOKEN") or GH_TOKEN
    repo_env = normalized_repo(None)

    files = sorted(glob.glob("tasks/*.md"))
    if not files:
        debug("[INFO] No tasks/*.md found"); return

    for path in files:
        post = frontmatter.load(path)
        spec = dict(post.metadata or {})
        body_md = (post.content or "")
        repo = normalized_repo(spec.get("repository")) or repo_env
        if not repo:
            debug(f"[SKIP] {path}: no repository"); continue
        if "id" not in spec or "title" not in spec:
            debug(f"[SKIP] {path}: require id + title"); continue

        # schedule
        create_new, parent_occ = should_create_parent_now(repo, spec, GH_TOKEN)
        open_parent = find_open_parent_by_family(repo, spec["id"], GH_TOKEN)

        if not APPLY:
            if create_new:
                debug(f"[DRY-RUN][CREATE] {spec['title']} (occ={parent_occ or '-'})")
            elif open_parent:
                debug(f"[DRY-RUN][UPDATE] #{open_parent['number']} {spec['title']}")
            else:
                debug(f"[DRY-RUN][SKIP] {spec['title']}")
            continue

        # ---- Hard guarantee: obtain a parent issue for THIS occurrence
        parent_issue = None
        if open_parent:
            parent_issue = get_issue(repo, open_parent["number"], GH_TOKEN)
        elif create_new:
            marks = [family_key(spec["id"])]
            if parent_occ: marks.append(occ_tag(spec["id"], parent_occ))
            initial_body = (body_md or "").strip() + "\n\n" + "\n".join(marks) + "\n"
            parent_issue = create_issue(
                repo,
                spec["title"],
                initial_body,
                ensure_list(spec.get("assign")),
                ensure_list(spec.get("labels")),
                GH_TOKEN
            )
            debug(f"[CREATE] #{parent_issue['number']} {spec['title']}")
        else:
            # No open parent and not scheduled to create a new one => skip everything
            debug(f"[SKIP] {spec['title']}: no open parent and this occurrence already exists")
            continue

        # Ensure sub-issues (occurrence-aware; per-subtask interval)
        child_pairs = ensure_subissues(
            repo=repo,
            parent_issue_num=parent_issue["number"],
            parent_id=spec["id"],
            parent_occ=parent_occ,
            parent_date_active=parse_date(spec.get("date_active")),
            parent_labels=ensure_list(spec.get("labels")),
            parent_assign=ensure_list(spec.get("assign")),
            subspecs=spec.get("subtasks") or [],
            token=GH_TOKEN
        )

        # Parent body + retick
        fam = family_key(spec["id"])
        occ = occ_tag(spec["id"], parent_occ) if parent_occ else None
        new_body = render_parent_body(body_md, fam, occ, child_pairs)
        new_body = retick_from_children(new_body, repo, GH_TOKEN)
        update_issue(repo, parent_issue["number"], {"body": new_body}, GH_TOKEN)
        debug(f"[UPDATE] #{parent_issue['number']} body refreshed")

        # Project dates
        da = parse_date(spec.get("date_active"))
        dd = compute_due_date(spec)
        if spec.get("project"):
            try:
                write_project_dates(repo, parent_issue["number"], da, dd, spec["project"], PROJ_TOKEN)
            except Exception as e:
                debug(f"[PROJECT] warn: {e}")

    debug("[DONE]")

if __name__ == "__main__":
    main()
