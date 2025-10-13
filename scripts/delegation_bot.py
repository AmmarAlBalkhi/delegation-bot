import os, re, hashlib
from datetime import date
import requests
import frontmatter
from pathlib import Path

GITHUB = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_ENV = os.environ.get("REPO", "")
APPLY = os.environ.get("APPLY", "false").strip().lower() == "true"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ---------- helpers ----------
def today_iso() -> str:
    return date.today().isoformat()

def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    return [s] if s else []

def as_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"true", "1", "yes", "y"}

def slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "task"

def posix_rel(path: str) -> str:
    return Path(path).as_posix()

# ---------- task loading ----------
def load_task_files():
    files = []
    for root, _, names in os.walk("tasks"):
        for n in names:
            if n.endswith(".md"):
                files.append(os.path.join(root, n))
    return sorted(files)

def load_tasks_from_file(path):
    """Return (tasks:list[dict], shared_body:str) with top-level defaults applied.
       Supports single-task (front-matter is the task) and multi-task (tasks:[...])."""
    post = frontmatter.load(path)
    meta = post.metadata or {}
    body = post.content or ""
    # multi
    if isinstance(meta.get("tasks"), list):
        defaults = {k: v for k, v in meta.items() if k != "tasks"}
        tasks = []
        for t in meta["tasks"]:
            merged = defaults.copy()
            merged.update(t or {})
            merged["_src"] = path
            tasks.append(merged)
        return tasks, body
    # single
    single = meta.copy()
    single["_src"] = path
    return [single], body

# ---------- fingerprint (thesis spec) ----------
def compute_fpr(repo: str, src: str, key: str, occ: str) -> str:
    base = f"{repo}|{src}|{key}|{occ}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def fpr_comment(fpr: str, src: str, key: str, occ: str) -> str:
    return f"<!-- 🔑 delegation-bot:fpr=sha256:{fpr}; src={src}; key={key}; occ={occ} -->"

def search_by_fpr(repo: str, fpr: str):
    """Find issues containing our 🔑 fingerprint. Prefer open."""
    q = f'repo:{repo} in:body "delegation-bot:fpr=sha256:{fpr}"'
    r = requests.get(f"{GITHUB}/search/issues", headers=HEADERS, params={"q": q})
    if not r.ok:
        return None, None
    items = r.json().get("items", [])
    open_item = next((it for it in items if it.get("state") == "open"), None)
    closed_item = next((it for it in items if it.get("state") == "closed"), None)
    return open_item, closed_item

def update_issue(repo: str, number: int, payload: dict):
    r = requests.patch(f"{GITHUB}/repos/{repo}/issues/{number}", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def create_issue(repo: str, payload: dict):
    r = requests.post(f"{GITHUB}/repos/{repo}/issues", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

# ---------- main ----------
def main():
    for path in load_task_files():
        tasks, body = load_tasks_from_file(path)

        for t in tasks:
            repo = t.get("repository") or REPO_ENV
            title = t.get("title")
            if not (repo and title):
                print(f"[SKIP] {path}: missing repository or title")
                continue

            # date gating
            da = str(t.get("date_active") or "").strip()
            if da and da > today_iso():
                print(f"[SKIP] {path}: date_active in future ({da})")
                continue

            labels = as_list(t.get("labels"))
            assignees = as_list(t.get("assign"))
            once = as_bool(t.get("once"))

            src = posix_rel(t.get("_src", path))
            key = t.get("id") or slug(title)
            occ = "" if once else (da or "")
            fpr = compute_fpr(repo, src, key, occ)
            marker = fpr_comment(fpr, src, key, occ)

            # body (shared body + info)
            info = [f"**Task source:** `{src}`", f"**Date active:** {da or 'None'}"]
            if t.get("due_date"):
                info.append(f"**Due date:** {t['due_date']}")
            body_full = f"{body}\n\n{marker}\n\n" + "\n".join(info)

            # idempotency
            open_item, closed_item = search_by_fpr(repo, fpr)
            if open_item:
                # Update the existing open issue to reflect latest fields/body
                payload = {"title": title, "body": body_full}
                if labels: payload["labels"] = labels
                if assignees: payload["assignees"] = assignees
                if APPLY:
                    res = update_issue(repo, open_item["number"], payload)
                    print(f"[UPDATE] #{res['number']} {title}")
                else:
                    print(f"[DRY-RUN][UPDATE] {title} (#{open_item['number']})")
                continue

            if once and closed_item:
                print(f"[SKIP] {path}: once=true and closed issue exists (#{closed_item['number']})")
                continue

            payload = {"title": title, "body": body_full}
            if labels: payload["labels"] = labels
            if assignees: payload["assignees"] = assignees

            if APPLY:
                try:
                    res = create_issue(repo, payload)
                    print(f"[CREATE] #{res['number']} {title}")
                except Exception:
                    # Retry without assignees if assigning fails
                    payload.pop("assignees", None)
                    res = create_issue(repo, payload)
                    print(f"[CREATE] #{res['number']} {title} (assignees skipped)")
            else:
                print(f"[DRY-RUN][CREATE] {title} in {repo}")

if __name__ == "__main__":
    main()
