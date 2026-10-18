from gtts import gTTS
import tempfile


async def text_to_speech(text: str, voice: str = "en") -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        mp3_path = f.name

    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(mp3_path)

    return mp3_path
