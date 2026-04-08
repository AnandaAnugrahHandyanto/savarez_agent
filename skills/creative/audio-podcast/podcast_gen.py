#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

def generate_podcast_script(text):
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY or OPENAI_API_KEY must be set.")
        sys.exit(1)

    url = "https://openrouter.ai/api/v1/chat/completions" if "OPENROUTER" in os.environ else "https://api.openai.com/v1/chat/completions"
    model = "anthropic/claude-3-5-sonnet:beta" if "OPENROUTER" in os.environ else "gpt-4o"

    system_prompt = """You are a podcast generator. Create an engaging 2-speaker "Deep Dive" educational podcast script based on the provided text.
The two hosts are Alex and Sam.
Return ONLY valid JSON in the following format, with no markdown formatting around it:
[
  {"speaker": "Alex", "text": "Welcome to the deep dive..."},
  {"speaker": "Sam", "text": "That's right, today we are looking at..."}
]"""

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text[:100000]}  # limit text length
        ],
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })

    print("Generating script via LLM...")
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            try:
                script = json.loads(content)
                return script
            except json.JSONDecodeError:
                # Attempt to strip markdown if present
                if content.startswith("```json"):
                    content = content.strip("```json").strip("```")
                return json.loads(content)
    except Exception as e:
        print(f"Failed to generate script: {e}")
        sys.exit(1)

def synthesize_audio(script, output_file):
    print("Synthesizing audio via edge-tts...")
    audio_files = []
    for i, line in enumerate(script):
        speaker = line.get("speaker", "Alex")
        text = line.get("text", "")
        # Alex = male, Sam = female (arbitrary edge-tts voices)
        voice = "en-US-ChristopherNeural" if speaker == "Alex" else "en-US-AriaNeural"
        
        tmp_file = f"temp_{i}.mp3"
        audio_files.append(tmp_file)
        
        cmd = ["edge-tts", "--voice", voice, "--text", text, "--write-media", tmp_file]
        subprocess.run(cmd, check=True)

    print(f"Combining {len(audio_files)} audio files into {output_file}...")
    
    # We use ffmpeg or just cat if we are lazy, but pydub or ffmpeg is better.
    # Since pydub is in dependencies, let's use ffmpeg directly if available or pydub.
    try:
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for f in audio_files:
            combined += AudioSegment.from_mp3(f)
        combined.export(output_file, format="mp3")
    except ImportError:
        print("pydub not found. Concatenating raw mp3s (might have glitchy transitions)...")
        with open(output_file, "wb") as outfile:
            for f in audio_files:
                with open(f, "rb") as infile:
                    outfile.write(infile.read())

    # Cleanup temp files
    for f in audio_files:
        if os.path.exists(f):
            os.remove(f)

    print("Done!")

def main():
    parser = argparse.ArgumentParser(description="Generate a NotebookLM-style podcast from a document.")
    parser.add_argument("--input", required=True, help="Input markdown or text file")
    parser.add_argument("--output", required=True, help="Output MP3 file")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    script = generate_podcast_script(text)
    synthesize_audio(script, args.output)

if __name__ == "__main__":
    main()
