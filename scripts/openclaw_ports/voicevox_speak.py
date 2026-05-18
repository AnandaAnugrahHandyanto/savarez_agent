"""Ported from clawdbot-main/scripts/tools — run via: py -3 scripts/openclaw_ports/<name>"""

#!/usr/bin/env python3
"""
voicevox_speak.py — VOICEVOX TTS スタンドアロン再生スクリプト

Usage:
    py -3 scripts/voicevox_speak.py --text "こんにちは" [--speaker 8] [--url http://127.0.0.1:50021]

VOICEVOX が起動していれば音声を合成して winsound（Windows組み込み）で再生する。
追加パッケージ不要。
"""

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


def audio_query(text: str, speaker: int, base_url: str) -> dict:
    """VOICEVOX /audio_query を呼び出してクエリを取得"""
    encoded = urllib.parse.quote(text)
    url = f"{base_url}/audio_query?text={encoded}&speaker={speaker}"
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def synthesis(query: dict, speaker: int, base_url: str) -> bytes:
    """VOICEVOX /synthesis を呼び出してWAVバイト列を取得"""
    url = f"{base_url}/synthesis?speaker={speaker}"
    body = json.dumps(query).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def play_wav_bytes(wav_bytes: bytes) -> None:
    """WAVデータをWindowsの組み込みwinsoundで再生"""
    try:
        import winsound

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_path = f.name
        try:
            winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
        finally:
            os.unlink(tmp_path)
        return
    except ImportError:
        pass  # Not Windows or winsound unavailable

    # Fallback: sounddevice + soundfile (optional, cross-platform)
    try:
        import io
        import sounddevice as sd  # type: ignore
        import soundfile as sf  # type: ignore

        data, samplerate = sf.read(io.BytesIO(wav_bytes))
        sd.play(data, samplerate)
        sd.wait()
        return
    except ImportError:
        pass

    # Last resort: write to stdout (pipe to aplay / ffplay)
    sys.stdout.buffer.write(wav_bytes)


def main() -> None:
    parser = argparse.ArgumentParser(description="VOICEVOX TTS スタンドアロン再生")
    parser.add_argument("--text", required=True, help="読み上げるテキスト")
    parser.add_argument("--speaker", type=int, default=8, help="VOICEVOXスピーカーID (デフォルト: 8)")
    parser.add_argument(
        "--url", default="http://127.0.0.1:50021", help="VOICEVOX エンジン URL"
    )
    args = parser.parse_args()

    text = args.text.strip()
    if not text:
        print("[voicevox_speak] テキストが空です", file=sys.stderr)
        sys.exit(1)

    # 文字数制限 (VOICEVOX は長文だとタイムアウトするため)
    if len(text) > 300:
        text = text[:297] + "…"

    try:
        query = audio_query(text, args.speaker, args.url)
        wav_bytes = synthesis(query, args.speaker, args.url)
        play_wav_bytes(wav_bytes)
        print(f"[voicevox_speak] OK: {text[:40]}{'…' if len(text) > 40 else ''}")
    except urllib.error.URLError as e:
        print(f"[voicevox_speak] VOICEVOX 接続失敗: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[voicevox_speak] エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
