# scripts/delegation_bot.py
import glob, os, hashlib, datetime as dt, sys
import requests, frontmatter

APPLY = (os.getenv("APPLY", "false").lower() == "true")
TOKEN = os.getenv("GITHUB_TOKEN")
DEFAULT_REPO = os.getenv("REPO")  # e.g., "ammar-uni/delegation-bot"

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
    """Return (ok, normalized_meta)."""
    title = (meta.get("title") or "").strip()
    if not title:
        print(f"[ERROR] {path}: missing required field 'title'; skipping")
        return False, None

    norm = dict(meta)
    norm["assign"] = as_list(meta.get("assign"))
    norm["labels"] = as_list(meta.get("labels"))

    # Light type checks
    for k in ("assign", "labels"):
        if not all(isinstance(x, str) for x in norm[k]):
            print(f"[ERROR] {path}: '{k}' must be a string or list of strings; skipping")
            return False, None
    return True, norm

def ensure_labels(repo, labels):
    if not labels:
        return
    try:
        url = f"https://api.github.com/repos/{repo}/labels"
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        existing = {l["name"] for l in r.json()}
        to_create = [name for name in labels if name not in existing]
        for name in to_create:
            cr = requests.post(url, headers=HEADERS, json={"name": name})
            if cr.status_code not in (200, 201):
                print(f"[WARN] Could not create label '{name}' ({cr.status_code})")
    except Exception as e:
        print(f"[WARN] ensure_labels failed: {e}")

def search_issue_by_fingerprint(repo, fingerprint):
    # Look for an OPEN issue with this fingerprint hidden in the body
    q = f'repo:{repo} in:body state:open "{fingerprint}"'
    url = f"https://api.github.com/search/issues?q={requests.utils.quote(q, safe="")}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    items = r.json().get("items", [])
    return items[0] if items else None

def safe_create_issue(repo, title, body, labels, assignees):
    """Create issue; if assignees are invalid, retry without them."""
    url = f"https://api.github.com/repos/{repo}/issues"
    payload = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    if assignees:
        payload["assignees"] = assignees

    r = requests.post(url, headers=HEADERS, json=payload)
    if r.status_code == 422 and "assignees" in (r.json().get("errors", [{}])[0].get("field", "")):
        # Retry without assignees
        print(f"[WARN] Assignee not permitted; creating issue without assignees.")
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
    active = iso(m.get("date_active"))
    due = iso(m.get("due_date"))

    if active and active > today:
        print(f"[SKIP] {path}: not active until {active}")
        continue

    # Fingerprint for idempotency (stable per path+title)
    fp = hashlib.sha1(f"{path}::{title}".encode("utf-8")).hexdigest()[:12]
    body = f"""{post.content}

---

**Task source:** `{path}`
**Date active:** {active}
**Due date:** {due}
<!-- task-fingerprint:{fp} -->
"""

    existing = search_issue_by_fingerprint(repo, fp)
    if existing:
        print(f"[EXISTS] #{existing['number']} for '{title}' already open (fp={fp})")
        continue

    ensure_labels(repo, labels)

    if not APPLY:
        print(
            f"[DRY-RUN] Would create issue in {repo}: '{title}', "
            f"assignees={assignees}, labels={labels}, due={due}, fp={fp}"
        )
        continue

    created = safe_create_issue(repo, title, body, labels, assignees)
    print(f"[CREATED] #{created['number']} '{title}' in {repo} (fp={fp})")
