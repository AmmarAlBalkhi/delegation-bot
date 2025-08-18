import glob, os, hashlib, datetime as dt, sys
import requests, frontmatter

APPLY = (os.getenv("APPLY","false").lower() == "true")
TOKEN = os.getenv("GITHUB_TOKEN")
DEFAULT_REPO = os.getenv("REPO")  # "ammar-uni/delegation-bot"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

def iso(d):
    if isinstance(d, str):
        try: return dt.date.fromisoformat(d)
        except: return None
    return d

def search_issue_by_fingerprint(repo, fingerprint):
    # Use GitHub search to find an open issue with this fingerprint in the body
    q = f'repo:{repo} in:body state:open "{fingerprint}"'
    url = f"https://api.github.com/search/issues?q={requests.utils.quote(q, safe='')}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    items = r.json().get("items", [])
    return items[0] if items else None

def create_issue(repo, title, body, labels, assignees):
    url = f"https://api.github.com/repos/{repo}/issues"
    payload = {"title": title, "body": body}
    if labels: payload["labels"] = labels
    if assignees: payload["assignees"] = assignees
    r = requests.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

today = dt.date.today()
paths = sorted(glob.glob("tasks/*.md"))
print(f"[INFO] Today={today} | files={len(paths)}")

if not paths:
    print("[INFO] No files found in tasks/")
    sys.exit(0)

for path in paths:
    post = frontmatter.load(path)
    m = post.metadata

    repo = m.get("repository") or DEFAULT_REPO
    title = m.get("title","(no title)")
    assignees = m.get("assign", [])
    labels = m.get("labels", [])
    active = iso(m.get("date_active"))
    due = iso(m.get("due_date"))

    if active and active > today:
        print(f"[SKIP] {path}: not active until {active}")
        continue

    # fingerprint for idempotency (stable per path+title)
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

    if not APPLY:
        print(f"[DRY-RUN] Would create issue in {repo}: '{title}', "
              f"assignees={assignees}, labels={labels}, due={due}, fp={fp}")
        continue

    created = create_issue(repo, title, body, labels, assignees)
    print(f"[CREATED] #{created['number']} '{title}' in {repo} (fp={fp})")
