"""File persistence for pharma compliance records.

Appends completed visit records to a JSON Lines file and archives
photos to a persistent directory.
"""

import fcntl
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent
RECORDS_DIR = PROJECT_DIR / "data" / "records"
PHOTOS_DIR = PROJECT_DIR / "data" / "photos"
GPS_CACHE_DIR = PROJECT_DIR / "data"
GPS_CACHE_FILE = GPS_CACHE_DIR / "gps_cache.json"

# ── GPS → 地址反向地理编码缓存 ──────────────────────────────────────────────

# 内存缓存，避免重复请求 API
_gps_cache: Dict[str, Optional[str]] = {}


def _load_gps_cache() -> Dict[str, Optional[str]]:
    """从磁盘加载 GPS 缓存（JSON 文件）。"""
    if not GPS_CACHE_FILE.exists():
        return {}
    try:
        with open(GPS_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Failed to load GPS cache: %s", e)
    return {}

# 模块加载时一次性将磁盘缓存读入内存，此后只写不读
_gps_cache.update(_load_gps_cache())


def _save_gps_cache(cache: Dict[str, Optional[str]]) -> None:
    """将 GPS 缓存原子写入磁盘 JSON 文件。"""
    try:
        GPS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = GPS_CACHE_FILE.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp_path, GPS_CACHE_FILE)
    except IOError as e:
        logger.warning("Failed to save GPS cache: %s", e)


