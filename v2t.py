#!/usr/bin/env python
import argparse
import os
import sys
import shutil
import re
import tempfile
import subprocess
from pathlib import Path
import logging
from typing import Optional, Tuple, List, Any, cast
from dataclasses import dataclass
import yt_dlp

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Supported media formats for local file processing
SUPPORTED_VIDEO_FORMATS = {".mp4", ".mkv", ".avi", ".mov"}
SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".flac", ".m4a"}
SUPPORTED_MEDIA_FORMATS = SUPPORTED_VIDEO_FORMATS | SUPPORTED_AUDIO_FORMATS


@dataclass
class Segment:
    start: float
    end: float
    text: str


class FFmpegError(Exception):
    pass


class TranscriberEngine:
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        task: str = "transcribe",
        hotwords: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> List[Segment]:
        raise NotImplementedError


class WhisperEngine(TranscriberEngine):
    def __init__(self, model_size: str, device: str):
        try:
            import faster_whisper
        except ImportError:
            raise ImportError("faster-whisper is not installed. Please run 'pip install faster-whisper'.")

        self.model_size = model_size
        self.device = device
        self.compute_type = "int8" if device == "cpu" else "float16"
        print(f"[Transcriber] Loading Whisper model '{model_size}' on {device}...")
        self.model = faster_whisper.WhisperModel(
            model_size, device=device, compute_type=self.compute_type
        )

    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        task: str = "transcribe",
        hotwords: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> List[Segment]:
        print(f"[Transcriber] Transcribing '{audio_path.name}' with Whisper...")
        if hotwords:
            print(f"[Transcriber] Using hotwords: {hotwords}")
        if initial_prompt:
            print(f"[Transcriber] Using initial_prompt: {initial_prompt}")

        # Build transcribe kwargs
        transcribe_kwargs = {
            "beam_size": 5,
            "language": language,
            "task": task,
            "initial_prompt": initial_prompt,
        }
        # Add hotwords if provided (faster-whisper uses 'hotwords' parameter)
        if hotwords:
            transcribe_kwargs["hotwords"] = hotwords

        segments_generator, info = self.model.transcribe(
            str(audio_path),
            **transcribe_kwargs,
        )

        print(
            f"[Transcriber] Detected language: {info.language} (Probability: {info.language_probability:.2f})"
        )

        result_segments = []
        from tqdm import tqdm

        # Use tqdm for progress
        with tqdm(total=info.duration, unit="s", desc="Transcribing") as pbar:
            for segment in segments_generator:
                # Convert faster_whisper segment to our internal Segment
                result_segments.append(
                    Segment(start=segment.start, end=segment.end, text=segment.text)
                )
                pbar.update(segment.end - pbar.n)

        return result_segments


# FunASR model mapping
# Note: For long audio, we use VAD + Paraformer + Punctuation combination
FUNASR_MODELS = {
    "sensevoicesmall": "iic/SenseVoiceSmall",
    "paraformer-large": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    # For long audio, use the same base model but with VAD enabled
    "paraformer-zh": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
}

# VAD and Punctuation models for long audio processing
FUNASR_VAD_MODEL = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
FUNASR_PUNC_MODEL = "iic/punc_ct-transformer_cn-en-common-vocab471067-large"


