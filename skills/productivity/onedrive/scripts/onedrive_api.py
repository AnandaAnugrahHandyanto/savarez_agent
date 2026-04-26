#!/usr/bin/env python3
"""OneDrive CLI via Microsoft Graph — pure stdlib, no pip deps needed."""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
import mimetypes

HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
DEFAULT_TOKEN_PATH = os.path.join(HERMES_HOME, "onedrive_token.json")
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# ────────── helpers ──────────

class ODError(Exception):
    """Base OneDrive error."""

class AuthError(ODError):
    ""

class NotFoundError(ODError):
    pass

class ConflictError(ODError):
    pass

def _json_request(url, data=None, headers=None, method=None):
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            if body:
                return json.loads(body.decode())
            return {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
        except json.JSONDecodeError:
            err = {"error": {"message": body}}
        if e.code == 401:
            raise AuthError(err.get("error", {}).get("message", body))
        if e.code == 404:
            raise NotFoundError(err.get("error", {}).get("message", body))
        if e.code == 409:
            raise ConflictError(err.get("error", {}).get("message", body))
        raise ODError(f"HTTP {e.code}: {err.get('error', {}).get('message', body)}")
    except urllib.error.URLError as e:
        raise ODError(str(e))

def _load_token(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

def _save_token(token, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(token, f, indent=2)

def _maybe_refresh(token, token_path=DEFAULT_TOKEN_PATH):
    """Try to refresh the access token if present and needed. Returns (access_token, token_dict)."""
    if not token:
        raise AuthError("No token found. Run setup.py --auth first.")
    client_id = token.get("_client_id")
    refresh_token = token.get("refresh_token")
    if not client_id or not refresh_token:
        raise AuthError("Token missing refresh_token or client_id. Re-authenticate.")

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": "https://graph.microsoft.com/Files.ReadWrite offline_access User.Read"
    }).encode()

    try:
        resp = _json_request(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token.update(resp)
        _save_token(token, token_path)
        return token["access_token"], token
    except (AuthError, ODError):
        raise AuthError("Token refresh failed. Run setup.py --auth again.")

def get_access_token(token_path=DEFAULT_TOKEN_PATH):
    token = _load_token(token_path)
    if not token:
        raise AuthError(f"No token found at {token_path}. Run setup.py --auth first.")
    # Try current token first
    try:
        _json_request(f"{GRAPH_BASE}/me", headers={"Authorization": f"Bearer {token['access_token']}"})
        return token["access_token"], token
    except AuthError:
        # Expired — refresh
        return _maybe_refresh(token, token_path)

# ────────── core operations ──────────

def _normalize_path(path):
    """OneDrive paths shouldn't have leading slashes for the children endpoint."""
    path = path.lstrip("/")
    # Replace backslashes
    path = path.replace("\\", "/")
    return path

def _path_to_api(path):
    """Convert a user path string into a Graph API URL."""
    clean = _normalize_path(path)
    if not clean:
        return f"{GRAPH_BASE}/me/drive/root"
    return f"{GRAPH_BASE}/me/drive/root:/{urllib.parse.quote(clean, safe='')}"

def list_folder(path="/", token_path=DEFAULT_TOKEN_PATH):
    token, _ = get_access_token(token_path)
    url = _path_to_api(path)
    if not url.endswith("/children"):
        url += ":/children"
    items = []
    while url:
        data = _json_request(url, headers={"Authorization": f"Bearer {token}"})
        value = data.get("value", [])
        for item in value:
            items.append({
                "name": item.get("name"),
                "id": item.get("id"),
                "type": "folder" if "folder" in item else "file",
                "size": item.get("size"),
                "modified": item.get("lastModifiedDateTime"),
                "path": item.get("parentReference", {}).get("path", "") + "/" + item.get("name", ""),
                "webUrl": item.get("webUrl"),
            })
        url = data.get("@odata.nextLink")
    return items

def upload_file(local_path, remote_path, conflict="replace", token_path=DEFAULT_TOKEN_PATH):
    token, _ = get_access_token(token_path)
    if not os.path.isfile(local_path):
        raise ODError(f"Local file not found: {local_path}")

    clean_remote = _normalize_path(remote_path)

    # Detect if remote path ends in a folder or filename
    # If the remote path has no extension and we're uploading to what looks like
    # a folder, append the local filename.
    if clean_remote.endswith("/"):
        clean_remote = clean_remote + os.path.basename(local_path)
    parent = clean_remote.rsplit("/", 1)[0] if "/" in clean_remote else ""
    # If parent is empty we're uploading to root

    # API endpoint
    url = _path_to_api(clean_remote) + ":/content"

    # Conflict behavior
    conflict_param = "replace" if conflict == "replace" else "rename"
    url += f"?@microsoft.graph.conflictBehavior={conflict_param}"

    size = os.path.getsize(local_path)
    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"

    # For files under 4MB we can use simple upload (PUT)
    # For larger files, we'd need resumable upload. Keeping it simple (max 60MB for now.)
    if size > 62_914_560:  # ~60MB
        raise ODError("File too large. Chunked upload not yet implemented.")

    with open(local_path, "rb") as f:
        body = f.read()

    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode())
            return {
                "name": data.get("name"),
                "id": data.get("id"),
                "size": data.get("size"),
                "webUrl": data.get("webUrl"),
                "created": data.get("createdDateTime"),
                "conflictBehavior": conflict_param
            }
    except urllib.error.HTTPError as e:
        if e.code == 409 and conflict == "rename":
            body = json.loads(e.read().decode())
            # Microsoft renamed it; sometimes it returns the uploaded item anyway
            return {"error": "Conflict — rename may have occurred", "details": body}
        raise ODError(f"Upload failed: HTTP {e.code}")

def download_file(remote_path, local_path=None, item_id=None, token_path=DEFAULT_TOKEN_PATH):
    token, _ = get_access_token(token_path)
    if item_id:
        url = f"{GRAPH_BASE}/me/drive/items/{item_id}"
    else:
        url = _path_to_api(remote_path)

    # First get metadata + content download URL
    meta = _json_request(url, headers={"Authorization": f"Bearer {token}"})

    if local_path is None:
        local_path = meta.get("name", "download")

    # The "@microsoft.graph.downloadUrl" is a short-lived direct URL
    download_url = meta.get("@microsoft.graph.downloadUrl")
    if not download_url:
        raise ODError("No download URL available for this item.")

    # Download using the direct URL (no auth needed for this URL)
    req = urllib.request.Request(download_url)
    with urllib.request.urlopen(req, timeout=300) as resp:
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(resp.read())

    return {"local_path": os.path.abspath(local_path), "name": meta.get("name"), "size": meta.get("size")}

def delete_item(remote_path=None, item_id=None, token_path=DEFAULT_TOKEN_PATH):
    token, _ = get_access_token(token_path)
    if item_id:
        url = f"{GRAPH_BASE}/me/drive/items/{item_id}"
    else:
        url = _path_to_api(remote_path)
    _json_request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    return {"deleted": True}

def create_folder(remote_path, token_path=DEFAULT_TOKEN_PATH):
    token, _ = get_access_token(token_path)
    clean = _normalize_path(remote_path)
    if "/" in clean:
        parent = clean.rsplit("/", 1)[0]
        name = clean.rsplit("/", 1)[1]
        parent_url = _path_to_api(parent) + ":/children"
    else:
        name = clean
        parent_url = f"{GRAPH_BASE}/me/drive/root/children"

    body = json.dumps({"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}).encode()
    req = urllib.request.Request(parent_url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
        return {"name": data.get("name"), "id": data.get("id"), "webUrl": data.get("webUrl")}

def search_items(query, token_path=DEFAULT_TOKEN_PATH):
    token, _ = get_access_token(token_path)
    url = f"{GRAPH_BASE}/me/drive/search(q='{urllib.parse.quote(query)}')"
    items = []
    while url:
        data = _json_request(url, headers={"Authorization": f"Bearer {token}"})
        for item in data.get("value", []):
            items.append({
                "name": item.get("name"),
                "id": item.get("id"),
                "type": "folder" if "folder" in item else "file",
                "size": item.get("size"),
                "modified": item.get("lastModifiedDateTime"),
                "webUrl": item.get("webUrl"),
            })
        url = data.get("@odata.nextLink")
    return items

# ────────── CLI ──────────

def print_json(data):
    print(json.dumps(data, indent=2, default=str))

def print_table(items):
    if not items:
        print("No items.")
        return
    if isinstance(items, dict):
        for k, v in items.items():
            print(f"  {k:20s} {v}")
        return
    for item in items:
        t = item.get("type", "file")[0].upper()
        name = item.get("name", "?")
        size = item.get("size", "")
        mod = item.get("modified", "")[:19] if item.get("modified") else ""
        print(f"  [{t}] {name:40s} {str(size):>12s}  {mod}")

def main():
    parser = argparse.ArgumentParser(description="OneDrive via Microsoft Graph")
    parser.add_argument("--token-path", default=DEFAULT_TOKEN_PATH, help="Token file path")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List a folder")
    p_list.add_argument("path", nargs="?", default="/", help="Remote path")

    # upload
    p_up = sub.add_parser("upload", help="Upload a file")
    p_up.add_argument("local_path", help="Local file path")
    p_up.add_argument("remote_path", nargs="?", help="Remote path (default: root with same name)")
    p_up.add_argument("--conflict", choices=["replace", "rename"], default="replace", help="On conflict behavior")

    # download
    p_down = sub.add_parser("download", help="Download a file")
    p_down.add_argument("remote_path", nargs="?", help="Remote path")
    p_down.add_argument("local_path", nargs="?", help="Local destination path")
    p_down.add_argument("--id", dest="item_id", help="Download by item ID instead of path")

    # delete
    p_del = sub.add_parser("delete", help="Delete a file or folder")
    p_del.add_argument("remote_path", nargs="?", help="Remote path")
    p_del.add_argument("--id", dest="item_id", help="Delete by item ID")

    # mkdir
    p_mkdir = sub.add_parser("mkdir", help="Create a folder")
    p_mkdir.add_argument("path", help="Remote folder path")

    # search
    p_search = sub.add_parser("search", help="Search OneDrive")
    p_search.add_argument("query", help="Search query")

    args = parser.parse_args()

    try:
        if args.command == "list":
            result = list_folder(args.path, args.token_path)
        elif args.command == "upload":
            remote = args.remote_path or os.path.basename(args.local_path)
            result = upload_file(args.local_path, remote, args.conflict, args.token_path)
        elif args.command == "download":
            result = download_file(args.remote_path, args.local_path, args.item_id, args.token_path)
        elif args.command == "delete":
            result = delete_item(args.remote_path, args.item_id, args.token_path)
        elif args.command == "mkdir":
            result = create_folder(args.path, args.token_path)
        elif args.command == "search":
            result = search_items(args.query, args.token_path)
        else:
            parser.print_help()
            sys.exit(1)
    except AuthError as e:
        print(json.dumps({"error": str(e), "fix": "Run setup.py --auth first."}))
        sys.exit(1)
    except NotFoundError as e:
        print(json.dumps({"error": f"Not found: {e}"}))
        sys.exit(1)
    except ODError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    if args.format == "json":
        print_json(result)
    else:
        if isinstance(result, list):
            print_table(result)
        elif isinstance(result, dict):
            print_table(result)

if __name__ == "__main__":
    main()
