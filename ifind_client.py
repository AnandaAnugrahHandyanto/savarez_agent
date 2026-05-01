#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal IFIND client for Hermes.

Current scope:
- hold refresh/access token from env or explicit arg
- decode refresh token metadata locally
- perform real HTTP refresh/access-token calls against the public iFinD HTTP API
- expose probe() output for safe diagnostics
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, TypedDict

import requests

IFIND_REFRESH_TOKEN_ENV = "IFIND_REFRESH_TOKEN"
IFIND_ACCESS_TOKEN_ENV = "IFIND_ACCESS_TOKEN"
IFIND_BASE_URL_ENV = "IFIND_BASE_URL"
SMART_STOCK_PICKING_TYPE_STOCK = "stock"
DEFAULT_TIMEOUT = 20
DEFAULT_BASE_URL = "https://quantapi.51ifind.com/api/v1"
TOKEN_EXPIRED_CODES = {-1003, -1300, -1302}


class IFINDBasicIndicator(TypedDict):
    indicator: str
    indiparams: list[Any]


@dataclass
class IFINDConfig:
    refresh_token: str = ""
    access_token: str = ""
    base_url: str = DEFAULT_BASE_URL
    timeout: int = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls) -> "IFINDConfig":
        return cls(
            refresh_token=os.getenv(IFIND_REFRESH_TOKEN_ENV, "").strip(),
            access_token=os.getenv(IFIND_ACCESS_TOKEN_ENV, "").strip(),
            base_url=os.getenv(IFIND_BASE_URL_ENV, DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
            timeout=DEFAULT_TIMEOUT,
        )


class IFINDClient:
    def __init__(self, config: IFINDConfig | None = None):
        self.config = config or IFINDConfig.from_env()

    @staticmethod
    def decode_refresh_token(refresh_token: str) -> dict[str, Any]:
        parts = (refresh_token or "").split(".")
        if len(parts) < 3:
            return {"valid_structure": False, "reason": "token_parts_lt_3"}
        decoded: dict[str, Any] = {"valid_structure": True}
        for idx, part in enumerate(parts[:2], start=1):
            try:
                pad = "=" * ((4 - len(part) % 4) % 4)
                raw = base64.b64decode(part + pad).decode("utf-8")
                decoded[f"part_{idx}"] = json.loads(raw)
            except Exception as exc:
                decoded[f"part_{idx}_error"] = str(exc)
        decoded["signature"] = parts[2]
        user = decoded.get("part_2", {}).get("user", {}) if isinstance(decoded.get("part_2"), dict) else {}
        expire_text = user.get("refreshTokenExpiredTime")
        if expire_text:
            try:
                decoded["refresh_token_expired_time"] = expire_text
                decoded["refresh_token_expired"] = datetime.now() > datetime.strptime(expire_text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                decoded["refresh_token_expired_time"] = expire_text
        return decoded

    def token_metadata(self) -> dict[str, Any]:
        refresh = self.config.refresh_token
        if not refresh:
            return {"has_refresh_token": False}
        meta = self.decode_refresh_token(refresh)
        meta["has_refresh_token"] = True
        meta["has_access_token"] = bool(self.config.access_token)
        meta["has_base_url"] = bool(self.config.base_url)
        meta["base_url"] = self.config.base_url
        return meta

    def can_attempt_network(self) -> tuple[bool, str]:
        if not self.config.refresh_token:
            return False, "missing_refresh_token"
        if not self.config.base_url:
            return False, "missing_base_url"
        return True, "ok"

    def auth_headers(self, access_token: Optional[str] = None) -> dict[str, str]:
        token = access_token or self.config.access_token
        if not token:
            return {}
        return {
            "access_token": token,
            "Accept-Encoding": "gzip,deflate",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return self.config.base_url.rstrip("/") + "/" + path.lstrip("/")

    def _parse_json(self, response: requests.Response) -> dict[str, Any]:
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_access_token(payload: dict[str, Any]) -> str:
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict) and "access_token" in data:
            return str(data["access_token"])
        if "access_token" in payload:
            return str(payload["access_token"])
        raise ValueError(f"access_token not found in payload: {payload}")

    @staticmethod
    def _extract_error(payload: dict[str, Any]) -> tuple[int | None, str]:
        if not isinstance(payload, dict):
            return None, str(payload)
        if "errorcode" not in payload:
            return None, json.dumps(payload, ensure_ascii=False)[:500]
        return int(payload.get("errorcode", 0)), str(payload.get("errmsg", ""))

    def request(self, method: str, path: str, *, headers: Optional[dict[str, str]] = None, **kwargs: Any) -> requests.Response:
        url = self._url(path)
        merged_headers = {}
        merged_headers.update(self.auth_headers())
        if headers:
            merged_headers.update(headers)
        return requests.request(method=method.upper(), url=url, headers=merged_headers, timeout=self.config.timeout, **kwargs)

    def _request_json_with_access(self, path: str, payload: Optional[dict[str, Any]] = None, retry: bool = True) -> dict[str, Any]:
        access_token = self.config.access_token
        if not access_token:
            token_result = self.get_access_token()
            if not token_result.get("success"):
                return {
                    "success": False,
                    "path": path,
                    "reason": "access_token_failed",
                    "token_result": token_result,
                }
            access_token = self.config.access_token
        try:
            response = self.request("POST", path, json=payload or {})
            data = self._parse_json(response)
            errorcode, errmsg = self._extract_error(data)
            if errorcode in TOKEN_EXPIRED_CODES and retry:
                refresh = self.update_access_token()
                if refresh.get("success"):
                    return self._request_json_with_access(path, payload=payload, retry=False)
                return {
                    "success": False,
                    "path": path,
                    "reason": "token_refresh_failed",
                    "refresh": refresh,
                    "raw": data,
                }
            return {
                "success": errorcode in (None, 0),
                "path": path,
                "errorcode": errorcode,
                "errmsg": errmsg,
                "raw": data,
            }
        except Exception as exc:
            return {
                "success": False,
                "path": path,
                "reason": "request_failed",
                "error": str(exc),
            }

    def real_time_quotation(self, ths_codes: str, indicators: str, functionpara: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        payload = {
            "codes": ths_codes,
            "indicators": indicators,
        }
        if functionpara:
            payload["functionpara"] = functionpara
        return self._request_json_with_access("/real_time_quotation", payload)

    def data_pool(self, reportname: str, functionpara: dict[str, Any], outputpara: str) -> dict[str, Any]:
        payload = {
            "reportname": reportname,
            "functionpara": functionpara,
            "outputpara": outputpara,
        }
        return self._request_json_with_access("/data_pool", payload)

    def smart_stock_picking(self, searchstring: str, searchtype: str) -> dict[str, Any]:
        payload = {
            "searchstring": searchstring,
            "searchtype": searchtype,
        }
        return self._request_json_with_access("/smart_stock_picking", payload)

    def basic_data_service(self, ths_codes: str, indipara: list[IFINDBasicIndicator]) -> dict[str, Any]:
        payload = {
            "codes": ths_codes,
            "indipara": indipara,
        }
        return self._request_json_with_access("/basic_data_service", payload)

    def get_trade_dates(self, exchange: str = "SSE", startdate: Optional[str] = None, enddate: Optional[str] = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"exchange": exchange}
        if startdate:
            payload["startdate"] = startdate
        if enddate:
            payload["enddate"] = enddate
        return self._request_json_with_access("/get_trade_dates", payload)

    def get_data_volume(self) -> dict[str, Any]:
        return self._request_json_with_access("/get_data_volume", {})

    def report_query(self, outputpara: str, ths_codes: Optional[str] = None, functionpara: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        payload = {"outputpara": outputpara}
        if ths_codes:
            payload["codes"] = ths_codes
        if functionpara:
            payload["functionpara"] = functionpara
        return self._request_json_with_access("/report_query", payload)

    @staticmethod
    def extract_first_table_rows(result: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
        raw = result.get("raw") if isinstance(result, dict) else None
        if not isinstance(raw, dict):
            return []
        tables = raw.get("tables") or []
        if not tables:
            return []
        table = tables[0].get("table") if isinstance(tables[0], dict) else None
        if not isinstance(table, dict) or not table:
            return []
        cols = list(table.keys())
        row_count = max((len(v) for v in table.values() if isinstance(v, list)), default=0)
        rows = []
        for i in range(min(row_count, limit)):
            row = {}
            for col in cols:
                values = table.get(col)
                if isinstance(values, list) and i < len(values):
                    row[col] = values[i]
                else:
                    row[col] = None
            rows.append(row)
        return rows

    def get_access_token(self) -> dict[str, Any]:
        ok, reason = self.can_attempt_network()
        if not ok:
            return {"success": False, "reason": reason}
        url = self._url("/get_access_token")
        headers = {
            "Content-Type": "application/json",
            "refresh_token": self.config.refresh_token,
        }
        try:
            response = requests.post(url, headers=headers, json={}, timeout=self.config.timeout)
            payload = self._parse_json(response)
            errorcode, errmsg = self._extract_error(payload)
            token = self._extract_access_token(payload)
            self.config.access_token = token
            return {
                "success": errorcode in (None, 0),
                "url": url,
                "errorcode": errorcode,
                "errmsg": errmsg,
                "access_token_present": bool(token),
                "access_token_preview": (token[:12] + "...") if token else "",
                "raw": payload,
            }
        except Exception as exc:
            return {
                "success": False,
                "url": url,
                "reason": "request_failed",
                "error": str(exc),
            }

    def update_access_token(self) -> dict[str, Any]:
        ok, reason = self.can_attempt_network()
        if not ok:
            return {"success": False, "reason": reason}
        url = self._url("/update_access_token")
        headers = {
            "Content-Type": "application/json",
            "refresh_token": self.config.refresh_token,
        }
        try:
            response = requests.post(url, headers=headers, json={}, timeout=self.config.timeout)
            payload = self._parse_json(response)
            errorcode, errmsg = self._extract_error(payload)
            token = self._extract_access_token(payload)
            self.config.access_token = token
            return {
                "success": errorcode in (None, 0),
                "url": url,
                "errorcode": errorcode,
                "errmsg": errmsg,
                "access_token_present": bool(token),
                "access_token_preview": (token[:12] + "...") if token else "",
                "raw": payload,
            }
        except Exception as exc:
            return {
                "success": False,
                "url": url,
                "reason": "request_failed",
                "error": str(exc),
            }


    def ensure_access_token(self) -> dict[str, Any]:
        if self.config.access_token:
            return {
                "success": True,
                "reason": "already_present",
                "access_token_present": True,
                "access_token_preview": self.config.access_token[:12] + "...",
            }
        return self.get_access_token()

    def probe(self) -> dict[str, Any]:
        meta = self.token_metadata()
        ok, reason = self.can_attempt_network()
        return {
            "meta": meta,
            "can_attempt_network": ok,
            "reason": reason,
            "base_url": self.config.base_url,
        }
