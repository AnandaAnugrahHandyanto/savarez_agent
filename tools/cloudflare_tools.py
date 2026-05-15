"""Cloudflare connectors as Hermes tools.

A single toolset (``cloudflare``) that exposes Cloudflare's developer-platform
products as first-class tools the agent can call:

* **KV**           — key/value store (config, feature flags, short-lived state)
* **R2**           — S3-compatible object storage (blobs, snapshots, attachments)
* **D1**           — serverless SQLite with FTS5/JSON
* **Vectorize**    — managed vector DB for semantic memory
* **AI Search**    — fully managed RAG (ex-AutoRAG): hybrid BM25 + semantic
* **Workers AI**   — chat completions (OpenAI-compat) and embeddings
* **Browser**      — Browser Rendering REST API (screenshot, PDF, scrape)
* **Email**        — Cloudflare Email Service transactional sending (public beta)
* **Image Gen**    — Workers AI text-to-image (FLUX.2, Leonardo, SDXL-Lightning)

Required environment:
    CLOUDFLARE_API_TOKEN   — token with the relevant product permissions
    CLOUDFLARE_ACCOUNT_ID  — account ID

Optional environment (per-product convenience defaults — every tool can also
take an explicit ID/name argument):
    CLOUDFLARE_GATEWAY_ID
    CLOUDFLARE_AI_SEARCH_ID
    CLOUDFLARE_KV_NAMESPACE_ID
    CLOUDFLARE_D1_DATABASE_ID
    CLOUDFLARE_VECTORIZE_INDEX
    CLOUDFLARE_R2_BUCKET
    CLOUDFLARE_R2_ACCESS_KEY_ID, CLOUDFLARE_R2_SECRET_ACCESS_KEY  (S3-compat path)
    CLOUDFLARE_EMAIL_FROM
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from tools.registry import registry

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"
TOOLSET = "cloudflare"
DEFAULT_TIMEOUT = 60

# Default Workers AI models — picked May 2026 from
# https://developers.cloudflare.com/workers-ai/models/. Keep these conservative:
# free-tier-eligible, GA (not beta), and known to take the JSON shapes our
# wrappers assume. Callers can always override per-call.
DEFAULT_CHAT_MODEL = "@cf/meta/llama-4-scout-17b-16e-instruct"
DEFAULT_EMBED_MODEL = "@cf/baai/bge-m3"
DEFAULT_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _cf_token() -> Optional[str]:
    return os.environ.get("CLOUDFLARE_API_TOKEN", "").strip() or None


def _cf_account_id() -> Optional[str]:
    return os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip() or None


def _check_cf_requirements() -> bool:
    """Toolset-level availability gate."""
    return bool(_cf_token() and _cf_account_id())


def _missing_credentials_error() -> str:
    return _err(
        "Cloudflare tools require CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID. "
        "Create a token at https://dash.cloudflare.com/profile/api-tokens and find "
        "your account ID at https://dash.cloudflare.com (right sidebar of any zone "
        "or Workers page)."
    )


def _cf_request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    data: Optional[bytes] = None,
    headers_extra: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Call the Cloudflare REST API and return a normalized result dict.

    Returns either ``{"ok": True, "result": ...}`` or
    ``{"ok": False, "error": "..."}``. Never raises.
    """
    token = _cf_token()
    if not token:
        return {"ok": False, "error": "missing CLOUDFLARE_API_TOKEN"}

    url = f"{CF_API_BASE}{path}" if path.startswith("/") else f"{CF_API_BASE}/{path}"
    headers = {"Authorization": f"Bearer {token}"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    if headers_extra:
        headers.update(headers_extra)

    try:
        resp = requests.request(
            method,
            url,
            params=params,
            json=json_body,
            data=data,
            headers=headers,
            timeout=timeout,
        )
    except requests.Timeout:
        return {"ok": False, "error": f"Cloudflare API timeout after {timeout}s"}
    except requests.ConnectionError as exc:
        return {"ok": False, "error": f"Cloudflare API connection error: {exc}"}

    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            payload: Any = resp.json()
        except Exception:
            payload = {"raw": resp.text[:500]}
    else:
        payload = {"raw": resp.content if resp.content else b"", "content_type": content_type}

    if not resp.ok:
        if isinstance(payload, dict):
            errors = payload.get("errors") or []
            if errors and isinstance(errors, list):
                msg = "; ".join(
                    str(e.get("message", e)) if isinstance(e, dict) else str(e)
                    for e in errors
                )
                return {"ok": False, "error": f"HTTP {resp.status_code}: {msg}", "status": resp.status_code}
            raw = payload.get("raw")
            if isinstance(raw, str):
                return {"ok": False, "error": f"HTTP {resp.status_code}: {raw[:300]}", "status": resp.status_code}
        return {"ok": False, "error": f"HTTP {resp.status_code}", "status": resp.status_code}

    if isinstance(payload, dict) and "result" in payload:
        return {"ok": True, "result": payload["result"], "raw": payload}
    return {"ok": True, "result": payload}


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False, default=str)


def _err(msg: str, **extra: Any) -> str:
    return json.dumps({"ok": False, "error": msg, **extra}, ensure_ascii=False)


def _resolve_id(
    explicit: Optional[str],
    env_var: Optional[str] = None,
) -> Optional[str]:
    """Return an explicit value or the configured env-var fallback."""
    if explicit is None and env_var:
        explicit = os.environ.get(env_var)
    if isinstance(explicit, str):
        explicit = explicit.strip()
    return explicit or None


# ===========================================================================
# Workers AI — chat / embeddings / image
# ===========================================================================


