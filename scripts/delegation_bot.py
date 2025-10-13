import os, re, hashlib
from datetime import date
from pathlib import Path
import requests
import frontmatter

REST = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"

# Prefer PAT for Projects v2 writes; fall back to GITHUB_TOKEN (issues).
TOKEN = os.environ.get("PROJECT_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
REPO_ENV = os.environ.get("REPO", "")
APPLY = os.environ.get("APPLY", "false").strip().lower() == "true"

PROJECT_LOGIN = os.environ.get("PROJECT_LOGIN", "").strip()
PROJECT_TITLE = os.environ.get("PROJECT_TITLE", "").strip()

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

print(f"[PROJECT] token_source={'PROJECT_TOKEN' if os.environ.get('PROJECT_TOKEN') else 'GITHUB_TOKEN'}")
print(f"[PROJECT] target login/title: {PROJECT_LOGIN!r} / {PROJECT_TITLE!r}")

def today_iso() -> str:
    return date.today().isoformat()

def as_list(v):
    if v is None: return []
    if isinstance(v, list): return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    return [s] if s else []

def as_bool(v):
    if isinstance(v, bool): return v
    if v is None: return False
    return str(v).strip().lower() in {"true","1","yes","y"}

def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+","-", s.lower()).strip("-")
    return s or "task"

def posix_rel(path: str) -> str:
    return Path(path).as_posix()

# ---------- Load tasks (single + multi) ----------
def load_task_files():
    files=[]
    for root,_,names in os.walk("tasks"):
        for n in names:
            if n.endswith(".md"): files.append(os.path.join(root,n))
    return sorted(files)

def load_tasks_from_file(path):
    post = frontmatter.load(path)
    meta = post.metadata or {}
    body = post.content or ""
    if isinstance(meta.get("tasks"), list):
        defaults = {k:v for k,v in meta.items() if k!="tasks"}
        tasks=[]
        for t in meta["tasks"]:
            merged = defaults.copy(); merged.update(t or {})
            merged["_src"] = path
            tasks.append(merged)
        return tasks, body
    single = meta.copy(); single["_src"] = path
    return [single], body

# ---------- Fingerprint + Issues ----------
def compute_fpr(repo: str, src: str, key: str, occ: str) -> str:
    return hashlib.sha256(f"{repo}|{src}|{key}|{occ}".encode("utf-8")).hexdigest()

def fpr_comment(fpr: str, src: str, key: str, occ: str) -> str:
    return f"<!-- 🔑 delegation-bot:fpr=sha256:{fpr}; src={src}; key={key}; occ={occ} -->"

def search_by_fpr(repo: str, fpr: str):
    q = f'repo:{repo} in:body "delegation-bot:fpr=sha256:{fpr}"'
    r = requests.get(f"{REST}/search/issues", headers=HEADERS, params={"q": q})
    if not r.ok: return None, None
    items = r.json().get("items", [])
    open_item  = next((it for it in items if it.get("state")=="open"), None)
    closed_item= next((it for it in items if it.get("state")=="closed"), None)
    return open_item, closed_item

def update_issue(repo: str, number: int, payload: dict):
    r = requests.patch(f"{REST}/repos/{repo}/issues/{number}", headers=HEADERS, json=payload)
    r.raise_for_status(); return r.json()

def create_issue(repo: str, payload: dict):
    r = requests.post(f"{REST}/repos/{repo}/issues", headers=HEADERS, json=payload)
    r.raise_for_status(); return r.json()

# ---------- GraphQL helpers for Project v2 ----------
def gql(query: str, variables: dict):
    r = requests.post(GRAPHQL, headers=HEADERS, json={"query": query, "variables": variables})
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL error: {data['errors']}")
    return data["data"]

_project_cache = {"id": None, "fields": {}}

def get_project_id():
    """
    Look up a ProjectV2 by PROJECT_LOGIN + PROJECT_TITLE.
    Try the login as a USER first; if not found, try as an ORG.
    Avoids the GraphQL 'organization not found' error.
    """
    if not (PROJECT_LOGIN and PROJECT_TITLE):
        print("[PROJECT] PROJECT_LOGIN/PROJECT_TITLE not set; skip")
        return None

    # --- 1) Try as USER ---
    q_user = """
    query($login:String!){
      user(login:$login){
        projectsV2(first:50){
          nodes { id title }
        }
      }
    }"""
    try:
        d = gql(q_user, {"login": PROJECT_LOGIN})
        nodes = (d.get("user") or {}).get("projectsV2", {}).get("nodes", []) or []
        match = next((n for n in nodes if n["title"] == PROJECT_TITLE), None)
        if match:
            _project_cache["id"] = match["id"]
            print(f"[PROJECT] Found USER project id={match['id']}")
            return match["id"]
        else:
            print(f"[PROJECT] USER projects found (no exact match): {[n['title'] for n in nodes]}")
    except Exception as e:
        print(f"[PROJECT] User lookup failed: {e}")

    # --- 2) Try as ORG ---
    q_org = """
    query($login:String!){
      organization(login:$login){
        projectsV2(first:50){
          nodes { id title }
        }
      }
    }"""
    try:
        d = gql(q_org, {"login": PROJECT_LOGIN})
        nodes = (d.get("organization") or {}).get("projectsV2", {}).get("nodes", []) or []
        match = next((n for n in nodes if n["title"] == PROJECT_TITLE), None)
        if match:
            _project_cache["id"] = match["id"]
            print(f"[PROJECT] Found ORG project id={match['id']}")
            return match["id"]
        else:
            print(f"[PROJECT] ORG projects found (no exact match): {[n['title'] for n in nodes]}")
    except Exception as e:
        print(f"[PROJECT] Org lookup failed: {e}")

    print(f"[PROJECT] Project not found for login/title: {PROJECT_LOGIN!r}/{PROJECT_TITLE!r}")
    return None

def get_field_id(project_id: str, name: str):
    key = (project_id, name)
    if key in _project_cache["fields"]:
        return _project_cache["fields"][key]
    q = """
    query($id:ID!){
      node(id:$id){
        ... on ProjectV2{
          fields(first:100){ nodes{ ... on ProjectV2FieldCommon { id name dataType } } }
        }
      }
    }"""
    d = gql(q, {"id": project_id})
    for n in d["node"]["fields"]["nodes"]:
        if n["name"] == name:
            _project_cache["fields"][key] = n["id"]
            print(f"[PROJECT] Field exists {name} id={n['id']} type={n.get('dataType')}")
            return n["id"]
    m = """
    mutation($pid:ID!, $name:String!){
      createProjectV2Field(input:{projectId:$pid, dataType:DATE, name:$name}){
        projectV2Field{ ... on ProjectV2FieldCommon { id name } }
      }
    }"""
    d2 = gql(m, {"pid": project_id, "name": name})
    fid = d2["createProjectV2Field"]["projectV2Field"]["id"]
    _project_cache["fields"][key] = fid
    print(f"[PROJECT] Created Date field {name} id={fid}")
    return fid

def get_project_item_id_for_issue(project_id: str, issue_node_id: str):
    q = """
    query($iid:ID!){
      node(id:$iid){
        ... on Issue{
          projectItems(first:50){ nodes{ id project{ id title } } }
        }
      }
    }"""
    d = gql(q, {"iid": issue_node_id})
    for n in d["node"]["projectItems"]["nodes"]:
        if n["project"]["id"] == project_id:
            return n["id"]
    return None

def add_issue_to_project(project_id: str, issue_node_id: str):
    m = """
    mutation($pid:ID!, $cid:ID!){
      addProjectV2ItemById(input:{projectId:$pid, contentId:$cid}){ item{ id } }
    }"""
    try:
        d = gql(m, {"pid": project_id, "cid": issue_node_id})
        item_id = d["addProjectV2ItemById"]["item"]["id"]
        print(f"[PROJECT] Added to project item={item_id}")
        return item_id
    except Exception as e:
        print(f"[PROJECT] addProjectV2ItemById failed (maybe exists): {e}")
        return get_project_item_id_for_issue(project_id, issue_node_id)

def set_date_field(project_id: str, item_id: str, field_id: str, date_str: str, label: str):
    if not date_str:
        return
    # NOTE: $val must be Date!, not String!
    m = """
    mutation($pid:ID!, $iid:ID!, $fid:ID!, $val:Date!){
      updateProjectV2ItemFieldValue(input:{
        projectId:$pid, itemId:$iid, fieldId:$fid, value:{ date:$val }
      }){ projectV2Item{ id } }
    }"""
    gql(m, {"pid": project_id, "iid": item_id, "fid": field_id, "val": date_str})
    print(f"[PROJECT] {label} set => {date_str}")


def write_dates_to_project(issue_json: dict, date_active: str, due_date: str):
    try:
        project_id = get_project_id()
        if not project_id:
            return
        item_id = add_issue_to_project(project_id, issue_json["node_id"])
        if not item_id:
            print("[PROJECT] Could not resolve project item id; skip date write")
            return
        print(f"[PROJECT] item={item_id}  Date active={date_active or '-'}  Due date={due_date or '-'}")
        fa_id = get_field_id(project_id, "Date active")
        dd_id = get_field_id(project_id, "Due date")
        if date_active: set_date_field(project_id, item_id, fa_id, date_active, "Date active")
        if due_date:    set_date_field(project_id, item_id, dd_id, due_date, "Due date")
    except Exception as e:
        print(f"[PROJECT] ERROR while writing dates: {e}")

# ---------- Main ----------
def main():
    for path in load_task_files():
        tasks, body = load_tasks_from_file(path)
        for t in tasks:
            repo = (t.get("repository") or REPO_ENV).strip()
            title = (t.get("title") or "").strip()
            if not (repo and title):
                print(f"[SKIP] {path}: missing repository or title"); continue

            da = str(t.get("date_active") or "").strip()
            if da and da > today_iso():
                print(f"[SKIP] {path}: date_active in future ({da})"); continue

            labels    = as_list(t.get("labels"))
            assignees = as_list(t.get("assign"))
            once      = as_bool(t.get("once"))
            due       = str(t.get("due_date") or "").strip()

            src = posix_rel(t.get("_src", path))
            key = t.get("id") or slug(title)
            occ = "" if once else (da or "")
            fpr = compute_fpr(repo, src, key, occ)
            marker = fpr_comment(fpr, src, key, occ)

            info = [f"**Task source:** `{src}`", f"**Date active:** {da or 'None'}"]
            if due: info.append(f"**Due date:** {due}")
            body_full = f"{body}\n\n{marker}\n\n" + "\n".join(info)

            open_item, closed_item = search_by_fpr(repo, fpr)
            if open_item:
                payload = {"title": title, "body": body_full}
                if labels: payload["labels"] = labels
                if assignees: payload["assignees"] = assignees
                if APPLY:
                    res = update_issue(repo, open_item["number"], payload)
                    print(f"[UPDATE] #{res['number']} {title}")
                    write_dates_to_project(res, da, due)
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
                    payload.pop("assignees", None)
                    res = create_issue(repo, payload)
                    print(f"[CREATE] #{res['number']} {title} (assignees skipped)")
                write_dates_to_project(res, da, due)
            else:
                print(f"[DRY-RUN][CREATE] {title} in {repo}")

if __name__ == "__main__":
    main()
