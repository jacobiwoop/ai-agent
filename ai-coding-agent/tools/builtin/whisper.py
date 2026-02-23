from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult


class TranscribeAudioParams(BaseModel):
    file_path: str = Field(
        ...,
        description="Absolute or relative path to the audio file to transcribe. Accepts .mp3, .mp4, .m4a, .wav, .ogg, .flac, .webm formats.",
    )


class WhisperTool(Tool):
    """
    Transcribes audio files (voice messages, recordings, etc.) to text using
    Groq's Whisper large-v3 model. Use this whenever the user sends a voice
    message or when an audio file needs to be read.
    """

    name = "transcribe_audio"
    description = (
        "Transcribe an audio file (voice note, recording) to text using Whisper. "
        "Use this when the user sends a voice message, or when you need to read "
        "the content of an audio file."
    )
    kind = ToolKind.READ
    schema = TranscribeAudioParams

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return False

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = TranscribeAudioParams(**invocation.params)

        groq_api_key = self.config.groq_api_key
        if not groq_api_key:
            return ToolResult.error_result(
                "GROQ_API_KEY is not configured. Please add it to your .env file."
            )

        audio_path = Path(params.file_path)
        if not audio_path.is_absolute():
            audio_path = Path(invocation.cwd) / audio_path

        if not audio_path.exists():
            return ToolResult.error_result(f"Audio file not found: {audio_path}")

        try:
            from groq import Groq

            client = Groq(api_key=groq_api_key)
            with open(audio_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=(audio_path.name, audio_file.read()),
                    model="whisper-large-v3",
                    temperature=0,
                    response_format="verbose_json",
                )
            return ToolResult.success_result(transcription.text)
        except Exception as e:
            return ToolResult.error_result(f"Transcription failed: {e}")