def _workers_ai_chat(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    gateway_id: Optional[str] = None,
) -> str:
    """Workers AI chat completion via the OpenAI-compatible endpoint.

    Routes through AI Gateway when ``gateway_id`` (or CLOUDFLARE_GATEWAY_ID) is
    set so observability and caching kick in automatically.
    """
    if not _check_cf_requirements():
        return _missing_credentials_error()
    if not model or not isinstance(model, str):
        return _err(
            "'model' is required (e.g. '@cf/meta/llama-4-scout-17b-16e-instruct' "
            "or '@cf/openai/gpt-oss-120b')"
        )
    if not isinstance(messages, list) or not messages:
        return _err("'messages' must be a non-empty list of {role, content}")

    account_id = _cf_account_id()
    gw = _resolve_id(gateway_id, "CLOUDFLARE_GATEWAY_ID")
    if gw:
        url = (
            f"https://gateway.ai.cloudflare.com/v1/{account_id}/{gw}"
            "/workers-ai/v1/chat/completions"
        )
    else:
        url = f"{CF_API_BASE}/accounts/{account_id}/ai/v1/chat/completions"

    body: Dict[str, Any] = {"model": model, "messages": messages}
    if max_tokens is not None:
        body["max_tokens"] = int(max_tokens)
    if temperature is not None:
        body["temperature"] = float(temperature)

    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {_cf_token()}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
    except requests.RequestException as exc:
        return _err(f"Workers AI request failed: {exc}")

    if not resp.ok:
        return _err(
            f"Workers AI HTTP {resp.status_code}: {resp.text[:300]}",
            status=resp.status_code,
        )

    try:
        data = resp.json()
    except Exception:
        return _err("Workers AI returned non-JSON response")

    choice0 = (data.get("choices") or [{}])[0]
    return _ok(
        {
            "model": model,
            "content": (choice0.get("message") or {}).get("content"),
            "finish_reason": choice0.get("finish_reason"),
            "usage": data.get("usage"),
            "raw": data,
        }
    )


def _workers_ai_embed(text: Any, *, model: str = DEFAULT_EMBED_MODEL) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    if not text:
        return _err("'text' is required (string or list of strings)")
    inputs: List[str] = [text] if isinstance(text, str) else [str(x) for x in text]

    res = _cf_request(
        "POST",
        f"/accounts/{_cf_account_id()}/ai/run/{model}",
        json_body={"text": inputs},
    )
    if not res["ok"]:
        return _err(res["error"])
    payload = res["result"]
    vectors = payload.get("data") if isinstance(payload, dict) else None
    return _ok({"model": model, "vectors": vectors, "raw": payload})


def _workers_ai_image(
    prompt: str,
    *,
    model: str = DEFAULT_IMAGE_MODEL,
    steps: Optional[int] = None,
    seed: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    if not prompt or not isinstance(prompt, str):
        return _err("'prompt' is required")

    body: Dict[str, Any] = {"prompt": prompt}
    if steps is not None:
        body["num_steps"] = int(steps)
    if seed is not None:
        body["seed"] = int(seed)
    if width is not None:
        body["width"] = int(width)
    if height is not None:
        body["height"] = int(height)

    url = f"{CF_API_BASE}/accounts/{_cf_account_id()}/ai/run/{model}"
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {_cf_token()}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=180,
        )
    except requests.Timeout:
        return _err(f"Workers AI image request timed out after 180s (model={model})")
    except requests.ConnectionError as exc:
        return _err(f"Workers AI connection error: {exc}")
    except requests.RequestException as exc:
        return _err(f"Workers AI request failed: {exc}")

    if not resp.ok:
        return _err(
            f"Workers AI HTTP {resp.status_code}: {resp.text[:300]}",
            status=resp.status_code,
        )

    b64 = _extract_workers_ai_image(resp)
    if not b64:
        return _err(f"Workers AI returned no image data (model={model})")

    try:
        from agent.image_gen_provider import save_b64_image
        saved = save_b64_image(
            b64,
            prefix=f"cf_{model.replace('/', '_').replace('@', '')}",
        )
        return _ok({"model": model, "image": str(saved), "format": "file"})
    except Exception as exc:
        logger.warning("save_b64_image failed (%s) — returning raw base64", exc)
        return _ok({"model": model, "image_b64": b64, "format": "base64"})


def _extract_workers_ai_image(resp: requests.Response) -> Optional[str]:
    """Pull the base64-encoded image out of a Workers AI response.

    Some image models return ``{"result": {"image": "<b64>"}}`` while others
    return the PNG bytes directly with a binary content type. Handle both.
    """
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            data = resp.json()
        except Exception:
            return None
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict):
            img = result.get("image")
            if isinstance(img, str) and img:
                return img
        return None
    if resp.content:
        return base64.b64encode(resp.content).decode("ascii")
    return None


# ===========================================================================
# KV — key/value store
# ===========================================================================


def _kv_namespace(explicit: Optional[str]) -> Optional[str]:
    return _resolve_id(explicit, "CLOUDFLARE_KV_NAMESPACE_ID")


def _kv_put(
    namespace_id: Optional[str],
    key: str,
    value: str,
    *,
    expiration_ttl: Optional[int] = None,
) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    ns = _kv_namespace(namespace_id)
    if not ns:
        return _err("namespace_id is required (or set CLOUDFLARE_KV_NAMESPACE_ID)")
    if not key:
        return _err("'key' is required")

    params: Dict[str, Any] = {}
    if expiration_ttl:
        params["expiration_ttl"] = int(expiration_ttl)

    res = _cf_request(
        "PUT",
        f"/accounts/{_cf_account_id()}/storage/kv/namespaces/{ns}/values/{key}",
        params=params,
        data=value.encode("utf-8") if isinstance(value, str) else value,
        headers_extra={"Content-Type": "text/plain"},
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"namespace_id": ns, "key": key, "stored": True})


def _kv_get(namespace_id: Optional[str], key: str) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    ns = _kv_namespace(namespace_id)
    if not ns:
        return _err("namespace_id is required (or set CLOUDFLARE_KV_NAMESPACE_ID)")
    if not key:
        return _err("'key' is required")

    url = (
        f"{CF_API_BASE}/accounts/{_cf_account_id()}"
        f"/storage/kv/namespaces/{ns}/values/{key}"
    )
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {_cf_token()}"},
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        return _err(f"KV get failed: {exc}")
    if resp.status_code == 404:
        return _ok({"namespace_id": ns, "key": key, "value": None, "found": False})
    if not resp.ok:
        return _err(
            f"KV get HTTP {resp.status_code}: {resp.text[:300]}",
            status=resp.status_code,
        )
    return _ok({"namespace_id": ns, "key": key, "value": resp.text, "found": True})


