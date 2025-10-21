#!/usr/bin/env python3
"""
Delegation Bot — parent + real sub-issues + interval scheduling + project dates

What this script does
---------------------
1) Reads task specs from tasks/*.md (YAML front-matter + Markdown body).
2) Creates/updates a **parent** Issue per task.
3) If `subtasks:` are present, creates a **real Issue** for each subtask
   and inserts a tracked task list in the parent body that references them
   (e.g., "- [ ] #123 Title"). GitHub automatically shows the linkage.
4) Reticks the parent’s task list: when a child Issue is closed, the item
   in the parent becomes checked "- [x]".
5) Supports `interval`: "once" | "daily" | "weekly" | "monthly" | "every:N".
6) Optionally writes ProjectV2 custom dates ("Date active" / "Due date")
   using GraphQL if you provide PROJECT_TOKEN.

Required env:
-------------
- GITHUB_TOKEN  (repo-scoped; Actions' default works for same-repo writes)
Optional:
- PROJECT_TOKEN (a classic PAT with project: write) for ProjectV2 date sync.
- REPO          (owner/name). Defaults to the Actions repo if unset.
- APPLY         ("true" to create/update; otherwise dry-run)

Task schema (front-matter)
--------------------------
id: string (stable id)
repository: owner/name (optional; defaults to env REPO)
title: string
assign: <login> | [logins]
labels: [label, ...]
date_active: YYYY-MM-DD
due_date: YYYY-MM-DD              # OR
due_in: 7                         # days from creation
interval: once|daily|weekly|monthly|every:N
project: { owner: "...", title: "Delegation Bot - PoC" }   # optional
subtasks:
  - id: string
    title: string
    assign: login or [logins] (optional; falls back to parent)
    labels: [ ... ]               (optional; falls back to parent)
    due_in: N                     (optional; defaults to parent's due_in)
"""

import os
import re
import sys
import json
import glob
import time
import datetime as dt
from typing import Dict, Any, List, Tuple, Optional

import frontmatter
import requests

ISO_DATE = "%Y-%m-%d"
SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})

# ---------- Helpers -----------------------------------------------------------

def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    return v if v not in ("", None) else default

def today_utc_date() -> dt.date:
    return dt.datetime.utcnow().date()

def parse_date(s: Optional[str]) -> Optional[dt.date]:
    if not s:
        return None
    return dt.datetime.strptime(str(s), ISO_DATE).date()

def parse_interval(s: Optional[str]) -> Tuple[str, Optional[int]]:
    """
    Returns (kind, n) where kind in {"once","daily","weekly","monthly","every"}
    and n is only used for "every".
    """
    if not s:
        return ("once", None)
    s = s.strip().lower()
    if s in ("once", "daily", "weekly", "monthly"):
        return (s, None)
    m = re.match(r"every\:(\d+)", s)
    if m:
        return ("every", int(m.group(1)))
    return ("once", None)

def gh_rest(method: str, url: str, token: str, **kw) -> requests.Response:
    h = kw.pop("headers", {})
    h["Authorization"] = f"Bearer {token}"
    return SESSION.request(method, url, headers=h, **kw)

def gh_graphql(query: str, variables: Dict[str, Any], token: str) -> Dict[str, Any]:
    r = gh_rest("POST", "https://api.github.com/graphql", token,
                json={"query": query, "variables": variables})
    if r.status_code >= 300:
        raise RuntimeError(f"GraphQL HTTP {r.status_code}: {r.text}")
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]

def ensure_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]

def normalized_repo(repo: Optional[str]) -> str:
    if repo:
        return repo
    return getenv("REPO") or getenv("GITHUB_REPOSITORY") or ""

def debug(msg: str):
    print(msg, flush=True)

# ---------- Fingerprints & body stitching ------------------------------------

def make_fingerprint(task_id: str) -> str:
    return f"<!-- delegation-fingerprint:{task_id} -->"

def make_sub_fingerprint(parent_id: str, sub_id: str) -> str:
    return f"<!-- delegation-sub:{parent_id}:{sub_id} -->"

def splice_section(body: str, heading: str, content: str) -> str:
    """
    Ensure a '### heading' section exists exactly once with content below it.
    """
    pattern = re.compile(rf"(?ms)^### {re.escape(heading)}\s*\n.*?(?=^### |\Z)")
    block = f"### {heading}\n{content}\n"
    if pattern.search(body):
        return pattern.sub(block, body)
    if body.endswith("\n") is False:
        body += "\n"
    return body + "\n" + block

