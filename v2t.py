#!/usr/bin/env python
import argparse
import os
import sys
import shutil
import re
from pathlib import Path
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass
import yt_dlp

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Segment:
    start: float
    end: float
    text: str


class TranscriberEngine:
    def transcribe(
        self, audio_path: Path, language: Optional[str] = None, task: str = "transcribe"
    ) -> List[Segment]:
        raise NotImplementedError


class WhisperEngine(TranscriberEngine):
    def __init__(self, model_size: str, device: str):
        try:
            import faster_whisper
        except ImportError:
            print("Error: faster-whisper not installed.")
            sys.exit(1)

        self.model_size = model_size
        self.device = device
        self.compute_type = "int8" if device == "cpu" else "float16"
        print(f"[Transcriber] Loading Whisper model '{model_size}' on {device}...")
        self.model = faster_whisper.WhisperModel(
            model_size, device=device, compute_type=self.compute_type
        )

    def transcribe(
        self, audio_path: Path, language: Optional[str] = None, task: str = "transcribe"
    ) -> List[Segment]:
        print(f"[Transcriber] Transcribing '{audio_path.name}' with Whisper...")

        segments_generator, info = self.model.transcribe(
            str(audio_path),
            beam_size=5,
            language=language,
            task=task,
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


class FunASREngine(TranscriberEngine):
    def __init__(self, model_name: str = "iic/SenseVoiceSmall", device: str = "cpu"):
        try:
            from funasr import AutoModel
        except ImportError:
            print("Error: funasr not installed. Run 'pip install -r requirements.txt'")
            sys.exit(1)

        self.device = device
        # Map whisper model sizes to funasr models if needed, but we default to SenseVoiceSmall
        # If user passed "large-v3" etc via --model, we ignore it or warn,
        # but for now we stick to SenseVoiceSmall as requested.
        self.model_name = "iic/SenseVoiceSmall"

        print(f"[Transcriber] Loading FunASR model '{self.model_name}' on {device}...")
        try:
            # Disable update to avoid network checks on every run if already downloaded
            self.model = AutoModel(
                model=self.model_name,
                device=device,
                disable_update=True,
                trust_remote_code=False,  # Based on our finding
            )
        except Exception as e:
            logger.error(f"Failed to load FunASR model: {e}")
            sys.exit(1)

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
        clean_text = re.sub(r'<\|[a-zA-Z]+\|>', '', text)
        clean_text = re.sub(r'<\|[A-Z]+\|>', '', clean_text) # NEUTRAL etc
        
        # 2. Split by timestamp tags
        parts = re.split(r'(<\|\d+\.\d+\|>)', clean_text)
        
        raw_tokens = [] # List of (time, text)
        current_time = 0.0
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if re.match(r'<\|\d+\.\d+\|>', part):
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
            is_end_of_sentence = re.search(r'[.!?。！？]$', txt)
            
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
                    end_time = raw_tokens[i+1][0]
                else:
                    # Last token, add heuristic duration
                    end_time = t + max(1.0, len(txt) * 0.2)
                
                # Create segment
                full_text = "".join(current_seg_text)
                segments.append(Segment(
                    start=current_seg_start,
                    end=end_time,
                    text=full_text
                ))
                
                # Reset for next segment
                if i + 1 < len(raw_tokens):
                    current_seg_start = raw_tokens[i+1][0]
                current_seg_text = []

        # Flush remaining
        if current_seg_text:
             # Last segment
             segments.append(Segment(
                start=current_seg_start,
                end=raw_tokens[-1][0] + 1.0,
                text="".join(current_seg_text)
            ))
            
        return segments

    def transcribe(
        self, audio_path: Path, language: Optional[str] = None, task: str = "transcribe"
    ) -> List[Segment]:
        print(
            f"[Transcriber] Transcribing '{audio_path.name}' with FunASR (SenseVoice)..."
        )

        # Note: SenseVoice auto-detects language, but we can pass language if needed.
        # language param in generate: "auto", "zh", "en", "yue", "ja", "ko"
        lang_param = language if language else "auto"

        try:
            # batch_size_s is chunk size for inference
            res = self.model.generate(
                input=str(audio_path),
                cache={},
                language=lang_param,
                use_itn=True,
                batch_size_s=60,
                merge_vad=True,
                merge_length_s=15,
            )
        except Exception as e:
            logger.error(f"FunASR Inference failed: {e}")
            return []

        all_segments = []

        if isinstance(res, list):
            for item in res:
                # item usually has 'text' with timestamps
                # We might also get 'timestamp' list if configured, but SenseVoice uses text tags
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

        # Initialize engine
        if self.args.engine == "funasr":
            self.transcriber = FunASREngine(device=self.args.device)
        else:
            self.transcriber = WhisperEngine(
                model_size=self.args.model, device=self.args.device
            )

    def check_ffmpeg(self):
        """Check if FFmpeg is installed."""
        if not shutil.which("ffmpeg"):
            print("Error: FFmpeg is not installed.")
            if sys.platform == "win32":
                print("Please install it using: winget install ffmpeg")
            print("Please download from https://ffmpeg.org/download.html and add to PATH")
            sys.exit(1)

    def sanitize_filename(self, name: str) -> str:
        """Sanitize filename to prevent issues."""
        clean_name = re.sub(r'[\\/*?:"<>|]', "_", name)
        clean_name = "".join(ch for ch in clean_name if ord(ch) >= 32)
        return clean_name.strip()

    def download_audio(self, url: str) -> Tuple[Optional[Path], str, str]:
        """Download audio from video URL using yt-dlp."""
        print(f"\n[Downloader] Processing: {url}")
        out_tmpl = str(self.temp_dir / "%(title)s_%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_tmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "cookiefile": (
                self.args.cookies
                if self.args.cookies
                else ("cookies.txt" if os.path.exists("cookies.txt") else None)
            ),
            "restrictfilenames": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                base_path = Path(filename).with_suffix(".mp3")

                if not base_path.exists():
                    possible_files = list(self.temp_dir.glob(f"*{info['id']}*.mp3"))
                    if possible_files:
                        base_path = possible_files[0]
                    else:
                        raise FileNotFoundError("Downloaded audio file not found.")

                print(f"[Downloader] Downloaded: {base_path.name}")
                return base_path, info.get("title", "Untitled"), info.get("id", "")
        except Exception as e:
            logger.error(f"Download failed for {url}: {str(e)}")
            return None, "", ""

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
        self.check_ffmpeg()

        urls = []
        for url_arg in self.args.urls:
            if os.path.isfile(url_arg):
                with open(url_arg, "r") as f:
                    urls.extend([line.strip() for line in f if line.strip()])
            else:
                urls.append(url_arg)

        if not urls:
            print("No URLs provided.")
            return

        print(f"Found {len(urls)} task(s).")

        for url in urls:
            audio_path, title, video_id = self.download_audio(url)
            if audio_path:
                segments = self.transcriber.transcribe(
                    audio_path, language=self.args.language, task=self.args.task
                )

                if segments:
                    safe_title = self.sanitize_filename(title)
                    if video_id and video_id not in safe_title:
                        safe_title = f"{safe_title}_{video_id}"

                    output_base = self.output_dir / safe_title

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

        if not any(self.temp_dir.iterdir()):
            try:
                self.temp_dir.rmdir()
            except:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="Video2Text CLI - Video to Text Converter"
    )

    parser.add_argument(
        "urls", nargs="+", help="Video URLs or path to .txt file containing URLs"
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

    args = parser.parse_args()

    app = V2T(args)
    app.run()


if __name__ == "__main__":
    main()