def _kv_delete(namespace_id: Optional[str], key: str) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    ns = _kv_namespace(namespace_id)
    if not ns:
        return _err("namespace_id is required (or set CLOUDFLARE_KV_NAMESPACE_ID)")
    if not key:
        return _err("'key' is required")
    res = _cf_request(
        "DELETE",
        f"/accounts/{_cf_account_id()}/storage/kv/namespaces/{ns}/values/{key}",
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"namespace_id": ns, "key": key, "deleted": True})


def _kv_list(
    namespace_id: Optional[str],
    prefix: Optional[str] = None,
    limit: Optional[int] = None,
) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    ns = _kv_namespace(namespace_id)
    if not ns:
        return _err("namespace_id is required (or set CLOUDFLARE_KV_NAMESPACE_ID)")
    params: Dict[str, Any] = {}
    if prefix:
        params["prefix"] = prefix
    if limit:
        params["limit"] = int(limit)
    res = _cf_request(
        "GET",
        f"/accounts/{_cf_account_id()}/storage/kv/namespaces/{ns}/keys",
        params=params,
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"namespace_id": ns, "keys": res["result"]})


# ===========================================================================
# R2 — object storage
# ===========================================================================
#
# Read/write/delete use the S3-compatible endpoint when an access-key pair is
# configured (preferred — supports binary uploads, presigning, multipart).
# Listing falls back to the Cloudflare REST API when boto3 isn't installed.


def _r2_bucket(explicit: Optional[str]) -> Optional[str]:
    return _resolve_id(explicit, "CLOUDFLARE_R2_BUCKET")


def _r2_s3_endpoint() -> str:
    return f"https://{_cf_account_id()}.r2.cloudflarestorage.com"


def _r2_has_s3_credentials() -> bool:
    return bool(
        os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID")
        and os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
    )


def _r2_s3_client():
    """Return a boto3 S3 client targeting R2. Raises ImportError if boto3 missing."""
    import boto3  # type: ignore

    return boto3.client(
        "s3",
        endpoint_url=_r2_s3_endpoint(),
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _r2_creds_error() -> str:
    return _err(
        "R2 read/write requires CLOUDFLARE_R2_ACCESS_KEY_ID and "
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY (S3-compat credentials). Create them at "
        "https://dash.cloudflare.com/?to=/:account/r2/api-tokens."
    )


def _r2_put(
    bucket: Optional[str],
    key: str,
    content: str,
    *,
    content_type: Optional[str] = None,
    base64_input: bool = False,
) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    b = _r2_bucket(bucket)
    if not b:
        return _err("bucket is required (or set CLOUDFLARE_R2_BUCKET)")
    if not key:
        return _err("'key' is required")
    if not _r2_has_s3_credentials():
        return _r2_creds_error()
    try:
        body = base64.b64decode(content) if base64_input else content.encode("utf-8")
        client = _r2_s3_client()
        kwargs: Dict[str, Any] = {"Bucket": b, "Key": key, "Body": body}
        if content_type:
            kwargs["ContentType"] = content_type
        client.put_object(**kwargs)
    except ImportError:
        return _err("boto3 is required for R2 operations. Install: pip install boto3")
    except Exception as exc:
        return _err(f"R2 put failed: {exc}")
    return _ok({"bucket": b, "key": key, "size": len(body)})


def _r2_get(bucket: Optional[str], key: str, *, base64_output: bool = False) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    b = _r2_bucket(bucket)
    if not b:
        return _err("bucket is required (or set CLOUDFLARE_R2_BUCKET)")
    if not key:
        return _err("'key' is required")
    if not _r2_has_s3_credentials():
        return _r2_creds_error()
    try:
        client = _r2_s3_client()
        obj = client.get_object(Bucket=b, Key=key)
        body = obj["Body"].read()
    except ImportError:
        return _err("boto3 is required for R2 operations. Install: pip install boto3")
    except Exception as exc:
        return _err(f"R2 get failed: {exc}")
    if base64_output:
        return _ok({"bucket": b, "key": key, "content_b64": base64.b64encode(body).decode("ascii")})
    try:
        text = body.decode("utf-8")
        return _ok({"bucket": b, "key": key, "content": text})
    except UnicodeDecodeError:
        return _ok(
            {
                "bucket": b,
                "key": key,
                "content_b64": base64.b64encode(body).decode("ascii"),
                "note": "binary content returned as base64",
            }
        )


def _r2_delete(bucket: Optional[str], key: str) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    b = _r2_bucket(bucket)
    if not b:
        return _err("bucket is required (or set CLOUDFLARE_R2_BUCKET)")
    if not key:
        return _err("'key' is required")
    if not _r2_has_s3_credentials():
        return _r2_creds_error()
    try:
        client = _r2_s3_client()
        client.delete_object(Bucket=b, Key=key)
    except ImportError:
        return _err("boto3 is required for R2 operations. Install: pip install boto3")
    except Exception as exc:
        return _err(f"R2 delete failed: {exc}")
    return _ok({"bucket": b, "key": key, "deleted": True})


def _r2_list(
    bucket: Optional[str],
    prefix: Optional[str] = None,
    limit: Optional[int] = None,
) -> str:
    """List objects in an R2 bucket.

    Prefers the S3-compatible API (richer per-object metadata, pagination).
    Falls back to the Cloudflare REST objects endpoint when boto3 isn't
    installed so the tool still works in a vanilla environment.
    """
    if not _check_cf_requirements():
        return _missing_credentials_error()
    b = _r2_bucket(bucket)
    if not b:
        return _err("bucket is required (or set CLOUDFLARE_R2_BUCKET)")

    if _r2_has_s3_credentials():
        try:
            client = _r2_s3_client()
            kwargs: Dict[str, Any] = {"Bucket": b}
            if prefix:
                kwargs["Prefix"] = prefix
            if limit:
                kwargs["MaxKeys"] = int(limit)
            resp = client.list_objects_v2(**kwargs)
            objs = [
                {
                    "key": o["Key"],
                    "size": o.get("Size"),
                    "last_modified": str(o.get("LastModified")),
                }
                for o in resp.get("Contents", [])
            ]
            return _ok({"bucket": b, "objects": objs, "count": len(objs)})
        except ImportError:
            pass  # fall through to REST listing
        except Exception as exc:
            return _err(f"R2 list failed: {exc}")

    params: Dict[str, Any] = {}
    if prefix:
        params["prefix"] = prefix
    if limit:
        params["per_page"] = int(limit)
    res = _cf_request(
        "GET",
        f"/accounts/{_cf_account_id()}/r2/buckets/{b}/objects",
        params=params,
    )
    if not res["ok"]:
        return _err(res["error"])
    payload = res["result"] or {}
    raw_objs = payload if isinstance(payload, list) else (payload.get("result") or [])
    objs = [
        {
            "key": o.get("key"),
            "size": o.get("size"),
            "last_modified": o.get("uploaded") or o.get("last_modified"),
        }
        for o in raw_objs
        if isinstance(o, dict)
    ]
    return _ok({"bucket": b, "objects": objs, "count": len(objs)})


# ===========================================================================
# D1 — serverless SQLite
# ===========================================================================


def _d1_db(explicit: Optional[str]) -> Optional[str]:
    return _resolve_id(explicit, "CLOUDFLARE_D1_DATABASE_ID")


def _d1_query(
    database_id: Optional[str],
    sql: str,
    params: Optional[List[Any]] = None,
) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    db = _d1_db(database_id)
    if not db:
        return _err("database_id is required (or set CLOUDFLARE_D1_DATABASE_ID)")
    if not sql:
        return _err("'sql' is required")
    body: Dict[str, Any] = {"sql": sql}
    if params is not None:
        body["params"] = params
    res = _cf_request(
        "POST",
        f"/accounts/{_cf_account_id()}/d1/database/{db}/query",
        json_body=body,
        timeout=120,
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"database_id": db, "results": res["result"]})