def render_parent_body(original_md: str,
                       parent_fp: str,
                       subtasks: List[Tuple[int, str]]) -> str:
    """
    Build the parent body: original markdown + fingerprint + Subtasks section.
    subtasks: list of (issue_number, title)
    """
    lines = []
    lines.append(original_md.strip())
    lines.append("")
    lines.append(parent_fp)
    if subtasks:
        items = "\n".join([f"- [ ] #{num} {title}" for num, title in subtasks])
        body = "\n".join(lines)
        return splice_section(body, "Subtasks", items)
    else:
        return "\n".join(lines).strip() + "\n"

def retick_checklist(body: str, token: str, repo: str) -> str:
    """
    If a line contains "- [ ] #123 ..." or "- [x] #123 ...", tick based on child state.
    """
    def child_state(num: int) -> str:
        r = gh_rest("GET", f"https://api.github.com/repos/{repo}/issues/{num}",
                    token)
        r.raise_for_status()
        return r.json()["state"]  # "open" or "closed"

    changed = False
    new_lines = []
    for line in body.splitlines():
        m = re.match(r"^-\s*\[( |x)\]\s*#(\d+)\b(.*)$", line.strip())
        if m:
            cur = m.group(1)
            num = int(m.group(2))
            rest = m.group(3)
            st = child_state(num)
            want = "x" if st == "closed" else " "
            if want != cur:
                changed = True
                new_lines.append(f"- [{want}] #{num}{rest}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    if changed:
        debug("[UPDATE] reticked checklist based on child issues")
    return "\n".join(new_lines)

# ---------- ProjectV2 date helpers (optional) ---------------------------------

GQL_FIND_PROJECT = """
query($owner:String!, $title:String!) {
  user(login:$owner) { projectsV2(first: 20, query:$title) { nodes { id title } } }
  organization(login:$owner) { projectsV2(first: 20, query:$title) { nodes { id title } } }
}
"""

GQL_ADD_ITEM = """
mutation($projectId:ID!, $contentId:ID!) {
  addProjectV2ItemById(input:{projectId:$projectId, contentId:$contentId}) { item { id } }
}
"""

GQL_FIELDS = """
query($projectId:ID!) {
  node(id:$projectId) {
    ... on ProjectV2 {
      fields(first:50) { nodes { ... on ProjectV2Field { id name dataType } } }
    }
  }
}
"""

GQL_WRITE_DATE = """
mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $val:Date!) {
  updateProjectV2ItemFieldValue(input:{
    projectId:$projectId, itemId:$itemId,
    fieldId:$fieldId, value:{ date:$val }
  }) { projectV2Item { id } }
}
"""

def find_user_or_org_project(owner: str, title: str, token: str) -> Optional[str]:
    data = gh_graphql(GQL_FIND_PROJECT, {"owner": owner, "title": title}, token)
    for k in ("user", "organization"):
        node = data.get(k)
        if node and node["projectsV2"]["nodes"]:
            for p in node["projectsV2"]["nodes"]:
                if p["title"].lower() == title.lower():
                    return p["id"]
    return None

def set_project_dates(repo: str, issue_num: int,
                      date_active: Optional[dt.date],
                      due_date: Optional[dt.date],
                      project_spec: Dict[str, Any],
                      token: str):
    """
    Best-effort: add to project, then set Date active / Due date if fields exist.
    """
    if not project_spec:
        return

    owner = repo.split("/")[0]
    project_id = find_user_or_org_project(project_spec.get("owner", owner),
                                          project_spec["title"], token)
    if not project_id:
        debug("[PROJECT] No matching project found; skipping")
        return

    # get Issue node id
    r = gh_rest("GET", f"https://api.github.com/repos/{repo}/issues/{issue_num}", token)
    r.raise_for_status()
    content_node_id = r.json()["node_id"]

    # add item
    try:
        data = gh_graphql(GQL_ADD_ITEM, {"projectId": project_id, "contentId": content_node_id}, token)
        item_id = data["addProjectV2ItemById"]["item"]["id"]
    except Exception as e:
        # Item might already be there; try to discover item id by listing is overkill—skip.
        debug(f"[PROJECT] add item warning: {e}; continuing")
        item_id = None

    # fetch fields
    fields = gh_graphql(GQL_FIELDS, {"projectId": project_id}, token)["node"]["fields"]["nodes"]
    field_map = {f["name"]: f for f in fields if f["dataType"] == "DATE"}

    def write(field_name: str, val: Optional[dt.date]):
        if not item_id or not val:
            return
        fld = field_map.get(field_name)
        if not fld:
            return
        gh_graphql(GQL_WRITE_DATE, {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": fld["id"],
            "val": val.strftime(ISO_DATE),
        }, token)
        debug(f"[PROJECT] {field_name} set => {val.strftime(ISO_DATE)}")

    write("Date active", date_active)
    write("Due date", due_date)

# ---------- Core issue operations ---------------------------------------------

def find_existing_issue_by_fp(repo: str, fp: str, token: str) -> Optional[Dict[str, Any]]:
    q = f'repo:{repo} in:body "{fp}"'
    r = gh_rest("GET", f"https://api.github.com/search/issues?q={requests.utils.quote(q)}", token)
    r.raise_for_status()
    items = r.json().get("items", [])
    return items[0] if items else None

def create_issue(repo: str, title: str, body: str,
                 assignees: List[str], labels: List[str],
                 token: str) -> Dict[str, Any]:
    payload = {"title": title, "body": body}
    if assignees:
        payload["assignees"] = assignees
    if labels:
        payload["labels"] = labels
    r = gh_rest("POST", f"https://api.github.com/repos/{repo}/issues", token, json=payload)
    r.raise_for_status()
    return r.json()

def update_issue(repo: str, number: int, body: Optional[str],
                 title: Optional[str], assignees: Optional[List[str]],
                 labels: Optional[List[str]], token: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if body is not None:
        payload["body"] = body
    if title is not None:
        payload["title"] = title
    if assignees is not None:
        payload["assignees"] = assignees
    if labels is not None:
        payload["labels"] = labels
    r = gh_rest("PATCH", f"https://api.github.com/repos/{repo}/issues/{number}", token, json=payload)
    r.raise_for_status()
    return r.json()

def ensure_parent_issue(repo: str, spec: Dict[str, Any], md_body: str,
                        token: str) -> Tuple[Dict[str, Any], bool]:
    """
    Create/update parent issue with fingerprint. Returns (issue, created_flag).
    """
    task_id = spec["id"]
    fp = make_fingerprint(task_id)
    assignees = ensure_list(spec.get("assign"))
    labels = ensure_list(spec.get("labels"))
    title = spec["title"]

    # First attempt to find an existing issue via fingerprint
    existing = find_existing_issue_by_fp(repo, fp, token)

    if existing:
        number = existing["number"]
        # Retain current body (we will rebuild later including subtasks)
        r = gh_rest("GET", f"https://api.github.com/repos/{repo}/issues/{number}", token)
        r.raise_for_status()
        issue = r.json()
        return issue, False
    else:
        body = f"{md_body.strip()}\n\n{fp}\n"
        issue = create_issue(repo, title, body, assignees, labels, token)
        debug(f"[CREATE] #{issue['number']} {title}")
        return issue, True

def ensure_child_issues(parent: Dict[str, Any], repo: str,
                        spec: Dict[str, Any], token: str) -> List[Tuple[int, str]]:
    """
    For each entry in subtasks, create a real Issue once (by sub-fingerprint).
    Returns list of (issue_number, title).
    """
    sub_specs = spec.get("subtasks") or []
    if not sub_specs:
        return []

    results = []
    parent_id = spec["id"]
    parent_labels = ensure_list(spec.get("labels"))
    parent_assign = ensure_list(spec.get("assign"))
    default_due_in = spec.get("due_in")

    for s in sub_specs:
        sub_id = s["id"]
        sub_fp = make_sub_fingerprint(parent_id, sub_id)
        sub_title = s["title"]
        sub_assignees = ensure_list(s.get("assign") or parent_assign)
        sub_labels = ensure_list(s.get("labels") or parent_labels)
        sub_due_in = s.get("due_in", default_due_in)
        sub_body = f"{sub_title}\n\n{sub_fp}\n"

        existing = find_existing_issue_by_fp(repo, sub_fp, token)
        if existing:
            number = existing["number"]
            results.append((number, sub_title))
            continue

        child = create_issue(repo, sub_title, sub_body, sub_assignees, sub_labels, token)
        number = child["number"]

        # set due date if due_in present
        if isinstance(sub_due_in, int) and sub_due_in > 0:
            due_date = today_utc_date() + dt.timedelta(days=sub_due_in)
            gh_rest("PATCH", f"https://api.github.com/repos/{repo}/issues/{number}",
                    token, json={"due_on": due_date.strftime("%Y-%m-%dT00:00:00Z")})
        debug(f"[CREATE] sub-issue #{number} {sub_title}")
        results.append((number, sub_title))

    return results

def parent_body_with_subtasks(parent_issue: Dict[str, Any], spec: Dict[str, Any],
                              md_body: str, subtasks: List[Tuple[int, str]]) -> str:
    fp = make_fingerprint(spec["id"])
    return render_parent_body(md_body, fp, subtasks)

# ---------- Scheduling logic --------------------------------------------------

def should_create_now(spec: Dict[str, Any], repo: str, token: str) -> bool:
    """
    Decide whether to (re)create based on interval and open/closed state.
    Strategy:
      - if interval == once: create if no issue with fingerprint exists.
      - else (recurring): if an OPEN issue with fp exists -> skip
                          else if date_active <= today -> create new
    """
    task_id = spec["id"]
    fp = make_fingerprint(task_id)
    interval_kind, _ = parse_interval(spec.get("interval", "once"))
    existing = find_existing_issue_by_fp(repo, fp, token)

    if interval_kind == "once":
        return existing is None

    # recurring
    if existing:
        # If the existing is open, skip. If it's closed, a new one may be created.
        r = gh_rest("GET",
                    f"https://api.github.com/repos/{repo}/issues/{existing['number']}",
                    token)
        r.raise_for_status()
        if r.json()["state"] == "open":
            return False

    date_active = parse_date(spec.get("date_active"))
    return date_active is None or date_active <= today_utc_date()

def compute_due_date(spec: Dict[str, Any]) -> Optional[dt.date]:
    if spec.get("due_date"):
        return parse_date(spec["due_date"])
    if isinstance(spec.get("due_in"), int) and spec["due_in"] > 0:
        return today_utc_date() + dt.timedelta(days=int(spec["due_in"]))
    return None

# ---------- Main --------------------------------------------------------------

def main():
    APPLY = (getenv("APPLY", "false").lower() == "true")
    GH_TOKEN = getenv("GITHUB_TOKEN")
    if not GH_TOKEN:
        print("GITHUB_TOKEN missing", file=sys.stderr)
        sys.exit(1)

    PROJ_TOKEN = getenv("PROJECT_TOKEN") or GH_TOKEN  # fallback to GH_TOKEN
    repo_env = normalized_repo(None)

    files = sorted(glob.glob("tasks/*.md"))
    if not files:
        debug("[INFO] No task files found")
        return

    for path in files:
        post = frontmatter.load(path)
        spec = dict(post.metadata)
        md_body = (post.content or "").strip()
        repo = normalized_repo(spec.get("repository")) or repo_env
        if not repo:
            debug(f"[SKIP] {path}: no repository set")
            continue

        # Schedule decision
        if not should_create_now(spec, repo, GH_TOKEN):
            debug(f"[SKIP] {path}: interval/date says not now")
            continue

        if not APPLY:
            debug(f"[DRY-RUN][CREATE] {spec['title']} in {repo}")
            # show intended subtasks
            for s in ensure_list(spec.get("subtasks")):
                debug(f"[DRY-RUN]  └ sub: {s['title']}")
            continue

        # Ensure parent
        parent_issue, created = ensure_parent_issue(repo, spec, md_body, GH_TOKEN)

        # Ensure children
        child_pairs = ensure_child_issues(parent_issue, repo, spec, GH_TOKEN)

        # Build & write the parent body (with subtasks)
        parent_number = parent_issue["number"]
        new_body = parent_body_with_subtasks(parent_issue, spec, md_body, child_pairs)
        # Retick based on child state
        new_body = retick_checklist(new_body, GH_TOKEN, repo)

        update_issue(repo, parent_number, new_body, None, None, None, GH_TOKEN)
        if created:
            debug(f"[UPDATE] #{parent_number} body -> added subtasks & fingerprint")
        else:
            debug(f"[UPDATE] #{parent_number} body -> refreshed")

        # Dates (repository issues due_on is only in projects/milestones; do project fields instead)
        date_active = parse_date(spec.get("date_active"))
        due_date = compute_due_date(spec)
        if spec.get("project"):
            try:
                set_project_dates(repo, parent_number, date_active, due_date, spec["project"], PROJ_TOKEN)
            except Exception as e:
                debug(f"[PROJECT] date write warning: {e}")

    debug("[DONE]")


if __name__ == "__main__":
    main()
