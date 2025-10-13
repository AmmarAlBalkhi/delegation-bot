import os, re, hashlib
from datetime import date
from pathlib import Path
import requests
import frontmatter

# --------- REST & GraphQL basics ---------
REST = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_ENV = os.environ.get("REPO", "")
APPLY = os.environ.get("APPLY", "false").strip().lower() == "true"

PROJECT_LOGIN = os.environ.get("PROJECT_LOGIN", "").strip()    # e.g., "ammar-uni" or your org
PROJECT_TITLE = os.environ.get("PROJECT_TITLE", "").strip()    # e.g., "Delegation Bot - PoC"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}

# --------- helpers ---------
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
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "task"

def posix_rel(path: str) -> str:
    return Path(path).as_posix()

# --------- load tasks (single & multi) ---------
def load_task_files():
    files=[]
    for root,_,names in os.walk("tasks"):
        for n in names:
            if n.endswith(".md"):
                files.append(os.path.join(root,n))
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

# --------- fingerprint (thesis spec) ---------
def compute_fpr(repo: str, src: str, key: str, occ: str) -> str:
    return hashlib.sha256(f"{repo}|{src}|{key}|{occ}".encode("utf-8")).hexdigest()

def fpr_comment(fpr: str, src: str, key: str, occ: str) -> str:
    return f"<!-- 🔑 delegation-bot:fpr=sha256:{fpr}; src={src}; key={key}; occ={occ} -->"

def search_by_fpr(repo: str, fpr: str):
    q = f'repo:{repo} in:body "delegation-bot:fpr=sha256:{fpr}"'
    r = requests.get(f"{REST}/search/issues", headers=HEADERS, params={"q": q})
    if not r.ok: return None, None
    items = r.json().get("items", [])
    open_item = next((it for it in items if it.get("state")=="open"), None)
    closed_item = next((it for it in items if it.get("state")=="closed"), None)
    return open_item, closed_item

def update_issue(repo: str, number: int, payload: dict):
    r = requests.patch(f"{REST}/repos/{repo}/issues/{number}", headers=HEADERS, json=payload)
    r.raise_for_status(); return r.json()

def create_issue(repo: str, payload: dict):
    r = requests.post(f"{REST}/repos/{repo}/issues", headers=HEADERS, json=payload)
    r.raise_for_status(); return r.json()

# --------- GraphQL for Project v2 (dates in project) ---------
def gql(query: str, variables: dict):
    r = requests.post(GRAPHQL, headers=HEADERS, json={"query": query, "variables": variables})
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL: {data['errors']}")
    return data["data"]

_project_cache = {"id": None, "fields": {}}

def get_project_id():
    if not PROJECT_LOGIN or not PROJECT_TITLE:
        return None
    if _project_cache["id"]:
        return _project_cache["id"]
    q = """
    query($login:String!, $q:String!){
      user(login:$login){ projectsV2(first:50, query:$q){ nodes{ id title } } }
      organization(login:$login){ projectsV2(first:50, query:$q){ nodes{ id title } } }
    }"""
    d = gql(q, {"login": PROJECT_LOGIN, "q": PROJECT_TITLE})
    nodes = []
    if d.get("user"): nodes += d["user"]["projectsV2"]["nodes"]
    if d.get("organization"): nodes += d["organization"]["projectsV2"]["nodes"]
    for n in nodes:
        if n["title"] == PROJECT_TITLE:
            _project_cache["id"] = n["id"]; return n["id"]
    return None

def get_field_id(project_id: str, name: str):
    key = (project_id, name)
    if key in _project_cache["fields"]:
        return _project_cache["fields"][key]
    q = """
    query($id:ID!){
      node(id:$id){
        ... on ProjectV2{
          fields(first:100){
            nodes{
              ... on ProjectV2FieldCommon { id name dataType }
            }
          }
        }
      }
    }"""
    d = gql(q, {"id": project_id})
    for n in d["node"]["fields"]["nodes"]:
        if n["name"] == name:
            _project_cache["fields"][key] = n["id"]; return n["id"]
    # create a new Date field if missing
    m = """
    mutation($pid:ID!, $name:String!){
      createProjectV2Field(input:{projectId:$pid, dataType:DATE, name:$name}){
        projectV2Field{ ... on ProjectV2FieldCommon { id name } }
      }
    }"""
    d2 = gql(m, {"pid": project_id, "name": name})
    fid = d2["createProjectV2Field"]["projectV2Field"]["id"]
    _project_cache["fields"][key] = fid
    return fid

def get_project_item_id_for_issue(project_id: str, issue_node_id: str):
    q = """
    query($iid:ID!){
      node(id:$iid){
        ... on Issue{
          projectItems(first:50){
            nodes{ id project{ id title } }
          }
        }
      }
    }"""
    d = gql(q, {"iid": issue_node_id})
    nodes = d["node"]["projectItems"]["nodes"]
    for n in nodes:
        if n["project"]["id"] == project_id:
            return n["id"]
    return None

def add_issue_to_project(project_id: str, issue_node_id: str):
    # Try to add; ignore if already present
    m = """
    mutation($pid:ID!, $cid:ID!){
      addProjectV2ItemById(input:{projectId:$pid, contentId:$cid}){
        item{ id }
      }
    }"""
    try:
        d = gql(m, {"pid": project_id, "cid": issue_node_id})
        return d["addProjectV2ItemById"]["item"]["id"]
    except Exception:
        # If it already exists, look it up
        return get_project_item_id_for_issue(project_id, issue_node_id)

def set_date_field(project_id: str, item_id: str, field_id: str, date_str: str):
    if not date_str:
        return
    m = """
    mutation($pid:ID!, $iid:ID!, $fid:ID!, $val:String!){
      updateProjectV2ItemFieldValue(input:{
        projectId:$pid, itemId:$iid, fieldId:$fid, value:{ date:$val }
      }){ projectV2Item{ id } }
    }"""
    gql(m, {"pid": project_id, "iid": item_id, "fid": field_id, "val": date_str})

def write_dates_to_project(issue_json: dict, date_active: str, due_date: str):
    if not (PROJECT_LOGIN and PROJECT_TITLE):
        return
    project_id = get_project_id()
    if not project_id:
        return
    item_id = add_issue_to_project(project_id, issue_json["node_id"])
    if not item_id:
        return
    # Ensure fields exist, then set them
    fa_id = get_field_id(project_id, "Date active")
    dd_id = get_field_id(project_id, "Due date")
    if date_active:
        set_date_field(project_id, item_id, fa_id, date_active)
    if due_date:
        set_date_field(project_id, item_id, dd_id, due_date)

# --------- main ---------
def main():
    for path in load_task_files():
        tasks, body = load_tasks_from_file(path)
        for t in tasks:
            repo = t.get("repository") or REPO_ENV
            title = t.get("title")
            if not (repo and title):
                print(f"[SKIP] {path}: missing repository or title"); continue

            da = str(t.get("date_active") or "").strip()
            if da and da > today_iso():
                print(f"[SKIP] {path}: date_active in future ({da})"); continue

            labels = as_list(t.get("labels"))
            assignees = as_list(t.get("assign"))
            once = as_bool(t.get("once"))
            due = str(t.get("due_date") or "").strip()

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
                    # write dates into project
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
                # write dates into project
                write_dates_to_project(res, da, due)
            else:
                print(f"[DRY-RUN][CREATE] {title} in {repo}")

if __name__ == "__main__":
    main()