# ===========================================================================
# Vectorize — vector database
# ===========================================================================


def _vectorize_index(explicit: Optional[str]) -> Optional[str]:
    return _resolve_id(explicit, "CLOUDFLARE_VECTORIZE_INDEX")


def _vectorize_query(
    index: Optional[str],
    vector: Optional[List[float]] = None,
    *,
    text: Optional[str] = None,
    top_k: int = 5,
    namespace: Optional[str] = None,
    filter_: Optional[Dict[str, Any]] = None,
    return_metadata: str = "all",
    return_values: bool = False,
) -> str:
    """Query Vectorize. Provide either ``vector`` or ``text`` (auto-embedded)."""
    if not _check_cf_requirements():
        return _missing_credentials_error()
    idx = _vectorize_index(index)
    if not idx:
        return _err("index is required (or set CLOUDFLARE_VECTORIZE_INDEX)")

    if vector is None and text:
        embed_resp = _workers_ai_embed(text)
        embed_payload = json.loads(embed_resp)
        if not embed_payload.get("ok"):
            return embed_resp
        data = embed_payload.get("data") or {}
        vectors_list = data.get("vectors") or []
        if not vectors_list:
            return _err("text embedding returned no vector")
        vector = vectors_list[0]

    if vector is None:
        return _err("either 'vector' or 'text' is required")

    body: Dict[str, Any] = {
        "vector": vector,
        "topK": int(top_k),
        "returnMetadata": return_metadata,
        "returnValues": bool(return_values),
    }
    if namespace:
        body["namespace"] = namespace
    if filter_:
        body["filter"] = filter_
    res = _cf_request(
        "POST",
        f"/accounts/{_cf_account_id()}/vectorize/v2/indexes/{idx}/query",
        json_body=body,
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"index": idx, "matches": res["result"]})


def _vectorize_upsert(index: Optional[str], vectors: List[Dict[str, Any]]) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    idx = _vectorize_index(index)
    if not idx:
        return _err("index is required (or set CLOUDFLARE_VECTORIZE_INDEX)")
    if not isinstance(vectors, list) or not vectors:
        return _err("'vectors' must be a non-empty list of {id, values, metadata?, namespace?}")

    ndjson = "\n".join(json.dumps(v, default=str) for v in vectors).encode("utf-8")
    res = _cf_request(
        "POST",
        f"/accounts/{_cf_account_id()}/vectorize/v2/indexes/{idx}/upsert",
        data=ndjson,
        headers_extra={"Content-Type": "application/x-ndjson"},
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"index": idx, "result": res["result"]})


# ===========================================================================
# AI Search — managed RAG (ex AutoRAG)
# ===========================================================================
#
# Cloudflare migrated the AutoRAG REST API to AI Search on 2026-03-23. The new
# canonical paths are ``/ai-search/instances/{name}/{chat/completions,search}``
# and accept OpenAI-style ``messages``. We post the user's query as a single
# user message; callers wanting multi-turn pass ``messages`` explicitly.


def _ai_search_id(explicit: Optional[str]) -> Optional[str]:
    return _resolve_id(explicit, "CLOUDFLARE_AI_SEARCH_ID")


def _ai_search_query(
    ai_search_id: Optional[str],
    query: Optional[str],
    *,
    messages: Optional[List[Dict[str, Any]]] = None,
    rewrite_query: bool = False,
    max_num_results: Optional[int] = None,
    ranking_options: Optional[Dict[str, Any]] = None,
    answer: bool = True,
) -> str:
    """Query an AI Search instance.

    ``answer=True`` (default) calls ``/chat/completions`` and returns the
    LLM-synthesized answer with cited chunks. ``answer=False`` calls
    ``/search`` and returns only the retrieved chunks.
    """
    if not _check_cf_requirements():
        return _missing_credentials_error()
    sid = _ai_search_id(ai_search_id)
    if not sid:
        return _err("ai_search_id is required (or set CLOUDFLARE_AI_SEARCH_ID)")
    if not messages and not query:
        return _err("either 'query' or 'messages' is required")

    msgs: List[Dict[str, Any]] = (
        messages if isinstance(messages, list) and messages
        else [{"role": "user", "content": query}]
    )

    endpoint = "chat/completions" if answer else "search"
    body: Dict[str, Any] = {"messages": msgs, "rewrite_query": bool(rewrite_query)}
    if max_num_results is not None:
        body["max_num_results"] = int(max_num_results)
    if ranking_options:
        body["ranking_options"] = ranking_options

    res = _cf_request(
        "POST",
        f"/accounts/{_cf_account_id()}/ai-search/instances/{sid}/{endpoint}",
        json_body=body,
        timeout=120,
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"ai_search_id": sid, "answer": answer, "result": res["result"]})


