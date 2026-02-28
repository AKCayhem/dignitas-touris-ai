"""
Agent 6 – Music Agent
Sources royalty-free background music from Pixabay Music API or the
Free Music Archive, then mixes it with the voiceover at a low volume.
Falls back to a numpy-generated ambient drone if all downloads fail.
"""

import time
import math
from pathlib import Path
from typing import Optional

import requests
import numpy as np

import config
from utils.logger import logger
from utils.file_manager import get_output_path, timestamped_filename


class MusicAgent:
    """Provides royalty-free background music and mixes it with the voiceover."""

    PIXABAY_MUSIC_URL = "https://pixabay.com/api/videos/music/"  # same key as images

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TourismAgent/1.0"})
        logger.info("MusicAgent ready")

    # ── Music sourcing ────────────────────────────────────────────────────────

    async def search_pixabay_music(
        self,
        mood: str = "inspiring",
        genre: str = "cinematic",
    ) -> Path:
        """
        Search and download a royalty-free track from Pixabay Music.

        Args:
            mood:  Mood tag (e.g. 'inspiring', 'happy', 'epic').
            genre: Genre tag (e.g. 'cinematic', 'ambient', 'travel').

        Returns:
            Path to the downloaded MP3.
        """
        if not config.PIXABAY_API_KEY:
            logger.warning("Pixabay API key missing; using generated music")
            return self._generate_ambient_music(duration=65)

        try:
            resp = self.session.get(
                self.PIXABAY_MUSIC_URL,
                params={
                    "key":      config.PIXABAY_API_KEY,
                    "q":        f"{mood} {genre} travel",
                    "per_page": 10,
                },
                timeout=15,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])

            if not hits:
                logger.warning("No Pixabay music results; trying 'ambient'")
                return await self.search_pixabay_music(mood="ambient", genre="background")

            # Pick the first result
            track = hits[0]
            audio_url = track.get("audio", "")
            if not audio_url:
                raise ValueError("No audio URL in response")

            fname = f"music_{track['id']}.mp3"
            out_path = self.download_free_music(audio_url, fname)
            logger.info(f"Pixabay music downloaded: {out_path.name}")
            return out_path

        except Exception as exc:
            logger.warning(f"Pixabay music search failed: {exc}")
            return self._generate_ambient_music(duration=65)

    def download_free_music(self, url: str, filename: str) -> Path:
        """
        Download a royalty-free music file from a direct URL.

        Args:
            url:      Direct download URL.
            filename: Destination file name.

        Returns:
            Path to the saved file.
        """
        out_path = get_output_path("audio", filename)
        if out_path.exists():
            return out_path

        try:
            resp = self.session.get(url, timeout=60, stream=True)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            logger.info(f"Music file saved: {out_path.name}")
            return out_path
        except Exception as exc:
            logger.warning(f"Music download failed: {exc}")
            return self._generate_ambient_music(duration=65)

    # ── Audio mixing ──────────────────────────────────────────────────────────

    def mix_audio(
        self,
        voice_path: Path,
        music_path: Path,
        music_volume: float = 0.10,
    ) -> Path:
        """
        Mix voiceover and background music.
        Music is ducked to *music_volume* so the voice is clearly audible.
        Music fades in (2 s) and fades out (3 s).

        Args:
            voice_path:   Path to the voiceover MP3.
            music_path:   Path to the background music MP3.
            music_volume: Relative volume for music (0.0–1.0).

        Returns:
            Path to the mixed audio file.
        """
        try:
            from pydub import AudioSegment

            voice = AudioSegment.from_file(str(voice_path))
            music = AudioSegment.from_file(str(music_path))

            # Sync music length to voice
            music = self._sync_to_duration(music, len(voice))

            # Reduce music volume
            reduction_db = 20 * math.log10(max(music_volume, 1e-9))
            music = music + reduction_db  # pydub uses dB

            # Fade in / out
            music = music.fade_in(2000).fade_out(3000)

            # Mix
            mixed = voice.overlay(music)

            fname = timestamped_filename("mixed_audio", "mp3")
            out_path = get_output_path("audio", fname)
            mixed.export(str(out_path), format="mp3", bitrate="192k")
            logger.info(f"Audio mixed: {out_path.name}")
            return out_path

        except ImportError:
            logger.warning("pydub not installed; returning voice without music")
            return voice_path
        except Exception as exc:
            logger.warning(f"Audio mix failed: {exc}")
            return voice_path

    def sync_music_to_video(self, music_path: Path, video_duration: float) -> Path:
        """
        Trim or loop the music so it exactly matches the video length.

        Args:
            music_path:     Input music file.
            video_duration: Target duration in seconds.

        Returns:
            Path to the synced music file.
        """
        target_ms = int(video_duration * 1000)

        try:
            from pydub import AudioSegment
            music = AudioSegment.from_file(str(music_path))
            synced = self._sync_to_duration(music, target_ms)
            out_path = music_path.with_stem(music_path.stem + "_synced")
            synced.export(str(out_path), format="mp3", bitrate="192k")
            return out_path
        except Exception as exc:
            logger.warning(f"Music sync failed: {exc}")
            return music_path

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _sync_to_duration(audio_segment, target_ms: int):
        """Loop or trim a pydub AudioSegment to exactly *target_ms* milliseconds."""
        current = len(audio_segment)
        if current >= target_ms:
            return audio_segment[:target_ms]
        # Loop
        loops_needed = math.ceil(target_ms / current)
        looped = audio_segment * loops_needed
        return looped[:target_ms]

    def _generate_ambient_music(self, duration: float = 65.0) -> Path:
        """
        Generate a simple ambient drone using numpy + scipy when no music
        can be downloaded. This is a last-resort fallback.

        Args:
            duration: Track length in seconds.

        Returns:
            Path to the generated WAV file (converted to MP3 if pydub available).
        """
        try:
            from scipy.io.wavfile import write as wav_write
            from scipy.signal import butter, lfilter

            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

            # Ambient chord: root + fifth + octave at 174 Hz (healing frequency)
            freqs = [174.0, 261.0, 348.0, 440.0]
            wave = sum(
                0.15 * np.sin(2 * np.pi * f * t + np.random.uniform(0, 0.1))
                for f in freqs
            )

            # Slow amplitude envelope (breathing effect)
            envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t)
            wave = (wave * envelope * 0.6).astype(np.float32)

            # Low-pass filter for warmth
            b, a = butter(4, 2000 / (sample_rate / 2), btype="low")
            wave = lfilter(b, a, wave).astype(np.float32)

            # Normalise
            peak = np.max(np.abs(wave))
            if peak > 0:
                wave = wave / peak * 0.7

            wave_int = (wave * 32767).astype(np.int16)
            stereo = np.column_stack([wave_int, wave_int])

            wav_path = get_output_path("audio", "ambient_generated.wav")
            wav_write(str(wav_path), sample_rate, stereo)

            # Convert to MP3 if pydub available
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_wav(str(wav_path))
                mp3_path = wav_path.with_suffix(".mp3")
                audio.export(str(mp3_path), format="mp3", bitrate="128k")
                wav_path.unlink(missing_ok=True)
                logger.info(f"Generated ambient music: {mp3_path.name}")
                return mp3_path
            except Exception:
                logger.info(f"Generated ambient music (WAV): {wav_path.name}")
                return wav_path

        except Exception as exc:
            logger.error(f"Music generation failed: {exc}")
            # Return an empty file so the pipeline doesn't crash
            silent_path = get_output_path("audio", "silent.mp3")
            if not silent_path.exists():
                silent_path.write_bytes(b"")
            return silent_path