class FunASREngine(TranscriberEngine):
    def __init__(self, model_name: str = "sensevoicesmall", device: str = "cpu"):
        try:
            from funasr import AutoModel
        except ImportError:
            raise ImportError("funasr is not installed. Please run 'pip install -r requirements.txt'.")

        self.device = device

        # Resolve model name from mapping or use as-is if it's a full model path
        model_key = model_name.lower()
        if model_key in FUNASR_MODELS:
            self.model_name = FUNASR_MODELS[model_key]
            self.model_type = model_key
        else:
            # Allow direct model path for advanced users
            self.model_name = model_name
            self.model_type = "sensevoicesmall"  # Default parsing mode

        # Determine if this is a SenseVoice or Paraformer model
        self.is_sensevoice = "sensevoice" in self.model_name.lower()
        self.is_paraformer = "paraformer" in self.model_name.lower()
        # Check if this model needs VAD for long audio processing
        self.use_vad = model_key == "paraformer-zh"

        print(f"[Transcriber] Loading FunASR model '{self.model_name}' on {device}...")
        if self.use_vad:
            print("[Transcriber] VAD enabled for long audio processing")

        try:
            # Build model kwargs
            model_kwargs = {
                "model": self.model_name,
                "device": device,
                "disable_update": True,
            }

            # For paraformer-zh (long audio), enable VAD and punctuation models
            if self.use_vad:
                model_kwargs["vad_model"] = FUNASR_VAD_MODEL
                model_kwargs["punc_model"] = FUNASR_PUNC_MODEL

            self.model = AutoModel(**model_kwargs)
        except Exception as e:
            logger.error(f"Failed to load FunASR model: {e}")
            raise RuntimeError(f"Failed to load FunASR model: {e}") from e

    def _parse_sensevoice_output(self, text: str) -> List[Segment]:
        """
        Parse SenseVoice output with timestamps tags like <|1.23|>.
        Example: <|0.00|> <|zh|> ... <|0.00|>Welcome<|0.50|> to<|1.00|>
        """
        # Remove header tags like <|zh|>, <|NEUTRAL|>, etc.
        # But keep time tags.

        # 1. Clean up header tags (language, emotion, event) but keep time tags
        # Typical header: <|0.00|> <|zh|> <|NEUTRAL|> <|0.00|>
        # We want to remove <|zh|>, <|NEUTRAL|>, <|speech|>, etc.
        # But be careful not to remove <|1.23|>

        # Remove non-digit tags
        clean_text = re.sub(r"<\|[a-zA-Z]+\|>", "", text)
        clean_text = re.sub(r"<\|[A-Z]+\|>", "", clean_text)  # NEUTRAL etc

        # 2. Split by timestamp tags
        parts = re.split(r"(<\|\d+\.\d+\|>)", clean_text)

        raw_tokens = []  # List of (time, text)
        current_time = 0.0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if re.match(r"<\|\d+\.\d+\|>", part):
                try:
                    t_val = float(part[2:-2])
                    current_time = t_val
                except ValueError:
                    pass
            else:
                # This is text content associated with the PREVIOUS timestamp
                # Note: SenseVoice format is typically <|time|>text<|next_time|>
                # So 'current_time' is the start time of this text.
                if part:
                    raw_tokens.append((current_time, part))

        # 3. Merge tokens into segments
        segments = []
        if not raw_tokens:
            return segments

        current_seg_text = []
        current_seg_start = raw_tokens[0][0]

        for i, (t, txt) in enumerate(raw_tokens):
            current_seg_text.append(txt)

            # Decide whether to split into a new segment
            # Condition 1: Punctuation end
            is_end_of_sentence = re.search(r"[.!?。！？]$", txt)

            # Condition 2: Long duration pause?
            # If next token starts much later than current token time?
            # Hard to guess duration of current token without next token time.
            # But we can look at the gap if we want.

            # Condition 3: Length limit
            is_long_enough = len("".join(current_seg_text)) > 80

            should_split = is_end_of_sentence or is_long_enough

            if should_split:
                # Determine end time
                if i + 1 < len(raw_tokens):
                    end_time = raw_tokens[i + 1][0]
                else:
                    # Last token, add heuristic duration
                    end_time = t + max(1.0, len(txt) * 0.2)

                # Create segment
                full_text = "".join(current_seg_text)
                segments.append(
                    Segment(start=current_seg_start, end=end_time, text=full_text)
                )

                # Reset for next segment
                if i + 1 < len(raw_tokens):
                    current_seg_start = raw_tokens[i + 1][0]
                current_seg_text = []

        # Flush remaining
        if current_seg_text:
            # Last segment
            segments.append(
                Segment(
                    start=current_seg_start,
                    end=raw_tokens[-1][0] + 1.0,
                    text="".join(current_seg_text),
                )
            )

        return segments

    def _parse_paraformer_output(self, result_item: dict) -> List[Segment]:
        """
        Parse Paraformer model output with timestamps.
        Paraformer returns: {'text': '...', 'timestamp': [[start1, end1], [start2, end2], ...], 'sentences': [...]}
        For long audio, it may return sentences with timestamps.
        """
        segments = []
        text = result_item.get("text", "")
        timestamps = result_item.get("timestamp", [])
        sentences = result_item.get("sentence_info", [])

        # If sentences are available (for paraformer-large-long), use them
        if sentences:
            for sent in sentences:
                start = sent.get("start", 0) / 1000.0  # Convert ms to seconds
                end = sent.get("end", 0) / 1000.0
                sent_text = sent.get("text", "")
                if sent_text:
                    segments.append(Segment(start=start, end=end, text=sent_text))
        elif timestamps and text:
            # For character/word level timestamps, merge into segments
            # timestamps format: [[start_ms, end_ms], ...]
            # We need to merge into sentence-level segments
            words = list(text)
            if len(timestamps) == len(words):
                # Build segments by grouping words
                current_text = []
                current_start = None
                current_end = None

                for i, (word, ts) in enumerate(zip(words, timestamps)):
                    start_ms, end_ms = ts
                    if current_start is None:
                        current_start = start_ms / 1000.0

                    current_text.append(word)
                    current_end = end_ms / 1000.0

                    # Split on sentence-ending punctuation or length
                    is_end = re.search(r"[.!?。！？]$", word)
                    is_long = len("".join(current_text)) > 60

                    if is_end or is_long:
                        segments.append(
                            Segment(
                                start=current_start,
                                end=current_end,
                                text="".join(current_text),
                            )
                        )
                        current_text = []
                        current_start = None
                        current_end = None

                # Flush remaining
                if current_text:
                    segments.append(
                        Segment(
                            start=current_start or 0.0,
                            end=current_end or 0.0,
                            text="".join(current_text),
                        )
                    )
            else:
                # Fallback: just use text with estimated timing
                segments.append(Segment(start=0.0, end=0.0, text=text))
        elif text:
            # No timestamps, just text
            segments.append(Segment(start=0.0, end=0.0, text=text))

        return segments

    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        task: str = "transcribe",
        hotwords: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> List[Segment]:
        model_display = "Paraformer" if self.is_paraformer else "SenseVoice"
        print(
            f"[Transcriber] Transcribing '{audio_path.name}' with FunASR ({model_display})..."
        )
        if hotwords:
            print(f"[Transcriber] Using hotwords: {hotwords}")
        if initial_prompt:
            logger.warning("initial_prompt is not supported by FunASR engine yet.")

        # Build generate kwargs based on model type
        if self.is_paraformer:
            # Paraformer-specific parameters
            generate_kwargs = {
                "input": str(audio_path),
                "cache": {},
                "batch_size_s": 300,  # Paraformer can handle longer batches
            }
            # Add hotwords if provided
            if hotwords:
                generate_kwargs["hotword"] = hotwords
        else:
            # SenseVoice parameters
            # Note: SenseVoice auto-detects language, but we can pass language if needed.
            # language param in generate: "auto", "zh", "en", "yue", "ja", "ko"
            lang_param = language if language else "auto"
            generate_kwargs = {
                "input": str(audio_path),
                "cache": {},
                "language": lang_param,
                "use_itn": True,
                "batch_size_s": 60,
                "merge_vad": True,
                "merge_length_s": 15,
            }
            # Add hotwords if provided
            if hotwords:
                generate_kwargs["hotword"] = hotwords

        try:
            res = self.model.generate(**generate_kwargs)
        except Exception as e:
            logger.error(f"FunASR Inference failed: {e}")
            return []

        all_segments = []

        if isinstance(res, list):
            for item in res:
                if self.is_paraformer:
                    # Use Paraformer-specific parsing
                    segments = self._parse_paraformer_output(item)
                else:
                    # Use SenseVoice parsing (text with embedded timestamps)
                    text_with_tags = item.get("text", "")
                    segments = self._parse_sensevoice_output(text_with_tags)
                all_segments.extend(segments)

        return all_segments