# ===========================================================================
# Browser Rendering — REST API
# ===========================================================================


def _browser_call(
    endpoint: str,
    *,
    url: Optional[str] = None,
    html: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    binary: bool = False,
) -> Dict[str, Any]:
    if not _check_cf_requirements():
        return {"ok": False, "error": "missing CF credentials"}
    if not url and not html:
        return {"ok": False, "error": "either 'url' or 'html' is required"}

    body: Dict[str, Any] = {}
    if url:
        body["url"] = url
    if html:
        body["html"] = html
    if extra:
        body.update(extra)

    api_url = (
        f"{CF_API_BASE}/accounts/{_cf_account_id()}/browser-rendering/{endpoint}"
    )
    try:
        resp = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {_cf_token()}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": f"browser-rendering request failed: {exc}"}

    if not resp.ok:
        return {
            "ok": False,
            "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
            "status": resp.status_code,
        }

    if binary:
        return {
            "ok": True,
            "bytes": resp.content,
            "content_type": resp.headers.get("Content-Type", ""),
        }
    try:
        return {"ok": True, "result": resp.json()}
    except Exception:
        return {"ok": True, "result": {"raw": resp.text}}


def _browser_screenshot(
    url: Optional[str],
    html: Optional[str],
    full_page: bool = True,
    viewport_width: Optional[int] = None,
    viewport_height: Optional[int] = None,
) -> str:
    extra: Dict[str, Any] = {"screenshotOptions": {"fullPage": bool(full_page)}}
    if viewport_width or viewport_height:
        extra["viewport"] = {
            "width": int(viewport_width or 1280),
            "height": int(viewport_height or 800),
        }
    res = _browser_call("screenshot", url=url, html=html, extra=extra, binary=True)
    if not res["ok"]:
        return _err(res["error"])
    b64 = base64.b64encode(res["bytes"]).decode("ascii")
    try:
        from agent.image_gen_provider import save_b64_image
        path = save_b64_image(b64, prefix="cf_screenshot", extension="png")
        return _ok(
            {
                "path": str(path),
                "bytes": len(res["bytes"]),
                "content_type": res["content_type"],
            }
        )
    except Exception:
        return _ok(
            {
                "image_b64": b64,
                "bytes": len(res["bytes"]),
                "content_type": res["content_type"],
            }
        )


def _browser_pdf(url: Optional[str], html: Optional[str]) -> str:
    res = _browser_call("pdf", url=url, html=html, binary=True)
    if not res["ok"]:
        return _err(res["error"])
    out_dir = os.path.expanduser("~/.hermes/cache/cf_browser")
    os.makedirs(out_dir, exist_ok=True)
    digest = hashlib.sha1(res["bytes"]).hexdigest()[:12]
    path = os.path.join(out_dir, f"cf_pdf_{digest}.pdf")
    with open(path, "wb") as fp:
        fp.write(res["bytes"])
    return _ok({"path": path, "bytes": len(res["bytes"])})


def _browser_content(url: Optional[str], html: Optional[str]) -> str:
    res = _browser_call("content", url=url, html=html)
    if not res["ok"]:
        return _err(res["error"])
    return _ok(res["result"])


def _browser_markdown(url: Optional[str], html: Optional[str]) -> str:
    res = _browser_call("markdown", url=url, html=html)
    if not res["ok"]:
        return _err(res["error"])
    return _ok(res["result"])


def _browser_links(url: Optional[str]) -> str:
    res = _browser_call("links", url=url)
    if not res["ok"]:
        return _err(res["error"])
    return _ok(res["result"])


def _browser_scrape(url: str, elements: List[Dict[str, str]]) -> str:
    if not elements:
        return _err("'elements' is required (e.g. [{'selector': 'h1'}])")
    res = _browser_call("scrape", url=url, extra={"elements": elements})
    if not res["ok"]:
        return _err(res["error"])
    return _ok(res["result"])


# ===========================================================================
# Email — Cloudflare Email Service (Send)
# ===========================================================================
#
# Cloudflare Email Sending is in public beta as of 2026-04-16. The REST API
# is ``POST /accounts/{id}/email/sending/send`` with a flat top-level payload
# — *not* the OpenAI-style content array some other vendors use.


def _email_send(
    to: Any,
    subject: str,
    *,
    text: Optional[str] = None,
    html: Optional[str] = None,
    from_address: Optional[str] = None,
    reply_to: Optional[str] = None,
    cc: Any = None,
    bcc: Any = None,
) -> str:
    if not _check_cf_requirements():
        return _missing_credentials_error()
    if not to:
        return _err("'to' is required")
    if not subject:
        return _err("'subject' is required")
    if not text and not html:
        return _err("either 'text' or 'html' is required")

    sender = _resolve_id(from_address, "CLOUDFLARE_EMAIL_FROM")
    if not sender:
        return _err("'from_address' is required (or set CLOUDFLARE_EMAIL_FROM)")

    def _coerce(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return v
        items = [str(x) for x in v]
        if len(items) == 1:
            return items[0]
        return items

    body: Dict[str, Any] = {
        "from": sender,
        "to": _coerce(to),
        "subject": subject,
    }
    if text:
        body["text"] = text
    if html:
        body["html"] = html
    if reply_to:
        body["reply_to"] = reply_to
    cc_v = _coerce(cc)
    if cc_v:
        body["cc"] = cc_v
    bcc_v = _coerce(bcc)
    if bcc_v:
        body["bcc"] = bcc_v

    res = _cf_request(
        "POST",
        f"/accounts/{_cf_account_id()}/email/sending/send",
        json_body=body,
    )
    if not res["ok"]:
        return _err(res["error"])
    return _ok({"sent": True, "result": res["result"]})


# ===========================================================================
# Schemas + registration
# ===========================================================================

WORKERS_AI_CHAT_SCHEMA = {
    "name": "cloudflare_workers_ai_chat",
    "description": (
        "Run a chat completion against Cloudflare Workers AI (Llama, Qwen, "
        "DeepSeek, Mistral, GPT-OSS, etc.). Routes through AI Gateway when "
        "CLOUDFLARE_GATEWAY_ID is set for caching and observability. Use for "
        "cheap auxiliary calls or to keep all inference inside Cloudflare's network."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": (
                    "Workers AI model id, e.g. '@cf/meta/llama-4-scout-17b-16e-instruct', "
                    "'@cf/openai/gpt-oss-120b', or '@cf/qwen/qwen3-30b-a3b-fp8'"
                ),
            },
            "messages": {
                "type": "array",
                "items": {"type": "object"},
                "description": "OpenAI-format messages: [{role, content}, ...]",
            },
            "max_tokens": {"type": "integer"},
            "temperature": {"type": "number"},
            "gateway_id": {
                "type": "string",
                "description": "AI Gateway slug (overrides CLOUDFLARE_GATEWAY_ID env)",
            },
        },
        "required": ["model", "messages"],
    },
}

