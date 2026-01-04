import gradio as gr
import os
from types import SimpleNamespace
from v2t import V2T
from pathlib import Path


# Function to run V2T
def run_v2t(url, engine, model, language, task, output_format, keep_audio):
    if not url:
        return "Please enter a video URL.", [], ""

    # Construct CLI command for display
    cmd = f'./v2t.py "{url}" --engine {engine}'
    if engine == "whisper":
        cmd += f" --model {model}"
    if language:
        cmd += f" --language {language}"
    cmd += f" --task {task} --format {output_format}"
    if keep_audio:
        cmd += " --keep-audio"

    # Create args
    args = SimpleNamespace(
        urls=[url],
        engine=engine,
        model=model,
        language=language if language else None,
        task=task,
        output="./output",
        device="cpu",  # Force CPU for now or add option
        keep_audio=keep_audio,
        format=output_format,
        cookies=None,
    )

    try:
        app = V2T(args)
        app.run()

        # Find generated files
        output_dir = Path("./output")
        if not output_dir.exists():
            return "Output directory not found.", [], cmd

        # Sort by modification time
        files = sorted(output_dir.iterdir(), key=os.path.getmtime, reverse=True)

        # Filter recently modified files (last 2 minutes?) or just top 5
        recent_files = [str(f) for f in files[:5]]

        return (
            f"Successfully processed: {url}\nCheck the files below.",
            recent_files,
            cmd,
        )

    except Exception as e:
        return f"Error: {str(e)}", [], cmd


# Define Gradio Interface
with gr.Blocks(title="Video2Text WebUI") as demo:
    gr.Markdown("# Video2Text WebUI")
    gr.Markdown("Convert Video to Text using Whisper or FunASR (SenseVoice).")

    with gr.Row():
        with gr.Column():
            url_input = gr.Textbox(
                label="Video URL", placeholder="https://www.youtube.com/watch?v=..."
            )

            with gr.Accordion("Configuration", open=True):
                engine_input = gr.Dropdown(
                    choices=["whisper", "funasr"],
                    value="whisper",
                    label="ASR Engine",
                    info="Whisper: General purpose (OpenAI). FunASR: Optimized for Chinese (Alibaba).",
                )

                model_input = gr.Dropdown(
                    choices=["tiny", "base", "small", "medium", "large-v3"],
                    value="small",
                    label="Whisper Model Size",
                    info="Ignored if using FunASR.",
                )

                language_input = gr.Textbox(
                    label="Language (Optional)",
                    placeholder="e.g., 'zh', 'en'. Leave empty for auto-detection.",
                )

                task_input = gr.Dropdown(
                    choices=["transcribe", "translate"],
                    value="transcribe",
                    label="Task",
                    info="Translate will translate to English.",
                )

                format_input = gr.Dropdown(
                    choices=["txt", "srt", "all"], value="txt", label="Output Format"
                )

                keep_audio_input = gr.Checkbox(label="Keep Audio File", value=False)

            submit_btn = gr.Button("Start Processing", variant="primary")

        with gr.Column():
            command_output = gr.Textbox(label="CLI Command", interactive=False)
            output_log = gr.Textbox(label="Status Log")
            output_files = gr.File(label="Generated Files")

    submit_btn.click(
        fn=run_v2t,
        inputs=[
            url_input,
            engine_input,
            model_input,
            language_input,
            task_input,
            format_input,
            keep_audio_input,
        ],
        outputs=[output_log, output_files, command_output],
    )

if __name__ == "__main__":
    demo.launch(share=False)
