---
name: audio-podcast
description: Generates a two-speaker educational audio podcast from a source document using edge-tts.
---

# Audio Podcast Generator (NotebookLM Style)

This skill generates a NotebookLM-style "Deep Dive" audio podcast from a document.
It creates a two-speaker educational script (Host 1 and Host 2) using an LLM, then converts it to an mp3 audio file using `edge-tts`.

## Dependencies
This skill requires `edge-tts` to be installed.
```bash
pip install edge-tts pydub
```

## Generate a Podcast

To generate a podcast from a document:

```bash
python ~/.hermes/skills/creative/audio-podcast/podcast_gen.py --input "path/to/document.md" --output "podcast.mp3"
```

## How it works
1. The script reads the source document.
2. It sends a prompt to OpenRouter/OpenAI (via Hermes environment variables) to write a dialogue.
3. It uses `edge-tts` to synthesize the text with two distinct voices.
4. It combines the audio and saves the final `.mp3`.
