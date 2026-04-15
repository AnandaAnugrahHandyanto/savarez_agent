import asyncio
import json
import uuid
import os
import logging
from typing import List, Dict, Any, Optional

from .schema import MasterResearchLedger, PodcastProject, DialogueLine, AudioClip
from .tts_provider import MacNativeTTSProvider, ElevenLabsTTSProvider

logger = logging.getLogger(__name__)

class MediaSynthesisOrchestrator:
    def __init__(self, agent_runner_coro):
        """agent_runner_coro is a callable that takes (system_prompt, user_prompt) -> result json"""
        self.agent_runner = agent_runner_coro
        self.tts = MacNativeTTSProvider() # default to local for V1

    async def _gather_research(self, topic: str, source_refs: List[str]) -> MasterResearchLedger:
        """Simulate triggering research subagents/browser scraping"""
        # In a full implementation, this runs a query against knowledge graph and returns real data.
        # Here we mock it based on schema for end-to-end functionality.
        return MasterResearchLedger(
            target_topic=topic,
            core_theses=["AI accelerates scaling", "Agentic unit economics are marginal"],
            supporting_audio_clips=[],
            external_research=[],
            visual_assets=[]
        )

    async def _generate_script(self, ledger: MasterResearchLedger) -> PodcastProject:
        """Uses LLM to generate the script constrained by the ledger."""
        system_prompt = (
            "You are a master script writer. Based strictly on the provided JSON Ledger, "
            "generate a PodcastProject JSON describing the timeline. "
            "Do not hallucinate facts."
        )
        user_prompt = f"Ledger Data:\n{ledger.model_dump_json()}\nGenerate a podcast script."
        
        result_json = await self.agent_runner(system_prompt, user_prompt)
        
        # fallback if JSON parsing fails/simplification for stub
        try:
            parsed = json.loads(result_json)
            return PodcastProject(**parsed)
        except Exception:
            return PodcastProject(
                episode_title=f"The deep dive: {ledger.target_topic}",
                target_duration_minutes=5,
                timeline=[
                    DialogueLine(speaker="Host_1", text=f"Welcome to today's episode on {ledger.target_topic}."),
                    DialogueLine(speaker="Host_2", text=ledger.core_theses[0] if ledger.core_theses else "Interesting topic.")
                ]
            )

    async def _synthesize_audio(self, script: PodcastProject, output_dir: str) -> str:
        """Renders TTS and handles audio splicing."""
        os.makedirs(output_dir, exist_ok=True)
        final_mp3 = os.path.join(output_dir, f"{script.episode_title.replace(' ','_')}.mp3")
        
        audio_segments = []
        try:
            from pydub import AudioSegment
            pydub_installed = True
        except ImportError:
            pydub_installed = False

        for i, line in enumerate(script.timeline):
            if line.speaker == "Audio_Splice" and line.audio_splice_ref:
                # Need to load the splice
                if pydub_installed and line.audio_splice_ref.local_file_path:
                    try:
                        clip = AudioSegment.from_file(line.audio_splice_ref.local_file_path)
                        audio_segments.append(clip)
                    except Exception as e:
                        logger.error(f"Failed to load clip: {e}")
            else:
                # Text to Speech
                temp_file = os.path.join(output_dir, f"line_{i}.mp3")
                await self.tts.synthesize(line.text, line.voice_tone, temp_file)
                if pydub_installed and os.path.exists(temp_file):
                    try:
                        clip = AudioSegment.from_file(temp_file)
                        audio_segments.append(clip)
                    except Exception as e:
                        logger.error(f"Failed to load TTS clip: {e}")

        # Combine
        if pydub_installed and audio_segments:
            combined = audio_segments[0]
            for segment in audio_segments[1:]:
                combined += segment
            combined.export(final_mp3, format="mp3")
        else:
            # fallback
            with open(final_mp3, "wb") as f:
                f.write(b"No pydub or audio generated")

        return final_mp3

    async def _generate_article(self, ledger: MasterResearchLedger, script: PodcastProject, output_dir: str) -> str:
        """Compiles the final Markdown article combining script, interactive diagrams, and audio player."""
        md_content = f"# {script.episode_title}\n\n"
        md_content += f"<audio controls src='{script.episode_title.replace(' ','_')}.mp3'></audio>\n\n"
        md_content += f"## Research Ledger Theses\n"
        for t in ledger.core_theses:
            md_content += f"- {t}\n"
        
        md_content += "\n## Transcript:\n"
        for l in script.timeline:
            md_content += f"**{l.speaker}**: {l.text}\n\n"

        out_file = os.path.join(output_dir, "article.md")
        with open(out_file, "w") as f:
            f.write(md_content)
        return out_file

    async def execute_pipeline(self, topic: str, source_refs: List[str], output_dir: str) -> Dict[str, str]:
        ledger = await self._gather_research(topic, source_refs)
        script = await self._generate_script(ledger)
        audio_path = await self._synthesize_audio(script, output_dir)
        article_path = await self._generate_article(ledger, script, output_dir)
        
        return {
            "audio_url": os.path.basename(audio_path),
            "article_path": article_path,
            "title": script.episode_title
        }