WORKERS_AI_EMBED_SCHEMA = {
    "name": "cloudflare_workers_ai_embed",
    "description": (
        "Generate text embeddings via Workers AI. Default model is bge-m3 "
        "(multilingual, 1024d)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"description": "Text or list of strings to embed"},
            "model": {
                "type": "string",
                "description": f"Embedding model id (default '{DEFAULT_EMBED_MODEL}')",
            },
        },
        "required": ["text"],
    },
}

WORKERS_AI_IMAGE_SCHEMA = {
    "name": "cloudflare_image_generate",
    "description": (
        "Generate an image via Workers AI. Defaults to FLUX.1 [schnell] "
        "(fast, free-tier friendly). Other options: "
        "'@cf/black-forest-labs/flux-2-klein-9b' (higher quality), "
        "'@cf/black-forest-labs/flux-2-klein-4b' (faster/cheaper FLUX.2), "
        "'@cf/black-forest-labs/flux-2-dev' (highest fidelity), "
        "'@cf/leonardo/phoenix-1.0', '@cf/leonardo/lucid-origin', "
        "'@cf/bytedance/stable-diffusion-xl-lightning'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "model": {"type": "string"},
            "steps": {"type": "integer"},
            "seed": {"type": "integer"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
        "required": ["prompt"],
    },
}

KV_PUT_SCHEMA = {
    "name": "cloudflare_kv_put",
    "description": (
        "Write a value to a Cloudflare KV namespace. namespace_id falls back "
        "to CLOUDFLARE_KV_NAMESPACE_ID."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "namespace_id": {"type": "string"},
            "key": {"type": "string"},
            "value": {"type": "string"},
            "expiration_ttl": {
                "type": "integer",
                "description": "Seconds until automatic expiration",
            },
        },
        "required": ["key", "value"],
    },
}

KV_GET_SCHEMA = {
    "name": "cloudflare_kv_get",
    "description": "Read a value from a Cloudflare KV namespace.",
    "parameters": {
        "type": "object",
        "properties": {
            "namespace_id": {"type": "string"},
            "key": {"type": "string"},
        },
        "required": ["key"],
    },
}

KV_DELETE_SCHEMA = {
    "name": "cloudflare_kv_delete",
    "description": "Delete a key from a Cloudflare KV namespace.",
    "parameters": {
        "type": "object",
        "properties": {
            "namespace_id": {"type": "string"},
            "key": {"type": "string"},
        },
        "required": ["key"],
    },
}

KV_LIST_SCHEMA = {
    "name": "cloudflare_kv_list",
    "description": "List keys in a Cloudflare KV namespace.",
    "parameters": {
        "type": "object",
        "properties": {
            "namespace_id": {"type": "string"},
            "prefix": {"type": "string"},
            "limit": {"type": "integer"},
        },
    },
}

R2_PUT_SCHEMA = {
    "name": "cloudflare_r2_put",
    "description": (
        "Upload an object to a Cloudflare R2 bucket via the S3-compatible API. "
        "Requires CLOUDFLARE_R2_ACCESS_KEY_ID and CLOUDFLARE_R2_SECRET_ACCESS_KEY."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "key": {"type": "string"},
            "content": {"type": "string"},
            "content_type": {"type": "string"},
            "base64_input": {
                "type": "boolean",
                "description": "Set true if 'content' is base64-encoded binary",
            },
        },
        "required": ["key", "content"],
    },
}

R2_GET_SCHEMA = {
    "name": "cloudflare_r2_get",
    "description": "Download an object from a Cloudflare R2 bucket.",
    "parameters": {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "key": {"type": "string"},
            "base64_output": {
                "type": "boolean",
                "description": "Set true to always return base64 (default: try utf-8)",
            },
        },
        "required": ["key"],
    },
}

R2_DELETE_SCHEMA = {
    "name": "cloudflare_r2_delete",
    "description": "Delete an object from a Cloudflare R2 bucket.",
    "parameters": {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "key": {"type": "string"},
        },
        "required": ["key"],
    },
}

R2_LIST_SCHEMA = {
    "name": "cloudflare_r2_list",
    "description": "List objects in a Cloudflare R2 bucket.",
    "parameters": {
        "type": "object",
        "properties": {
            "bucket": {"type": "string"},
            "prefix": {"type": "string"},
            "limit": {"type": "integer"},
        },
    },
}

D1_QUERY_SCHEMA = {
    "name": "cloudflare_d1_query",
    "description": (
        "Run a SQL statement against a Cloudflare D1 database. Supports "
        "SELECT/INSERT/UPDATE/DELETE/DDL. Use parameterized queries with "
        "'?1, ?2, ...' placeholders. FTS5, JSON and math extensions are "
        "available."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "database_id": {"type": "string"},
            "sql": {"type": "string"},
            "params": {"type": "array", "items": {}},
        },
        "required": ["sql"],
    },
}

VECTORIZE_QUERY_SCHEMA = {
    "name": "cloudflare_vectorize_query",
    "description": (
        "Query a Cloudflare Vectorize index. Provide either a precomputed "
        "'vector' or a 'text' string (auto-embedded via Workers AI bge-m3)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "index": {"type": "string"},
            "vector": {"type": "array", "items": {"type": "number"}},
            "text": {"type": "string"},
            "top_k": {"type": "integer"},
            "namespace": {"type": "string"},
            "filter": {"type": "object"},
            "return_metadata": {
                "type": "string",
                "enum": ["none", "indexed", "all"],
            },
            "return_values": {"type": "boolean"},
        },
    },
}

