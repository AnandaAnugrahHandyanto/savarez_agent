"""
QQbot message handler for pharma compliance.

Handles text, voice (STT), and photo (Vision+OCR+EXIF) messages.
Merges multimodal messages within a 5-minute window into one task record.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Lazy imports for Hermes modules (imported at module level so tests can patch)
try:
    from tools.transcription_tools import transcribe_audio
except ImportError:
    transcribe_audio = None

try:
    from tools.vision_tools import vision_analyze_tool
except ImportError:
    vision_analyze_tool = None

from pharma_compliance.session import (
    MERGE_WINDOW_SECONDS,
    MessageType,
    SessionManager,
    VisitSession,
)
from pharma_compliance.extractor import extract_fields, fields_to_summary, get_missing_core_fields
from pharma_compliance.persistence import save_record

logger = logging.getLogger(__name__)


class ComplianceBotHandler:
    """Handles incoming QQbot messages for pharma compliance tracking.

    Key flows:
    - Text → extract fields directly
    - Voice → download → STT → extract fields
    - Photo → download → Vision+OCR → EXIF → cross-check
    - Multi-message merge within 5-min window
    """

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        on_task_complete: Optional[Callable] = None,
    ):
        self.sessions = session_manager or SessionManager()
        self.on_task_complete = on_task_complete
        self._merge_timers: Dict[str, asyncio.Task] = {}

    # ── Public entry point ──────────────────────────────────────────────────

    async def handle_message(
        self,
        user_id: str,
        msg_type: str,  # "text", "voice", "photo"
        content: str,   # text content or URL/path for voice/photo
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle an incoming message and return extracted results.

        Returns:
            dict with:
              - "merged": bool — whether a full task was completed
              - "task": dict or None — extracted fields if merged
              - "warnings": list[str] — any compliance warnings
              - "pending_count": int — messages still pending
              - "text_preview": str or None — preview text for user confirmation
        """
        warnings: List[str] = []
        metadata = metadata or {}
        session = self.sessions.get_or_create_session(user_id)

        # Check for manual merge trigger in text messages
        if msg_type == "text" and session.check_manual_merge(content):
            return await self._force_merge(session)

        try:
            if msg_type == "voice":
                result = await self._handle_voice(user_id, content, metadata, session)
            elif msg_type == "photo":
                result = await self._handle_photo(user_id, content, metadata, session)
            else:
                result = await self._handle_text(user_id, content, metadata, session)
        except Exception as e:
            logger.error("handle_message failed for user %s: %s", user_id, e)
            return {
                "merged": False,
                "task": None,
                "warnings": [f"处理失败: {e}"],
                "pending_count": len(session.pending_messages),
                "text_preview": None,
                "missing_fields": [],
            }

        # Schedule background merge timer (reset on each new message)
        self._schedule_merge_timeout(session.user_id)

        # Check if session should auto-merge immediately (5-min timeout from last message)
        if session.should_merge():
            return await self._do_merge(session, warnings)

        result["warnings"] = result.get("warnings", []) + warnings
        return result

    # ── Text handler ────────────────────────────────────────────────────────

    async def _handle_text(
        self,
        user_id: str,
        text: str,
        metadata: Dict[str, Any],
        session: VisitSession,
    ) -> Dict[str, Any]:
        session.add_message(MessageType.TEXT, text, metadata=metadata)
        fields = extract_fields(text)
        return {
            "merged": False,
            "task": None,
            "warnings": [],
            "pending_count": len(session.pending_messages),
            "text_preview": text,
            "missing_fields": get_missing_core_fields(fields),
        }

    # ── Voice handler ───────────────────────────────────────────────────────

    async def _handle_voice(
        self,
        user_id: str,
        content: str,  # file path or URL to audio file
        metadata: Dict[str, Any],
        session: VisitSession,
    ) -> Dict[str, Any]:
        transcript = ""
        confidence = 0.0
        stt_used = False
        downloaded = False

        try:
            if not os.path.exists(content):
                # Could be URL — download to temp
                content = await self._download_file(content, suffix=".ogg")
                downloaded = True

            # When STT module is unavailable, give a clear suggestion
            if transcribe_audio is None:
                return {
                    "merged": False,
                    "task": None,
                    "warnings": [
                        "语音识别暂不可用，请用文字描述拜访情况，或发送门头照+文字"
                    ],
                    "pending_count": len(session.pending_messages),
                    "text_preview": None,
                    "missing_fields": [],
                }

            # Use Hermes STT module
            try:
                result = transcribe_audio(content)
                if result.get("success"):
                    transcript = result.get("transcript", "")
                    stt_used = True
                    # Use explicit confidence from result if available, otherwise infer
                    if "confidence" in result:
                        confidence = float(result["confidence"])
                    else:
                        confidence = 0.85 if transcript else 0.0
                    logger.info(
                        "STT success (provider=%s): %s",
                        result.get("provider", "?"), transcript[:80],
                    )
                else:
                    logger.warning("STT failed: %s", result.get("error", "unknown"))
                    return {
                        "merged": False,
                        "task": None,
                        "warnings": [f"语音识别失败: {result.get('error', '')}"],
                        "pending_count": len(session.pending_messages),
                        "text_preview": None,
                        "missing_fields": [],
                    }
            except ImportError:
                logger.warning("Hermes STT not available")
                transcript = "[语音消息 — 无法识别]"
            except Exception as e:
                logger.error("STT call failed: %s", e)
                transcript = "[语音消息 — 识别异常]"

        finally:
            # Only delete temp files that were downloaded, never local files
            if downloaded:
                self._safe_delete(content)

        # Handle long transcript — save raw text in metadata for potential segmentation
        if transcript and len(transcript) > 2000:
            metadata["stt_raw"] = transcript

        # Low-confidence check — ask user to confirm; keep message pending for force-merge
        if confidence < 0.6:
            if transcript:
                session.add_message(MessageType.VOICE, transcript, metadata=metadata)
            fields = extract_fields(transcript) if transcript else {}
            return {
                "merged": False,
                "task": None,
                "warnings": [],
                "pending_count": len(session.pending_messages),
                "text_preview": transcript,
                "needs_confirmation": True,
                "missing_fields": get_missing_core_fields(fields),
            }

        session.add_message(MessageType.VOICE, transcript, metadata=metadata)
        fields = extract_fields(transcript)
        return {
            "merged": False,
            "task": None,
            "warnings": [],
            "pending_count": len(session.pending_messages),
            "text_preview": transcript,
            "missing_fields": get_missing_core_fields(fields),
        }

    # ── Photo handler ───────────────────────────────────────────────────────

    async def _handle_photo(
        self,
        user_id: str,
        content: str,  # file path or URL to image
        metadata: Dict[str, Any],
        session: VisitSession,
    ) -> Dict[str, Any]:
        warnings: List[str] = []
        ocr_text = ""
        exif_data: Dict[str, Any] = {}
        downloaded = False

        # Step 1: Ensure file is local
        local_path = content
        if content.startswith("http://") or content.startswith("https://"):
            local_path = await self._download_file(content, suffix=".jpg")
            downloaded = True

        # Step 2: Vision + OCR via Hermes vision_tools
        ocr_text = await self._ocr_via_vision(local_path)
        if not ocr_text:
            ocr_text = self._ocr_via_pil_fallback(local_path)

        # Step 3: Extract EXIF (GPS + timestamp)
        exif_data = self._extract_exif(local_path)

        # Step 4: Store photo data in session
        photo_metadata = {
            "ocr_text": ocr_text,
            "exif": exif_data,
            "file_path": local_path,
            "is_temp": downloaded,
        }
        session.add_message(
            MessageType.PHOTO,
            ocr_text or "[门头照]",
            metadata=photo_metadata,
        )

        return {
            "merged": False,
            "task": None,
            "warnings": warnings,
            "pending_count": len(session.pending_messages),
            "text_preview": f"[门头照] {ocr_text}" if ocr_text else "[门头照]",
            "photo_exif": exif_data,
            "missing_fields": get_missing_core_fields(extract_fields(ocr_text or "[门头照]")),
        }

    # ── Vision+OCR ──────────────────────────────────────────────────────────

    async def _ocr_via_vision(self, image_path: str) -> str:
        """Use Hermes vision_tools (qwen-vl-max via DashScope) for OCR."""
        try:
            prompt = (
                "请识别这张图片中的所有文字，特别关注：\n"
                "1. 店名/机构名称\n"
                "2. 门牌号\n"
                "3. 任何地址信息\n"
                "4. 电话号码\n\n"
                "请以JSON格式返回：\n"
                '{"store_name": "店名", "address": "地址", "phone": "电话", "other_text": "其他文字"}'
            )
            result = await vision_analyze_tool(
                image_url=image_path,
                user_prompt=prompt,
            )
            # vision_analyze_tool returns JSON string with {"success": bool, "analysis": str}
            parsed = json.loads(result)
            if parsed.get("success"):
                analysis = parsed.get("analysis", "")
                # Try to parse structured JSON from analysis
                try:
                    structured = json.loads(analysis)
                    store_name = structured.get("store_name", "")
                    address = structured.get("address", "")
                    phone = structured.get("phone", "")
                    other = structured.get("other_text", "")
                    parts = [p for p in [store_name, address, phone, other] if p]
                    return " ".join(parts) if parts else analysis
                except (json.JSONDecodeError, TypeError):
                    return analysis
            return ""
        except ImportError:
            logger.warning("Hermes vision_tools not available")
            return ""
        except Exception as e:
            logger.error("Vision+OCR failed: %s", e)
            return ""

    def _ocr_via_pil_fallback(self, image_path: str) -> str:
        """Fallback OCR using PIL/Pillow for basic text extraction."""
        try:
            from PIL import Image

            img = Image.open(image_path)
            return f"[图片: {img.width}x{img.height}]"
        except ImportError:
            return "[图片 — 无法分析]"
        except Exception as e:
            logger.error("PIL fallback failed: %s", e)
            return ""

    # ── EXIF extraction ─────────────────────────────────────────────────────

    def _extract_exif(self, image_path: str) -> Dict[str, Any]:
        """Extract EXIF metadata: GPS coordinates and capture time."""
        result: Dict[str, Any] = {"gps": None, "datetime": None}

        try:
            from PIL import Image
            from PIL.ExifTags import Base as ExifBase, GPSTAGS

            img = Image.open(image_path)
            exif_raw = img.getexif()
            if not exif_raw:
                return result

            exif = {ExifBase(k).name: v for k, v in exif_raw.items() if k in ExifBase}

            # Capture time
            dt_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
            if dt_str:
                try:
                    dt = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
                    result["datetime"] = dt.isoformat()
                except ValueError:
                    result["datetime"] = str(dt_str)

            # GPS coordinates
            gps_info = exif_raw.get_ifd(0x8825)  # GPSInfo IFD
            if gps_info:
                gps = {}
                for tag_id, value in gps_info.items():
                    tag_name = GPSTAGS.get(tag_id, str(tag_id))
                    gps[tag_name] = value
                result["gps"] = self._parse_gps(gps)

        except ImportError:
            logger.debug("PIL/Pillow not available for EXIF")
        except Exception as e:
            logger.warning("EXIF extraction failed: %s", e)

        return result

    def _parse_gps(self, gps: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Parse GPS data from EXIF into lat/lon."""
        try:
            lat_ref = gps.get("GPSLatitudeRef", "N")
            lat = gps.get("GPSLatitude")
            lon_ref = gps.get("GPSLongitudeRef", "E")
            lon = gps.get("GPSLongitude")

            if not lat or not lon:
                return None

            def _to_decimal(dms) -> float:
                if isinstance(dms, (tuple, list)) and len(dms) >= 3:
                    return float(dms[0]) + float(dms[1]) / 60.0 + float(dms[2]) / 3600.0
                return float(dms)

            lat_dd = _to_decimal(lat)
            lon_dd = _to_decimal(lon)
            if lat_ref == "S":
                lat_dd = -lat_dd
            if lon_ref == "W":
                lon_dd = -lon_dd

            return {"latitude": round(lat_dd, 6), "longitude": round(lon_dd, 6)}
        except Exception as e:
            logger.warning("GPS parse failed: %s", e)
            return None

    # ── Cross-check logic ───────────────────────────────────────────────────

    def cross_check(
        self,
        claimed_store: str,
        ocr_store: str,
        claimed_location: Optional[Dict[str, float]] = None,
        exif_gps: Optional[Dict[str, float]] = None,
        claimed_time: Optional[str] = None,
        exif_time: Optional[str] = None,
    ) -> List[str]:
        """Cross-check claimed info against photo metadata. Returns warnings."""
        warnings: List[str] = []

        # Check 1: store name mismatch
        if ocr_store and claimed_store:
            if not self._fuzzy_match(claimed_store, ocr_store):
                warnings.append(
                    f"⚠️ 地址不匹配: 声称'{claimed_store}' vs OCR'{ocr_store}'"
                )

        # Check 2: GPS deviation > 500m
        if claimed_location and exif_gps:
            dist = self._haversine_distance(
                claimed_location.get("latitude", 0),
                claimed_location.get("longitude", 0),
                exif_gps.get("latitude", 0),
                exif_gps.get("longitude", 0),
            )
            if dist > 500:
                warnings.append(
                    f"⚠️ 位置偏差: {dist:.0f}m"
                )

        # Check 3: time deviation > 30 min
        if claimed_time and exif_time:
            try:
                ct = datetime.fromisoformat(claimed_time)
                et = datetime.fromisoformat(exif_time)
                diff = abs((ct - et).total_seconds())
                if diff > 1800:
                    warnings.append(
                        f"⚠️ 时间偏差: {diff/60:.0f}分钟"
                    )
            except (ValueError, TypeError):
                pass

        return warnings

    @staticmethod
    def _fuzzy_match(a: str, b: str, threshold: float = 0.6) -> bool:
        """Simple fuzzy matching between two names."""
        a_clean = "".join(c for c in a if c.isalnum())
        b_clean = "".join(c for c in b if c.isalnum())
        if not a_clean or not b_clean:
            return False
        # Check if one is a substring of the other
        if a_clean in b_clean or b_clean in a_clean:
            return True
        # Character overlap ratio
        overlap = len(set(a_clean) & set(b_clean))
        max_len = max(len(set(a_clean)), len(set(b_clean)))
        return overlap / max_len >= threshold if max_len > 0 else False

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate haversine distance in meters between two GPS points."""
        import math

        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ── Merge logic ─────────────────────────────────────────────────────────

    async def _do_merge(
        self, session: VisitSession, extra_warnings: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Merge pending messages into a task record and run extraction."""
        warnings = list(extra_warnings or [])
        merged_text = session.merge_contents()

        # Extract fields from merged text
        fields = extract_fields(merged_text)

        # Extract claimed_location from any message's metadata (rep-shared GPS)
        claimed_location = self._extract_claimed_location(session)

        # Cross-check photo vs text claims
        photo_metas = self._collect_photo_metadata(session)
        if photo_metas:
            warnings.extend(
                self._run_cross_checks(fields, photo_metas, claimed_location)
            )

        task = {
            "fields": fields,
            "summary": fields_to_summary(fields),
            "warnings": warnings,
            "message_count": len(session.pending_messages),
            "merged_text": merged_text,
        }

        # Collect photo paths BEFORE any archival/deletion
        photo_paths = self._collect_photo_paths(session)

        # Persist record + photos to disk FIRST (before archive may delete temp files)
        persist_ok = False
        try:
            save_record(task, photo_paths)
            persist_ok = True
        except Exception as e:
            logger.error("Failed to persist record: %s", e)

        if persist_ok:
            # Only archive (which may delete temp files) after successful persistence
            self._archive_photos(session)
            # Clear pending messages ONLY after successful persistence
            session.clear()
        else:
            logger.warning(
                "Persistence failed for user %s — session NOT cleared, data retained for retry",
                session.user_id,
            )

        # Cancel any pending merge timer for this session
        self._cancel_merge_timer(session.user_id)

        # Check feedback field completeness — 反馈必填引导追问
        feedback = fields.get("feedback", "")
        feedback_missing = not feedback or (isinstance(feedback, str) and not feedback.strip())
        followup_msg = None
        if feedback_missing:
            followup_msg = (
                "好的，记录下来了～再补充一下：这次的拜访对象有什么具体的反馈吗？"
                "比如对产品的评价、销量变化、提出的建议等等。"
            )
            logger.info("Feedback field missing for user %s, requesting follow-up", session.user_id)

        if self.on_task_complete:
            try:
                result = self.on_task_complete(task)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("on_task_complete callback failed: %s", e)

        missing_fields = get_missing_core_fields(fields)
        if feedback_missing and "feedback" not in missing_fields:
            missing_fields.append("feedback")

        return {
            "merged": True,
            "task": task,
            "warnings": warnings,
            "pending_count": 0,
            "text_preview": fields_to_summary(fields),
            "missing_fields": missing_fields,
            "needs_followup": feedback_missing,
            "followup_field": "feedback" if feedback_missing else None,
            "followup_message": followup_msg,
        }

    async def _force_merge(self, session: VisitSession) -> Dict[str, Any]:
        """Force merge triggered by manual phrase ('完了' etc.)."""
        if not session.pending_messages:
            return {
                "merged": False,
                "task": None,
                "warnings": [],
                "pending_count": 0,
                "text_preview": None,
                "missing_fields": [],
            }
        logger.info("Manual merge triggered for user %s", session.user_id)
        return await self._do_merge(session)

    @staticmethod
    def _extract_claimed_location(session: VisitSession) -> Optional[Dict[str, float]]:
        """Extract claimed GPS location from any pending message's metadata."""
        for msg in session.pending_messages:
            loc = msg.metadata.get("claimed_location")
            if loc and isinstance(loc, dict):
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    return {"latitude": float(lat), "longitude": float(lon)}
        return None

    def _collect_photo_metadata(self, session: VisitSession) -> List[Dict[str, Any]]:
        return [
            msg.metadata
            for msg in session.pending_messages
            if msg.msg_type == MessageType.PHOTO
        ]

    def _run_cross_checks(
        self,
        fields: Dict[str, Any],
        photo_metas: List[Dict[str, Any]],
        claimed_location: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        warnings: List[str] = []
        claimed_store = fields.get("org_name", "")
        claimed_address = fields.get("org_address", "")
        claimed_date = fields.get("visit_date", "")
        claimed_time = fields.get("visit_time", "")
        claimed_dt = f"{claimed_date}T{claimed_time}" if claimed_date and claimed_time else None

        for pm in photo_metas:
            ocr_text = pm.get("ocr_text", "")
            exif = pm.get("exif", {})

            # Extract store name from OCR text
            ocr_store = self._extract_store_from_ocr(ocr_text)

            cross_warnings = self.cross_check(
                claimed_store=claimed_store,
                ocr_store=ocr_store,
                claimed_location=claimed_location,
                exif_gps=exif.get("gps"),
                claimed_time=claimed_dt,
                exif_time=exif.get("datetime"),
            )
            warnings.extend(cross_warnings)

        return warnings

    @staticmethod
    def _extract_store_from_ocr(ocr_text: str) -> str:
        """Extract store name from OCR output."""
        if not ocr_text:
            return ""
        # OCR text often starts with the store name
        for suffix in ["大药房", "药房", "药店", "医院", "诊所", "连锁"]:
            idx = ocr_text.find(suffix)
            if idx >= 0:
                start = max(0, idx - 10)
                return ocr_text[start:idx + len(suffix)].strip()
        return ""

    def _archive_photos(self, session: VisitSession) -> None:
        """Move photos to session archive directory."""
        archive_dir = Path(tempfile.gettempdir()) / "pharma_archive" / session.user_id
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            for msg in session.pending_messages:
                if msg.msg_type == MessageType.PHOTO:
                    src = msg.metadata.get("file_path", "")
                    if src and os.path.exists(src):
                        dst = archive_dir / os.path.basename(src)
                        import shutil
                        shutil.copy2(src, dst)
                        logger.debug("Archived photo: %s → %s", src, dst)
                        if msg.metadata.get("is_temp"):
                            ComplianceBotHandler._safe_delete(src)
        except Exception as e:
            logger.error("Photo archive failed: %s", e)

    @staticmethod
    def _collect_photo_paths(session: VisitSession) -> List[str]:
        """Collect file paths of all photos in the session for persistence."""
        paths: List[str] = []
        for msg in session.pending_messages:
            if msg.msg_type == MessageType.PHOTO:
                src = msg.metadata.get("file_path", "")
                if src and os.path.exists(src):
                    paths.append(src)
        return paths

    # ── Background merge timer ──────────────────────────────────────────────

    def _schedule_merge_timeout(self, session_id: str, timeout: float = 300.0) -> None:
        """Schedule a background merge after `timeout` seconds of inactivity.

        Cancels any existing timer for the session and creates a new one.
        When the timer fires, triggers merge_and_finalize.
        """
        self._cancel_merge_timer(session_id)

        async def _delayed_merge():
            await asyncio.sleep(timeout)
            session = self.sessions.get_session(session_id)
            if session and session.pending_messages:
                logger.info(
                    "Background merge timer fired for user %s (%d pending)",
                    session_id, len(session.pending_messages),
                )
                try:
                    await self._do_merge(session)
                except Exception as e:
                    logger.error("Background merge failed for user %s: %s", session_id, e)

        self._merge_timers[session_id] = asyncio.create_task(_delayed_merge())
        logger.debug("Scheduled merge timer for user %s (%.0fs)", session_id, timeout)

    def _cancel_merge_timer(self, session_id: str) -> None:
        """Cancel the pending merge timer for a session."""
        timer = self._merge_timers.pop(session_id, None)
        if timer and not timer.done():
            timer.cancel()
            logger.debug("Cancelled merge timer for user %s", session_id)

    # ── Utilities ────────────────────────────────────────────────────────────

    async def _download_file(self, url: str, suffix: str = ".tmp") -> str:
        """Download a file from URL to temp directory. Returns local path.

        Cleans up the temp file on failure.
        """
        path = None
        try:
            import aiohttp
        except ImportError:
            aiohttp = None

        if aiohttp is not None:
            fd, path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            with open(path, "wb") as f:
                                f.write(await resp.read())
                            return path
                        else:
                            raise IOError(f"Download failed: HTTP {resp.status}")
            except Exception:
                self._safe_delete(path)
                raise
        else:
            import urllib.request
            fd, path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            try:
                urllib.request.urlretrieve(url, path)
                return path
            except Exception:
                self._safe_delete(path)
                raise

    @staticmethod
    def _safe_delete(file_path: str) -> None:
        """Safely delete a temporary file."""
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug("Deleted temp file: %s", file_path)
        except Exception as e:
            logger.warning("Failed to delete temp file %s: %s", file_path, e)


# ── Convenience function ────────────────────────────────────────────────────

async def process_message(
    user_id: str,
    msg_type: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience function to process a single message."""
    handler = ComplianceBotHandler()
    return await handler.handle_message(user_id, msg_type, content, metadata)
