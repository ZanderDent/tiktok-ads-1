import os
import requests
import uuid
from pathlib import Path
import textwrap

def text_to_speech(input_text, voice="alloy", format="mp3"):
    max_length = 4096
    audio_chunks = []

    # Split the text into smaller chunks
    if len(input_text) > max_length:
        text_parts = textwrap.wrap(input_text, max_length, break_long_words=False)
    else:
        text_parts = [input_text]

    for part in text_parts:
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={"model": "tts-1", "input": part, "voice": voice, "response_format": format}
        )
        audio_chunks.append(response.content)

    combined_audio_path = Path(f"./generated_files/speech_{uuid.uuid4()}.{format}")
    combined_audio_path.parent.mkdir(parents=True, exist_ok=True)

    with open(combined_audio_path, "wb") as f:
        for chunk in audio_chunks:
            f.write(chunk)

    return str(combined_audio_path)