VECTORIZE_UPSERT_SCHEMA = {
    "name": "cloudflare_vectorize_upsert",
    "description": "Insert or update vectors in a Cloudflare Vectorize index.",
    "parameters": {
        "type": "object",
        "properties": {
            "index": {"type": "string"},
            "vectors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "values": {"type": "array", "items": {"type": "number"}},
                        "metadata": {"type": "object"},
                        "namespace": {"type": "string"},
                    },
                    "required": ["id", "values"],
                },
            },
        },
        "required": ["vectors"],
    },
}

AI_SEARCH_SCHEMA = {
    "name": "cloudflare_ai_search",
    "description": (
        "Query a Cloudflare AI Search (ex-AutoRAG) instance. Returns either a "
        "synthesized answer with cited chunks (answer=true, default) or just "
        "the retrieved chunks (answer=false). Uses the new "
        "/ai-search/instances/{name}/{chat/completions,search} API."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ai_search_id": {"type": "string"},
            "query": {"type": "string"},
            "messages": {
                "type": "array",
                "items": {"type": "object"},
                "description": "OpenAI-format messages (overrides 'query' for multi-turn).",
            },
            "answer": {"type": "boolean"},
            "rewrite_query": {"type": "boolean"},
            "max_num_results": {"type": "integer"},
        },
    },
}

BROWSER_SCREENSHOT_SCHEMA = {
    "name": "cloudflare_browser_screenshot",
    "description": "Render a webpage and return a PNG screenshot. Requires url OR html.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "html": {"type": "string"},
            "full_page": {"type": "boolean"},
            "viewport_width": {"type": "integer"},
            "viewport_height": {"type": "integer"},
        },
    },
}

BROWSER_PDF_SCHEMA = {
    "name": "cloudflare_browser_pdf",
    "description": "Render a webpage as a PDF. Returns a local file path.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "html": {"type": "string"},
        },
    },
}

BROWSER_CONTENT_SCHEMA = {
    "name": "cloudflare_browser_content",
    "description": "Fetch the fully rendered HTML of a page (executes JS).",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "html": {"type": "string"},
        },
    },
}

BROWSER_MARKDOWN_SCHEMA = {
    "name": "cloudflare_browser_markdown",
    "description": "Fetch a page and return Cloudflare's clean Markdown extraction.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "html": {"type": "string"},
        },
    },
}

BROWSER_LINKS_SCHEMA = {
    "name": "cloudflare_browser_links",
    "description": "Extract all hyperlinks from a page.",
    "parameters": {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
}

BROWSER_SCRAPE_SCHEMA = {
    "name": "cloudflare_browser_scrape",
    "description": "Scrape elements matching CSS selectors. 'elements' is a list of {selector}.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "elements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"selector": {"type": "string"}},
                    "required": ["selector"],
                },
            },
        },
        "required": ["url", "elements"],
    },
}

EMAIL_SEND_SCHEMA = {
    "name": "cloudflare_email_send",
    "description": (
        "Send a transactional email via Cloudflare Email Sending (public beta, "
        "Workers Paid plan). The sender domain must be verified in your "
        "Cloudflare account. Recipients can be a string or list of strings."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "to": {"description": "Recipient email or list of emails"},
            "subject": {"type": "string"},
            "text": {"type": "string"},
            "html": {"type": "string"},
            "from_address": {
                "type": "string",
                "description": "Sender (defaults to CLOUDFLARE_EMAIL_FROM)",
            },
            "reply_to": {"type": "string"},
            "cc": {"description": "string or list"},
            "bcc": {"description": "string or list"},
        },
        "required": ["to", "subject"],
    },
}


# Handler wrappers — keep arg extraction obvious and explicit.

def _h_workers_ai_chat(args, **_kw):
    return _workers_ai_chat(
        model=args.get("model", ""),
        messages=args.get("messages") or [],
        max_tokens=args.get("max_tokens"),
        temperature=args.get("temperature"),
        gateway_id=args.get("gateway_id"),
    )


def _h_workers_ai_embed(args, **_kw):
    return _workers_ai_embed(
        text=args.get("text"),
        model=args.get("model") or DEFAULT_EMBED_MODEL,
    )


def _h_image_generate(args, **_kw):
    return _workers_ai_image(
        prompt=args.get("prompt", ""),
        model=args.get("model") or DEFAULT_IMAGE_MODEL,
        steps=args.get("steps"),
        seed=args.get("seed"),
        width=args.get("width"),
        height=args.get("height"),
    )


def _h_kv_put(args, **_kw):
    return _kv_put(
        namespace_id=args.get("namespace_id"),
        key=args.get("key", ""),
        value=args.get("value", ""),
        expiration_ttl=args.get("expiration_ttl"),
    )


def _h_kv_get(args, **_kw):
    return _kv_get(namespace_id=args.get("namespace_id"), key=args.get("key", ""))


def _h_kv_delete(args, **_kw):
    return _kv_delete(namespace_id=args.get("namespace_id"), key=args.get("key", ""))


def _h_kv_list(args, **_kw):
    return _kv_list(
        namespace_id=args.get("namespace_id"),
        prefix=args.get("prefix"),
        limit=args.get("limit"),
    )


def _h_r2_put(args, **_kw):
    return _r2_put(
        bucket=args.get("bucket"),
        key=args.get("key", ""),
        content=args.get("content", ""),
        content_type=args.get("content_type"),
        base64_input=bool(args.get("base64_input", False)),
    )


def _h_r2_get(args, **_kw):
    return _r2_get(
        bucket=args.get("bucket"),
        key=args.get("key", ""),
        base64_output=bool(args.get("base64_output", False)),
    )


def _h_r2_delete(args, **_kw):
    return _r2_delete(bucket=args.get("bucket"), key=args.get("key", ""))


def _h_r2_list(args, **_kw):
    return _r2_list(
        bucket=args.get("bucket"),
        prefix=args.get("prefix"),
        limit=args.get("limit"),
    )


def _h_d1_query(args, **_kw):
    return _d1_query(
        database_id=args.get("database_id"),
        sql=args.get("sql", ""),
        params=args.get("params"),
    )


