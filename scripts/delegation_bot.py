import glob, os, hashlib, datetime as dt, sys
import requests, frontmatter

APPLY = (os.getenv("APPLY", "false").lower() == "true")
TOKEN = os.getenv("GITHUB_TOKEN")
DEFAULT_REPO = os.getenv("REPO")  # "ammar-uni/delegation-bot"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# ---------- helpers ----------
def iso(d):
    if isinstance(d, str):
        try:
            return dt.date.fromisoformat(d)
        except Exception:
            return None
    return d

def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]

def validate_and_normalize(meta, path):
    title = (meta.get("title") or "").strip()
    if not title:
        print(f"[ERROR] {path}: missing required field 'title'; skipping")
        return False, None
    norm = dict(meta)
    norm["assign"] = as_list(meta.get("assign"))
    norm["labels"] = as_list(meta.get("labels"))
    for k in ("assign", "labels"):
        if not all(isinstance(x, str) for x in norm[k]):
            print(f"[ERROR] {path}: '{k}' must be a string or list of strings; skipping")
            return False, None
    return True, norm

def ensure_labels(repo, labels):
    if not labels: return
    try:
        url = f"https://api.github.com/repos/{repo}/labels"
        r = requests.get(url, headers=HEADERS); r.raise_for_status()
        existing = {l["name"] for l in r.json()}
        for name in labels:
            if name not in existing:
                cr = requests.post(url, headers=HEADERS, json={"name": name})
                if cr.status_code not in (200, 201):
                    print(f"[WARN] Could not create label '{name}' ({cr.status_code})")
    except Exception as e:
        print(f"[WARN] ensure_labels failed: {e}")

def search_issue_by_fingerprint(repo, fingerprint, state="open"):
    # state: "open" | "closed" | "all"
    state_q = "is:open" if state == "open" else ("is:closed" if state == "closed" else "")
    q = f'repo:{repo} in:body is:issue {state_q} "{fingerprint}"'
    url = f"https://api.github.com/search/issues?q={requests.utils.quote(q, safe='')}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    items = r.json().get("items", [])
    return items[0] if items else None

def safe_create_issue(repo, title, body, labels, assignees):
    url = f"https://api.github.com/repos/{repo}/issues"
    payload = {"title": title, "body": body}
    if labels: payload["labels"] = labels
    if assignees: payload["assignees"] = assignees
    r = requests.post(url, headers=HEADERS, json=payload)
    if r.status_code == 422 and "assignees" in (r.json().get("errors", [{}])[0].get("field", "")):
        print("[WARN] Assignee not permitted; creating issue without assignees.")
        payload.pop("assignees", None)
        r = requests.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()
# ---------- /helpers ----------

today = dt.date.today()
paths = sorted(glob.glob("tasks/*.md"))
print(f"[INFO] Today={today} | files={len(paths)}")

if not paths:
    print("[INFO] No files found in tasks/")
    sys.exit(0)

for path in paths:
    post = frontmatter.load(path)
    ok, m = validate_and_normalize(post.metadata, path)
    if not ok: 
        continue

    repo = m.get("repository") or DEFAULT_REPO
    title = m.get("title", "(no title)")
    assignees = m.get("assign", [])
    labels = m.get("labels", [])
    once = str(m.get("once", "false")).lower() in ("true", "1", "yes")
    active = iso(m.get("date_active"))
    due = iso(m.get("due_date"))

    if active and active > today:
        print(f"[SKIP] {path}: not active until {active}")
        continue

    fp = hashlib.sha1(f"{path}::{title}".encode("utf-8")).hexdigest()[:12]
    body = f"""{post.content}

---

**Task source:** `{path}`
**Date active:** {active}
**Due date:** {due}
<!-- task-fingerprint:{fp} -->
"""

    # 1) Skip if an OPEN copy exists
    existing_open = search_issue_by_fingerprint(repo, fp, "open")
    if existing_open:
        print(f"[EXISTS] #{existing_open['number']} for '{title}' already open (fp={fp})")
        continue

    # 2) If once=true, also skip if it was already done in the past
    if once:
        existing_closed = search_issue_by_fingerprint(repo, fp, "closed")
        if existing_closed:
            print(f"[SKIP] {path}: once=true and closed issue #{existing_closed['number']} exists (fp={fp})")
            continue

    ensure_labels(repo, labels)

    if not APPLY:
        print(f"[DRY-RUN] Would create issue in {repo}: '{title}', "
              f"assignees={assignees}, labels={labels}, due={due}, fp={fp}, once={once}")
        continue

    created = safe_create_issue(repo, title, body, labels, assignees)
    print(f"[CREATED] #{created['number']} '{title}' in {repo} (fp={fp})")
