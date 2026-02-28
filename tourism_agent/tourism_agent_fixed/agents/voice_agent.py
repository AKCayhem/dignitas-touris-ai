"""
Agent 5 – Voice Generator
Produces a voiceover for the video script.
Priority order:
  1. ElevenLabs API (best quality, free tier 10k chars/month)
  2. gTTS (Google Text-to-Speech, completely free, always available)
  3. pyttsx3 (offline, emergency fallback)
"""

import os
import time
from pathlib import Path
from typing import Optional

from gtts import gTTS

import config
from utils.logger import logger
from utils.file_manager import get_output_path, timestamped_filename

# Track ElevenLabs usage in a local file to avoid exceeding the free limit
_EL_USAGE_FILE = Path(__file__).parent.parent / "logs" / "elevenlabs_usage.txt"
_EL_FREE_LIMIT = 10_000   # characters per month


def _read_el_usage() -> int:
    try:
        return int(_EL_USAGE_FILE.read_text().strip())
    except Exception:
        return 0


def _write_el_usage(chars: int) -> None:
    _EL_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _EL_USAGE_FILE.write_text(str(chars))


class VoiceGeneratorAgent:
    """Generates spoken voiceover audio from a script text string."""

    # ElevenLabs Rachel voice ID (natural, engaging female voice)
    EL_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

    def __init__(self) -> None:
        self._el_client = None
        if config.ELEVENLABS_API_KEY:
            try:
                from elevenlabs.client import ElevenLabs
                self._el_client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
                logger.info("ElevenLabs client ready")
            except Exception as exc:
                logger.warning(f"ElevenLabs init failed: {exc}")

    # ── Public API ───────────────────────────────────────────────────────────

    async def generate_voice(self, script_text: str) -> Path:
        """
        Generate voiceover audio, trying ElevenLabs first then gTTS.

        Args:
            script_text: Full narration text.

        Returns:
            Path to the generated audio file.
        """
        # Try ElevenLabs
        el_path = self.generate_elevenlabs_voice(script_text)
        if el_path:
            return el_path

        # Fallback to gTTS
        logger.info("Falling back to gTTS for voiceover")
        return self.generate_gtts_voice(script_text)

    def generate_elevenlabs_voice(
        self,
        script_text: str,
        voice_id: str | None = None,
    ) -> Optional[Path]:
        """
        Generate voiceover using ElevenLabs API.

        Args:
            script_text: Narration text.
            voice_id:    ElevenLabs voice ID (defaults to Rachel).

        Returns:
            Path to MP3, or None if limit exceeded / error.
        """
        if not self._el_client:
            return None

        used = _read_el_usage()
        if used + len(script_text) > _EL_FREE_LIMIT:
            logger.warning(
                f"ElevenLabs monthly limit approaching ({used}/{_EL_FREE_LIMIT} chars); "
                "switching to gTTS"
            )
            return None

        voice_id = voice_id or self.EL_VOICE_ID
        try:
            audio_gen = self._el_client.text_to_speech.convert(
                voice_id=voice_id,
                text=script_text,
                model_id="eleven_monolingual_v1",
                voice_settings={
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                },
            )
            fname = timestamped_filename("voiceover_el", "mp3")
            out_path = get_output_path("audio", fname)
            with open(out_path, "wb") as f:
                for chunk in audio_gen:
                    f.write(chunk)

            # Update usage counter
            _write_el_usage(used + len(script_text))
            logger.info(f"ElevenLabs voiceover saved: {out_path.name}")
            return out_path

        except Exception as exc:
            logger.warning(f"ElevenLabs TTS error: {exc}")
            return None

    def generate_gtts_voice(
        self,
        script_text: str,
        language: str = "en",
        slow: bool = False,
    ) -> Path:
        """
        Generate voiceover using Google Text-to-Speech (gTTS) – always free.

        Args:
            script_text: Narration text.
            language:    BCP-47 language code.
            slow:        If True, generates slower speech.

        Returns:
            Path to the generated MP3.
        """
        fname = timestamped_filename("voiceover_gtts", "mp3")
        out_path = get_output_path("audio", fname)

        try:
            tts = gTTS(text=script_text, lang=language, slow=slow)
            tts.save(str(out_path))
            logger.info(f"gTTS voiceover saved: {out_path.name}")
            return out_path
        except Exception as exc:
            logger.error(f"gTTS error: {exc}")
            return self._pyttsx3_fallback(script_text)

    def _pyttsx3_fallback(self, script_text: str) -> Path:
        """Emergency offline TTS using pyttsx3."""
        out_path = get_output_path("audio", "voiceover_pyttsx3.mp3")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.save_to_file(script_text, str(out_path))
            engine.runAndWait()
            logger.info(f"pyttsx3 voiceover saved: {out_path.name}")
        except Exception as exc:
            logger.error(f"pyttsx3 fallback also failed: {exc}")
            # Create a silent placeholder so the pipeline doesn't break
            out_path.write_bytes(b"")
        return out_path

    # ── Audio processing ──────────────────────────────────────────────────────

    def adjust_audio_speed(
        self,
        audio_path: Path,
        target_duration: float,
    ) -> Path:
        """
        Speed-up or slow-down the audio to fit within *target_duration* seconds.
        Uses pydub for adjustment.

        Args:
            audio_path:       Input audio path.
            target_duration:  Desired duration in seconds.

        Returns:
            Path to the adjusted audio file.
        """
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(str(audio_path))
            current_duration = len(audio) / 1000.0  # ms → s

            if abs(current_duration - target_duration) < 1.0:
                return audio_path  # Already close enough

            speed_factor = current_duration / target_duration
            speed_factor = max(1, min(speed_factor, 1.5))  # Clamp to reasonable range

            # pydub doesn't have native speed change; we use frame rate trick
            adjusted = audio._spawn(
                audio.raw_data,
                overrides={"frame_rate": int(audio.frame_rate * speed_factor)},
            ).set_frame_rate(audio.frame_rate)

            out_path = audio_path.with_stem(audio_path.stem + "_adjusted")
            adjusted.export(str(out_path), format="mp3")
            logger.info(f"Audio adjusted {current_duration:.1f}s → {target_duration:.1f}s (×{speed_factor:.2f})")
            return out_path

        except ImportError:
            logger.warning("pydub not installed; audio speed not adjusted")
            return audio_path
        except Exception as exc:
            logger.warning(f"Audio speed adjustment failed: {exc}")
            return audio_path

    def add_voice_effects(self, audio_path: Path) -> Path:
        """
        Post-process the voiceover:
        - Normalise volume levels
        - Apply subtle EQ/warmth (bass boost with pydub)

        Args:
            audio_path: Input audio file.

        Returns:
            Path to processed audio file.
        """
        try:
            from pydub import AudioSegment
            from pydub.effects import normalize

            audio = AudioSegment.from_file(str(audio_path))
            audio = normalize(audio)

            # Slight low-frequency boost for warmth
            audio = audio.low_pass_filter(8000)   # remove harsh highs
            audio = audio + 2                      # +2 dB overall

            out_path = audio_path.with_stem(audio_path.stem + "_processed")
            audio.export(str(out_path), format="mp3", bitrate="192k")
            logger.info(f"Voice effects applied: {out_path.name}")
            return out_path

        except ImportError:
            logger.warning("pydub not installed; voice effects skipped")
            return audio_path
        except Exception as exc:
            logger.warning(f"Voice effects failed: {exc}")
            return audio_path
