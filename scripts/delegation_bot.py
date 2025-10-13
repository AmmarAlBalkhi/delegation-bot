import os
import hashlib
from datetime import date
import requests
import frontmatter

GITHUB = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_ENV = os.environ.get("REPO", "")
APPLY = os.environ.get("APPLY", "false").strip().lower() == "true"
HEADERS = {"Authorization": f"Bearer {TOKEN}",
           "Accept": "application/vnd.github+json"}

def today_iso() -> str:
    return date.today().isoformat()

def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v).strip()] if str(v).strip() else []

def as_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"true", "yes", "1", "y"}

def load_task_files():
    files = []
    for root, _, names in os.walk("tasks"):
        for n in names:
            if n.endswith(".md"):
                files.append(os.path.join(root, n))
    return sorted(files)

def load_tasks_from_file(path):
    """Return (tasks:list[dict], shared_body:str) with top-level defaults applied."""
    post = frontmatter.load(path)
    meta = post.metadata or {}
    body = post.content or ""

    # Multi-task: meta['tasks'] is a list of dicts
    if isinstance(meta.get("tasks"), list):
        defaults = {k: v for k, v in meta.items() if k != "tasks"}
        tasks = []
        for t in meta["tasks"]:
            merged = defaults.copy()
            merged.update(t or {})
            merged["_src"] = path
            tasks.append(merged)
        return tasks, body

    # Single-task: treat front-matter as a 1-item list
    single = meta.copy()
    single["_src"] = path
    return [single], body

def search_existing(repo, fp):
    """Search for issues containing our fingerprint comment; prefer an open one."""
    q = f'repo:{repo} in:body "task-fingerprint:{fp}"'
    r = requests.get(f"{GITHUB}/search/issues", headers=HEADERS, params={"q": q})
    if not r.ok:
        return None, None
    items = r.json().get("items", [])
    open_item = next((it for it in items if it.get("state") == "open"), None)
    closed_item = next((it for it in items if it.get("state") == "closed"), None)
    return open_item, closed_item

def create_issue(repo, payload):
    r = requests.post(f"{GITHUB}/repos/{repo}/issues", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def main():
    for path in load_task_files():
        tasks, body = load_tasks_from_file(path)

        for meta in tasks:
            repo = meta.get("repository") or REPO_ENV
            title = meta.get("title")
            if not (repo and title):
                print(f"[SKIP] {path}: missing repository or title")
                continue

            # date gating
            da = str(meta.get("date_active") or "").strip()
            if da and da > today_iso():
                print(f"[SKIP] {path}: date_active in future ({da})")
                continue

            labels = as_list(meta.get("labels"))
            assignees = as_list(meta.get("assign"))
            once = as_bool(meta.get("once"))

            # fingerprint (same as your current logic)
            fp_src = f"{path}::{title}"
            fp = hashlib.sha1(fp_src.encode("utf-8")).hexdigest()[:12]
            fp_comment = f"<!-- task-fingerprint:{fp} -->"

            # full issue body (shared body + info block)
            info = [f"**Task source:** `{path}`",
                    f"**Date active:** {da or 'None'}"]
            if meta.get("due_date"):
                info.append(f"**Due date:** {meta['due_date']}")
            body_full = f"{body}\n\n{fp_comment}\n\n" + "\n".join(info)

            # idempotency
            open_item, closed_item = search_existing(repo, fp)
            if open_item:
                print(f"[SKIP] {path}: issue already open (#{open_item['number']})")
                continue
            if once and closed_item:
                print(f"[SKIP] {path}: once=true and closed issue exists (#{closed_item['number']})")
                continue

            payload = {"title": title, "body": body_full}
            if labels:
                payload["labels"] = labels
            if assignees:
                payload["assignees"] = assignees

            if APPLY:
                try:
                    res = create_issue(repo, payload)
                    print(f"[CREATE] #{res['number']} {title}")
                except Exception:
                    payload.pop("assignees", None)
                    res = create_issue(repo, payload)
                    print(f"[CREATE] #{res['number']} {title} (assignees skipped)")
            else:
                print(f"[DRY-RUN] would create: {title} in {repo}")

if __name__ == "__main__":
    main()