def _gps_to_address(lat: float, lon: float) -> Optional[str]:
    """通过 photon.komoot.io 反向地理编码将 GPS 坐标转为中文地址。

    双重缓存策略：
    1. 内存 dict（进程生命周期内有效）
    2. 磁盘 JSON 文件（跨进程/跨重启持久化）

    Args:
        lat: 纬度（-90 ~ 90）
        lon: 经度（-180 ~ 180）

    Returns:
        格式化后的中文地址字符串，失败时返回 None。
    """
    # 缓存 key：四舍五入到小数点后 4 位（约 11 米精度，足够区分门店）
    cache_key = f"{lat:.4f},{lon:.4f}"

    # 1. 检查内存缓存（含模块加载时预载的磁盘数据）
    if cache_key in _gps_cache:
        logger.debug("GPS cache hit (memory): %s → %s", cache_key, _gps_cache[cache_key])
        return _gps_cache[cache_key]

    # 2. 调用 photon.komoot.io 反向地理编码 API
    try:
        url = f"https://photon.komoot.io/reverse?lat={lat}&lon={lon}&lang=zh"
        headers = {
            "User-Agent": "Hermes-PharmaCompliance/1.0 (reverse geocoding for compliance records)",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        features = data.get("features", [])
        if not features:
            logger.info("GPS reverse geocoding returned no results for %s", cache_key)
            address = None
        else:
            # 取第一条结果的 display_name
            properties = features[0].get("properties", {})
            display_name = properties.get("name", "")
            # 补充省市信息
            city = properties.get("city", "")
            state = properties.get("state", "")
            country = properties.get("country", "")

            # 本地化格式化：优先拼接省/市/具体地址
            parts = []
            if state and state != city:
                parts.append(state)
            if city:
                parts.append(city)
            if display_name and display_name not in parts:
                parts.append(display_name)

            address = "".join(parts) if parts else display_name
            if not address:
                address = None

            logger.info("GPS → 地址: %s → %s", cache_key, address)

    except requests.exceptions.Timeout:
        logger.warning("GPS reverse geocoding timed out for %s", cache_key)
        address = None
    except requests.exceptions.RequestException as e:
        logger.warning("GPS reverse geocoding request failed for %s: %s", cache_key, e)
        address = None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning("GPS reverse geocoding parse failed for %s: %s", cache_key, e)
        address = None
    except Exception as e:
        logger.error("Unexpected error in GPS reverse geocoding for %s: %s", cache_key, e)
        address = None

    # 3. 更新缓存（包括 None 值，避免重复请求失败的坐标）
    _gps_cache[cache_key] = address
    _save_gps_cache(_gps_cache)

    return address


def _extract_address_from_gps(image_path: str) -> Optional[str]:
    """从图片 EXIF 提取 GPS 坐标并反向地理编码为地址。

    端到端流程：图片 → EXIF GPS → 十进制经纬度 → 反向地理编码 → 中文地址。

    Args:
        image_path: 图片文件的绝对路径。

    Returns:
        格式化的中文地址字符串，无 GPS 数据或失败时返回 None。
    """
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS

        img = Image.open(image_path)
        exif_raw = img.getexif()
        if not exif_raw:
            logger.debug("No EXIF data in %s", image_path)
            return None

        # 提取 GPSInfo IFD
        gps_info = exif_raw.get_ifd(0x8825)  # GPSInfo IFD
        if not gps_info:
            logger.debug("No GPS info in EXIF for %s", image_path)
            return None

        # 解析 GPS 标签
        gps: Dict[str, Any] = {}
        for tag_id, value in gps_info.items():
            tag_name = GPSTAGS.get(tag_id, str(tag_id))
            gps[tag_name] = value

        # 提取经纬度及其参考方向
        lat_ref = gps.get("GPSLatitudeRef", "N")
        lat = gps.get("GPSLatitude")
        lon_ref = gps.get("GPSLongitudeRef", "E")
        lon = gps.get("GPSLongitude")

        if not lat or not lon:
            logger.debug("No GPS coordinates in EXIF for %s", image_path)
            return None

        # DMS → 十进制
        def _to_decimal(dms) -> float:
            if isinstance(dms, (tuple, list)) and len(dms) >= 3:
                return float(dms[0]) + float(dms[1]) / 60.0 + float(dms[2]) / 3600.0
            return float(dms)

        lat_dd = _to_decimal(lat)
        lon_dd = _to_decimal(lon)

        # 南半球/西半球取负值
        if lat_ref == "S":
            lat_dd = -lat_dd
        if lon_ref == "W":
            lon_dd = -lon_dd

        logger.info(
            "Extracted GPS from EXIF: lat=%.6f lon=%.6f → reverse geocoding",
            lat_dd, lon_dd,
        )

        return _gps_to_address(round(lat_dd, 6), round(lon_dd, 6))

    except ImportError:
        logger.debug("PIL/Pillow not available for EXIF GPS extraction")
        return None
    except Exception as e:
        logger.warning(
            "Failed to extract address from GPS for %s: %s", image_path, e
        )
        return None


def ensure_dirs() -> None:
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def save_record(task: Dict[str, Any], photo_paths: List[str]) -> str:
    """Persist a completed compliance record.

    Args:
        task: The merged task dict from _do_merge (contains fields, summary,
              warnings, message_count, merged_text).
        photo_paths: Absolute paths to photo files to archive.

    Returns:
        The record_id string (e.g. '20250617_153000_123_百姓大药房').
    """
    ensure_dirs()

    org_name = task.get("fields", {}).get("org_name", "unknown")
    # Sanitize org_name for filename
    safe_name = "".join(c for c in org_name if c.isalnum() or c in "._-()（）")[:30]
    # Use microseconds (truncated to 3-digit milliseconds) to avoid second-level collisions
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    record_id = f"{timestamp}_{safe_name}"

    # Copy photos — each photo wrapped in try/except so one bad file
    # doesn't block the entire record from being written
    saved_photos: List[str] = []
    for i, src in enumerate(photo_paths):
        try:
            if not src or not os.path.exists(src):
                continue
            ext = os.path.splitext(src)[1] or ".jpg"
            dst = PHOTOS_DIR / f"{record_id}_{i}{ext}"
            shutil.copy2(src, dst)
            saved_photos.append(str(dst))
        except Exception as e:
            logger.warning(
                "Failed to copy photo %s for record %s: %s", src, record_id, e
            )

    # Build persistent record
    persistent = {
        "record_id": record_id,
        "saved_at": datetime.now().isoformat(),
        "fields": task.get("fields", {}),
        "summary": task.get("summary", ""),
        "warnings": task.get("warnings", []),
        "message_count": task.get("message_count", 0),
        "merged_text": task.get("merged_text", ""),
        "photos": saved_photos,
    }

    # Append with exclusive file lock to prevent interleaved writes
    records_file = RECORDS_DIR / "records.jsonl"
    with open(records_file, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(persistent, ensure_ascii=False) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    logger.info(
        "Persisted record %s (%d photos, %d chars merged text)",
        record_id, len(saved_photos), len(task.get("merged_text", "")),
    )
    return record_id


def update_record(record_id: str, updated_fields: Dict[str, Any]) -> bool:
    """Update an existing record's fields in records.jsonl.

    Reads the entire JSONL file, finds the matching record_id,
    updates its fields, and rewrites the file atomically.

    Args:
        record_id: The record_id to update.
        updated_fields: New field values to merge into the record.

    Returns:
        True if the record was found and updated, False otherwise.
    """
    records_file = RECORDS_DIR / "records.jsonl"
    if not records_file.exists():
        logger.warning("update_record: records file not found")
        return False

    records: List[Dict[str, Any]] = []
    found = False
    with open(records_file, "r", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    records.append({"__raw__": line})
                    continue
                if record.get("record_id") == record_id:
                    # Merge updated_fields into existing fields
                    existing_fields = record.get("fields", {})
                    existing_fields.update(updated_fields)
                    record["fields"] = existing_fields
                    record["updated_at"] = datetime.now().isoformat()
                    # Rebuild summary
                    from pharma_compliance.extractor import fields_to_summary
                    record["summary"] = fields_to_summary(existing_fields)
                    found = True
                records.append(record)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    if not found:
        logger.warning("update_record: record_id %s not found", record_id)
        return False

    # Atomic write: write to temp, then rename
    tmp_path = records_file.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            for record in records:
                if "__raw__" in record:
                    f.write(record["__raw__"] + "\n")
                else:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    os.replace(tmp_path, records_file)

    logger.info("Updated record %s with %d fields", record_id, len(updated_fields))
    return True


def list_records(limit: int = 20) -> List[Dict[str, Any]]:
    """Return most recent records (for inspection)."""
    records_file = RECORDS_DIR / "records.jsonl"
    if not records_file.exists():
        return []

    records: List[Dict[str, Any]] = []
    with open(records_file, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning(
                    "Skipping malformed record at %s line %d: %s",
                    records_file, line_no, e,
                )

    return records[-limit:]
