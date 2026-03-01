---
name: v2t-local
description: Download audio from online video URLs and transcribe to txt locally with Whisper via V2T. Default output is ~/Downloads/v2t-output. Supports tiny/small/base/medium/large model tiers.
metadata:
  {
    "openclaw":
      {
        "emoji": "🎬",
        "requires": { "anyBins": ["python3", "ffmpeg"] }
      }
  }
---

# V2T Local (OpenClaw Skill)

Use this skill when the user wants: **在线视频 URL → 本地 Whisper 转写 txt**.

## Defaults

- Output directory: `~/Downloads/v2t-output`
- Output format: `txt`
- Engine: `whisper` (through `v2t.py`)
- Model tiers: `tiny`, `small`, `base`, `medium`, `large`
  - `large` is mapped to V2T's `large-v3`

## Command

```bash
python3 /Users/yang/Documents/GitHub/V2T/openclaw-skill/v2t-local/run_v2t_local.py "<VIDEO_URL>" --model small
```

## Examples

Single URL:

```bash
python3 /Users/yang/Documents/GitHub/V2T/openclaw-skill/v2t-local/run_v2t_local.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --model tiny
```

Multiple URLs:

```bash
python3 /Users/yang/Documents/GitHub/V2T/openclaw-skill/v2t-local/run_v2t_local.py "https://..." "https://..." --model medium
```

Custom output directory:

```bash
python3 /Users/yang/Documents/GitHub/V2T/openclaw-skill/v2t-local/run_v2t_local.py "https://..." --model large --output ~/Downloads/my-v2t
```

With cookies:

```bash
python3 /Users/yang/Documents/GitHub/V2T/openclaw-skill/v2t-local/run_v2t_local.py "https://..." --cookies /Users/yang/Documents/GitHub/V2T/cookies.txt
```

## Notes

- First run for a model downloads weights (can be slow).
- If URL is region/member restricted, pass `--cookies`.
- Output filenames follow V2T naming logic.