class V2T:
    def __init__(self, args):
        self.args = args
        self.output_dir = Path(args.output)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path("temp_audio")
        self.temp_dir.mkdir(exist_ok=True)

        # Handle cookies with temp file to avoid modification
        self.cookies_file = None
        self._temp_cookie_file = None

        original_cookies = self.args.cookies
        if not original_cookies and os.path.exists("cookies.txt"):
            original_cookies = "cookies.txt"

        if original_cookies and os.path.exists(original_cookies):
            try:
                fd, temp_path = tempfile.mkstemp(prefix="v2t_cookies_", suffix=".txt")
                os.close(fd)
                shutil.copy2(original_cookies, temp_path)
                self.cookies_file = temp_path
                self._temp_cookie_file = temp_path
                logger.debug(f"Created temp cookies file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to create temp cookies file: {e}")
                self.cookies_file = original_cookies

        # Initialize engine
        if self.args.engine == "funasr":
            funasr_model = getattr(self.args, "funasr_model", "sensevoicesmall")
            self.transcriber = FunASREngine(
                model_name=funasr_model, device=self.args.device
            )
        else:
            self.transcriber = WhisperEngine(
                model_size=self.args.model, device=self.args.device
            )

    def cleanup(self):
        """Cleanup temporary files."""
        if self._temp_cookie_file and os.path.exists(self._temp_cookie_file):
            try:
                os.remove(self._temp_cookie_file)
                logger.debug(f"Removed temp cookies file: {self._temp_cookie_file}")
                self._temp_cookie_file = None
            except OSError as e:
                logger.warning(f"Failed to remove temp cookies file: {e}")

        if self.temp_dir.exists() and not any(self.temp_dir.iterdir()):
            try:
                self.temp_dir.rmdir()
            except:
                pass

    def __del__(self):
        self.cleanup()

    def check_ffmpeg(self):
        """Check if FFmpeg is installed."""
        if not shutil.which("ffmpeg"):
            error_message = "Error: FFmpeg is not installed. "
            if sys.platform == "win32":
                error_message += "Please install it using: winget install ffmpeg. "
            error_message += "Or download from https://ffmpeg.org/download.html and add to PATH."
            raise FFmpegError(error_message)

    def sanitize_filename(self, name: str) -> str:
        """Sanitize filename to prevent issues."""
        clean_name = re.sub(r'[\\/*?:"<>|]', "_", name)
        clean_name = "".join(ch for ch in clean_name if ord(ch) >= 32)
        return clean_name.strip()

    def is_local_file(self, path_or_url: str) -> bool:
        """Check if the input is a local file path (not a URL)."""
        # Check if it looks like a URL
        if path_or_url.startswith(("http://", "https://", "www.")):
            return False
        # Check if it's an existing file with supported format
        path = Path(path_or_url)
        if path.exists() and path.is_file():
            return path.suffix.lower() in SUPPORTED_MEDIA_FORMATS
        return False

    def is_local_folder(self, path_str: str) -> bool:
        """Check if the input is a local folder path."""
        if path_str.startswith(("http://", "https://", "www.")):
            return False
        path = Path(path_str)
        return path.exists() and path.is_dir()

    def scan_folder(self, folder_path: str, recursive: bool = False) -> List[str]:
        """Scan a folder for supported media files.

        Args:
            folder_path: Path to the folder to scan
            recursive: If True, scan subfolders recursively

        Returns:
            List of absolute file paths for supported media files
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            logger.error(f"Folder not found: {folder_path}")
            return []

        media_files = []

        if recursive:
            # Use rglob for recursive scanning
            for ext in SUPPORTED_MEDIA_FORMATS:
                # Case-insensitive matching for Windows
                media_files.extend(folder.rglob(f"*{ext}"))
                media_files.extend(folder.rglob(f"*{ext.upper()}"))
        else:
            # Use glob for top-level only
            for ext in SUPPORTED_MEDIA_FORMATS:
                media_files.extend(folder.glob(f"*{ext}"))
                media_files.extend(folder.glob(f"*{ext.upper()}"))

        # Remove duplicates and sort
        unique_files = sorted(set(str(f.resolve()) for f in media_files))

        if unique_files:
            print(
                f"[Scanner] Found {len(unique_files)} media file(s) in '{folder_path}'"
            )
            for f in unique_files:
                print(f"  - {Path(f).name}")
        else:
            print(f"[Scanner] No media files found in '{folder_path}'")

        return unique_files

    def process_local_file(self, file_path: str) -> Tuple[Optional[Path], str]:
        """Process a local media file, extracting audio if needed.

        For video files: Extract audio to mp3 using FFmpeg
        For audio files: Use directly (or convert if needed)

        Returns:
            Tuple of (audio_path, original_filename_stem)
            audio_path is None if processing failed
        """
        source_path = Path(file_path)
        original_stem = source_path.stem  # filename without extension

        print(f"\n[LocalFile] Processing: {source_path.name}")

        suffix = source_path.suffix.lower()

        # For audio files that are directly supported, no conversion needed
        if suffix in {".mp3", ".wav", ".flac", ".m4a"}:
            print(
                f"[LocalFile] Audio file detected, using directly: {source_path.name}"
            )
            return source_path, original_stem

        # For video files, extract audio using FFmpeg
        if suffix in SUPPORTED_VIDEO_FORMATS:
            print(f"[LocalFile] Video file detected, extracting audio...")
            # Create temp audio file
            temp_audio_path = self.temp_dir / f"{original_stem}_extracted.mp3"

            try:
                # Use FFmpeg to extract audio
                cmd = [
                    "ffmpeg",
                    "-i",
                    str(source_path),
                    "-vn",  # No video
                    "-acodec",
                    "libmp3lame",
                    "-ab",
                    "192k",
                    "-ar",
                    "16000",  # 16kHz for ASR
                    "-ac",
                    "1",  # Mono
                    "-y",  # Overwrite
                    str(temp_audio_path),
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                if result.returncode != 0:
                    logger.error(f"FFmpeg extraction failed: {result.stderr}")
                    return None, original_stem

                if temp_audio_path.exists():
                    print(f"[LocalFile] Audio extracted: {temp_audio_path.name}")
                    return temp_audio_path, original_stem
                else:
                    logger.error("FFmpeg completed but output file not found")
                    return None, original_stem

            except Exception as e:
                logger.error(f"Failed to extract audio from {source_path.name}: {e}")
                return None, original_stem

        # Unsupported format
        logger.error(f"Unsupported file format: {suffix}")
        return None, original_stem

    def _extract_audio_ffmpeg(self, input_path: Path) -> Optional[Path]:
        """Extract audio from a downloaded media file using FFmpeg.

        Converts to mono 16kHz mp3 suitable for ASR.

        Returns:
            Path to the extracted mp3 file, or None on failure.
        """
        output_path = input_path.with_suffix(".mp3")
        # Skip if input is already the target mp3
        if input_path.suffix.lower() == ".mp3" and input_path == output_path:
            return input_path

        try:
            cmd = [
                "ffmpeg",
                "-i", str(input_path),
                "-vn",              # No video
                "-acodec", "libmp3lame",
                "-ab", "192k",
                "-ar", "16000",     # 16kHz for ASR
                "-ac", "1",         # Mono
                "-y",               # Overwrite
                str(output_path),
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if result.returncode != 0:
                logger.error(f"FFmpeg audio extraction failed: {result.stderr}")
                return None

            if output_path.exists():
                # Remove original downloaded file to save space
                if input_path != output_path:
                    try:
                        os.remove(input_path)
                    except OSError:
                        pass
                return output_path
            return None
        except Exception as e:
            logger.error(f"FFmpeg audio extraction error: {e}")
            return None

    def download_audio(self, url: str) -> Tuple[Optional[Path], str, str, str, str]:
        """Download audio from video URL using yt-dlp.

        Strategy: try bestaudio first; if the source doesn't offer a
        standalone audio stream (common on YouTube for some regions/accounts),
        fall back to downloading a low-quality video with good audio and then
        extract the audio track with FFmpeg.

        Returns:
            Tuple of (audio_path, title, video_id, upload_date, uploader)
        """
        print(f"\n[Downloader] Processing: {url}")
        out_tmpl = str(self.temp_dir / "%(title)s_%(id)s.%(ext)s")

        # Format preference chain:
        #   1) bestaudio          – pure audio stream (smallest, best quality)
        #   2) worstvideo+bestaudio – low-res video muxed with best audio
        #   3) worst              – absolute fallback, smallest available file
        ydl_opts = {
            "format": "bestaudio/worstvideo*+bestaudio/worst",
            "outtmpl": out_tmpl,
            "quiet": True,
            "no_warnings": True,
            "cookiefile": self.cookies_file,
            "restrictfilenames": True,
            "noplaylist": True,  # 防止 Bilibili 播放列表导致元信息丢失
        }

        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = Path(ydl.prepare_filename(info))

                # yt-dlp may merge into mkv/webm; locate the actual file
                if not downloaded_file.exists():
                    # Try common extensions
                    for ext in (".mkv", ".webm", ".mp4", ".m4a", ".opus", ".mp3"):
                        candidate = downloaded_file.with_suffix(ext)
                        if candidate.exists():
                            downloaded_file = candidate
                            break
                    else:
                        # Glob by video id
                        possible = list(self.temp_dir.glob(f"*{info['id']}*"))
                        if possible:
                            downloaded_file = possible[0]
                        else:
                            raise FileNotFoundError(
                                "Downloaded file not found after yt-dlp."
                            )

                print(f"[Downloader] Downloaded: {downloaded_file.name}")

                # Extract audio with FFmpeg (handles both pure-audio and video files)
                audio_path = self._extract_audio_ffmpeg(downloaded_file)
                if audio_path is None:
                    raise RuntimeError(
                        f"Failed to extract audio from {downloaded_file.name}"
                    )

                # Extract video metadata
                title = str(info.get("title") or "Untitled")
                video_id = str(info.get("id") or "")
                upload_date = info.get("upload_date") or ""
                upload_date = str(upload_date) if upload_date else ""
                uploader = info.get("uploader") or info.get("channel") or ""
                uploader = str(uploader) if uploader else ""

                print(f"[Downloader] Audio ready: {audio_path.name}")
                print(
                    f"[Downloader] Video info - Date: {upload_date}, Author: {uploader}"
                )
                return audio_path, title, video_id, upload_date, uploader
        except Exception as e:
            logger.error(f"Download failed for {url}: {str(e)}")
            return None, "", "", "", ""

    def format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def write_srt(self, segments: List[Segment], output_path: Path):
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_time = self.format_time(segment.start)
                end_time = self.format_time(segment.end)
                text = segment.text.strip()
                f.write(f"{i}\n{start_time} --> {end_time}\n{text}\n\n")

    def write_txt(self, segments: List[Segment], output_path: Path):
        with open(output_path, "w", encoding="utf-8") as f:
            for segment in segments:
                f.write(f"{segment.text.strip()}\n")

    def run(self):
        try:
            self._run_internal()
        finally:
            self.cleanup()

    def _run_internal(self):
        self.check_ffmpeg()

        # Collect all tasks: can be URLs, local files, or folders
        local_files = []  # List of local file paths
        urls = []  # List of URLs

        recursive = getattr(self.args, "recursive", False)

        for input_arg in self.args.inputs:
            # Check if it's a text file containing URLs/paths
            if os.path.isfile(input_arg) and Path(input_arg).suffix.lower() == ".txt":
                with open(input_arg, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # Check each line
                        if self.is_local_file(line):
                            local_files.append(line)
                        elif self.is_local_folder(line):
                            local_files.extend(self.scan_folder(line, recursive))
                        else:
                            urls.append(line)
            # Check if it's a local media file
            elif self.is_local_file(input_arg):
                local_files.append(input_arg)
            # Check if it's a folder
            elif self.is_local_folder(input_arg):
                local_files.extend(self.scan_folder(input_arg, recursive))
            # Otherwise treat as URL
            else:
                urls.append(input_arg)

        total_tasks = len(local_files) + len(urls)
        if total_tasks == 0:
            print("No valid inputs provided.")
            return

        print(
            f"Found {total_tasks} task(s): {len(local_files)} local file(s), {len(urls)} URL(s)."
        )

        # Get hotwords and initial_prompt from args
        hotwords = getattr(self.args, "hotwords", None)
        initial_prompt = getattr(self.args, "initial_prompt", None)

        if hotwords:
            print(f"[Config] Hotwords enabled: {hotwords}")
        if initial_prompt:
            print(f"[Config] Initial prompt enabled: {initial_prompt}")

        # Process local files first
        for file_path in local_files:
            audio_path, original_stem = self.process_local_file(file_path)
            is_temp_audio = False

            if audio_path:
                # Check if this is a temporary extracted audio (from video)
                source_suffix = Path(file_path).suffix.lower()
                if source_suffix in SUPPORTED_VIDEO_FORMATS:
                    is_temp_audio = True

                segments = self.transcriber.transcribe(
                    audio_path,
                    language=self.args.language,
                    task=self.args.task,
                    hotwords=hotwords,
                    initial_prompt=initial_prompt,
                )

                if segments:
                    # For local files, use original filename as output name
                    safe_stem = self.sanitize_filename(original_stem)
                    output_base = self.output_dir / safe_stem

                    if self.args.format in ["txt", "all"]:
                        txt_path = output_base.with_suffix(".txt")
                        self.write_txt(segments, txt_path)
                        print(f"[Output] Saved TXT: {txt_path}")

                    if self.args.format in ["srt", "all"]:
                        srt_path = output_base.with_suffix(".srt")
                        self.write_srt(segments, srt_path)
                        print(f"[Output] Saved SRT: {srt_path}")

                # Cleanup temporary extracted audio (not original files!)
                if is_temp_audio and not self.args.keep_audio:
                    try:
                        os.remove(audio_path)
                        print(f"[Cleanup] Removed temporary audio: {audio_path.name}")
                    except OSError as e:
                        logger.warning(f"Failed to remove {audio_path}: {e}")

            print("-" * 50)

        # Process URLs
        for url in urls:
            audio_path, title, video_id, upload_date, uploader = self.download_audio(
                url
            )
            if audio_path:
                segments = self.transcriber.transcribe(
                    audio_path,
                    language=self.args.language,
                    task=self.args.task,
                    hotwords=hotwords,
                    initial_prompt=initial_prompt,
                )

                if segments:
                    # Build filename: {date}_{author}_{title}_{video_id}
                    # Format date from YYYYMMDD to YYYY-MM-DD for readability
                    date_part = ""
                    if upload_date and len(upload_date) == 8:
                        date_part = (
                            f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                        )

                    # Sanitize all parts
                    safe_title = self.sanitize_filename(title)
                    safe_uploader = self.sanitize_filename(uploader) if uploader else ""

                    # Build filename parts list (only include non-empty parts)
                    name_parts = []
                    if date_part:
                        name_parts.append(date_part)
                    if safe_uploader:
                        name_parts.append(safe_uploader)
                    if safe_title:
                        name_parts.append(safe_title)
                    if video_id:
                        name_parts.append(video_id)

                    # Join with underscore
                    output_filename = "_".join(name_parts) if name_parts else "output"
                    output_base = self.output_dir / output_filename

                    if self.args.format in ["txt", "all"]:
                        txt_path = output_base.with_suffix(".txt")
                        self.write_txt(segments, txt_path)
                        print(f"[Output] Saved TXT: {txt_path}")

                    if self.args.format in ["srt", "all"]:
                        srt_path = output_base.with_suffix(".srt")
                        self.write_srt(segments, srt_path)
                        print(f"[Output] Saved SRT: {srt_path}")

                if not self.args.keep_audio:
                    try:
                        os.remove(audio_path)
                        print(f"[Cleanup] Removed temporary audio: {audio_path.name}")
                    except OSError as e:
                        logger.warning(f"Failed to remove {audio_path}: {e}")
            print("-" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Video2Text CLI - Video to Text Converter"
    )

    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="INPUT",
        help="Video URLs, local media files, folders, or path to .txt file containing URLs/paths. "
        "Supported formats: MP4, MKV, AVI, MOV (video); MP3, WAV, FLAC, M4A (audio)",
    )
    parser.add_argument(
        "--engine",
        default="whisper",
        choices=["whisper", "funasr"],
        help="ASR engine to use: 'whisper' (default) or 'funasr' (SenseVoice)",
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size (default: small). Ignored for FunASR.",
    )
    parser.add_argument(
        "--funasr-model",
        default="sensevoicesmall",
        choices=["sensevoicesmall", "paraformer-large", "paraformer-zh"],
        dest="funasr_model",
        help="FunASR model to use (default: sensevoicesmall). 'paraformer-large' for high-accuracy Chinese ASR, 'paraformer-zh' for long audio with VAD support.",
    )
    parser.add_argument("--language", help="Source language code (e.g., 'en', 'zh')")
    parser.add_argument(
        "--task",
        default="transcribe",
        choices=["transcribe", "translate"],
        help="Task type (default: transcribe)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--device", default="cpu", help="Device to run on (default: cpu)"
    )
    parser.add_argument(
        "--keep-audio", action="store_true", help="Keep downloaded audio files"
    )
    parser.add_argument(
        "--format",
        default="txt",
        choices=["txt", "srt", "all"],
        help="Output format (default: txt)",
    )
    parser.add_argument("--cookies", help="Path to cookies.txt file (Netscape format)")
    parser.add_argument(
        "--hotwords",
        help="Hotwords to boost recognition (comma-separated or space-separated words, e.g., 'GPT,LLM,Transformer' or '人工智能 机器学习')",
    )
    parser.add_argument(
        "--initial-prompt",
        help="Initial prompt to provide context to the model (Whisper only). Useful for guiding punctuation or vocabulary.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan subfolders when a folder path is provided",
    )

    args = parser.parse_args()

    app = V2T(args)
    app.run()


if __name__ == "__main__":
    main()