def _h_vectorize_query(args, **_kw):
    return _vectorize_query(
        index=args.get("index"),
        vector=args.get("vector"),
        text=args.get("text"),
        top_k=int(args.get("top_k", 5)),
        namespace=args.get("namespace"),
        filter_=args.get("filter"),
        return_metadata=args.get("return_metadata", "all"),
        return_values=bool(args.get("return_values", False)),
    )


def _h_vectorize_upsert(args, **_kw):
    return _vectorize_upsert(index=args.get("index"), vectors=args.get("vectors") or [])


def _h_ai_search(args, **_kw):
    return _ai_search_query(
        ai_search_id=args.get("ai_search_id"),
        query=args.get("query"),
        messages=args.get("messages"),
        rewrite_query=bool(args.get("rewrite_query", False)),
        max_num_results=args.get("max_num_results"),
        ranking_options=args.get("ranking_options"),
        answer=bool(args.get("answer", True)),
    )


def _h_browser_screenshot(args, **_kw):
    return _browser_screenshot(
        url=args.get("url"),
        html=args.get("html"),
        full_page=bool(args.get("full_page", True)),
        viewport_width=args.get("viewport_width"),
        viewport_height=args.get("viewport_height"),
    )


def _h_browser_pdf(args, **_kw):
    return _browser_pdf(url=args.get("url"), html=args.get("html"))


def _h_browser_content(args, **_kw):
    return _browser_content(url=args.get("url"), html=args.get("html"))


def _h_browser_markdown(args, **_kw):
    return _browser_markdown(url=args.get("url"), html=args.get("html"))


def _h_browser_links(args, **_kw):
    return _browser_links(url=args.get("url"))


def _h_browser_scrape(args, **_kw):
    return _browser_scrape(url=args.get("url", ""), elements=args.get("elements") or [])


def _h_email_send(args, **_kw):
    return _email_send(
        to=args.get("to") or [],
        subject=args.get("subject", ""),
        text=args.get("text"),
        html=args.get("html"),
        from_address=args.get("from_address"),
        reply_to=args.get("reply_to"),
        cc=args.get("cc"),
        bcc=args.get("bcc"),
    )


# Registration — toolset "cloudflare", availability gated by env vars.

_REQUIRES = ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"]

registry.register(name="cloudflare_workers_ai_chat", toolset=TOOLSET, schema=WORKERS_AI_CHAT_SCHEMA, handler=_h_workers_ai_chat, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🤖")
registry.register(name="cloudflare_workers_ai_embed", toolset=TOOLSET, schema=WORKERS_AI_EMBED_SCHEMA, handler=_h_workers_ai_embed, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="📐")
registry.register(name="cloudflare_image_generate", toolset=TOOLSET, schema=WORKERS_AI_IMAGE_SCHEMA, handler=_h_image_generate, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🎨")

registry.register(name="cloudflare_kv_put", toolset=TOOLSET, schema=KV_PUT_SCHEMA, handler=_h_kv_put, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🗝️")
registry.register(name="cloudflare_kv_get", toolset=TOOLSET, schema=KV_GET_SCHEMA, handler=_h_kv_get, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🗝️")
registry.register(name="cloudflare_kv_delete", toolset=TOOLSET, schema=KV_DELETE_SCHEMA, handler=_h_kv_delete, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🗑️")
registry.register(name="cloudflare_kv_list", toolset=TOOLSET, schema=KV_LIST_SCHEMA, handler=_h_kv_list, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="📜")

registry.register(name="cloudflare_r2_put", toolset=TOOLSET, schema=R2_PUT_SCHEMA, handler=_h_r2_put, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="☁️")
registry.register(name="cloudflare_r2_get", toolset=TOOLSET, schema=R2_GET_SCHEMA, handler=_h_r2_get, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="☁️", max_result_size_chars=2_000_000)
registry.register(name="cloudflare_r2_delete", toolset=TOOLSET, schema=R2_DELETE_SCHEMA, handler=_h_r2_delete, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🗑️")
registry.register(name="cloudflare_r2_list", toolset=TOOLSET, schema=R2_LIST_SCHEMA, handler=_h_r2_list, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="📜")

registry.register(name="cloudflare_d1_query", toolset=TOOLSET, schema=D1_QUERY_SCHEMA, handler=_h_d1_query, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🗃️", max_result_size_chars=500_000)

registry.register(name="cloudflare_vectorize_query", toolset=TOOLSET, schema=VECTORIZE_QUERY_SCHEMA, handler=_h_vectorize_query, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🧭")
registry.register(name="cloudflare_vectorize_upsert", toolset=TOOLSET, schema=VECTORIZE_UPSERT_SCHEMA, handler=_h_vectorize_upsert, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🧭")

registry.register(name="cloudflare_ai_search", toolset=TOOLSET, schema=AI_SEARCH_SCHEMA, handler=_h_ai_search, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🔍", max_result_size_chars=200_000)

registry.register(name="cloudflare_browser_screenshot", toolset=TOOLSET, schema=BROWSER_SCREENSHOT_SCHEMA, handler=_h_browser_screenshot, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="📸")
registry.register(name="cloudflare_browser_pdf", toolset=TOOLSET, schema=BROWSER_PDF_SCHEMA, handler=_h_browser_pdf, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="📄")
registry.register(name="cloudflare_browser_content", toolset=TOOLSET, schema=BROWSER_CONTENT_SCHEMA, handler=_h_browser_content, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🌐", max_result_size_chars=500_000)
registry.register(name="cloudflare_browser_markdown", toolset=TOOLSET, schema=BROWSER_MARKDOWN_SCHEMA, handler=_h_browser_markdown, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="📝", max_result_size_chars=500_000)
registry.register(name="cloudflare_browser_links", toolset=TOOLSET, schema=BROWSER_LINKS_SCHEMA, handler=_h_browser_links, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🔗")
registry.register(name="cloudflare_browser_scrape", toolset=TOOLSET, schema=BROWSER_SCRAPE_SCHEMA, handler=_h_browser_scrape, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="🕸️")

registry.register(name="cloudflare_email_send", toolset=TOOLSET, schema=EMAIL_SEND_SCHEMA, handler=_h_email_send, check_fn=_check_cf_requirements, requires_env=_REQUIRES, emoji="✉️")
