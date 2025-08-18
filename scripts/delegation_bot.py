import glob, sys, datetime as dt
import frontmatter

def iso(d):
    if isinstance(d, str):
        try: return dt.date.fromisoformat(d)
        except: return None
    return d

today = dt.date.today()

for path in glob.glob("tasks/*.md"):
    post = frontmatter.load(path)
    m = post.metadata
    title = m.get("title","(no title)")
    assignees = m.get("assign", [])
    labels = m.get("labels", [])
    active = iso(m.get("date_active"))
    due = iso(m.get("due_date"))
    if active and active > today:
        print(f"[SKIP] {path}: not active until {active}")
        continue
    print(f"[DRY-RUN] Would create issue: '{title}', assignees={assignees}, labels={labels}, due={due}")
