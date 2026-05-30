import os
import uuid
from gtts import gTTS
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Set up output static directories
AUDIO_STATIC_DIR = os.path.join(settings.BASE_DIR, "static", "audio")
os.makedirs(AUDIO_STATIC_DIR, exist_ok=True)

class TTSService:
    @staticmethod
    async def generate_speech(text: str, dialect: str = "Hindi") -> str:
        """
        Converts text output into audio format (.mp3 or .wav) saved to static directory.
        Adapts lang configuration dynamically. Falls back to gTTS (CPU friendly, fast).
        """
        filename = f"{uuid.uuid4()}.mp3"
        output_path = os.path.join(AUDIO_STATIC_DIR, filename)

        # Map dialects to primary TTS languages
        lang = "hi"  # Default Hindi
        if dialect in ["Bengali"]:
            lang = "bn"
        elif dialect in ["Tamil"]:
            lang = "ta"
        elif dialect in ["Telugu"]:
            lang = "te"

        # Production integration point for Bhashini TTS API
        api_key = settings.BHASHINI_API_KEY
        if api_key and api_key != "your_bhashini_api_key_here":
            try:
                # Structure payload representing Bhashini speech synthesis request
                # In real scenario, make a post request to Bhashini endpoint and save the byte stream.
                logger.info("Connecting to Bhashini TTS API...", lang=lang)
                # (For actual implementation, read Bhashini docs and handle byte streaming)
                pass
            except Exception as e:
                logger.error("Bhashini TTS engine failed. Falling back to local offline TTS.", error=str(e))

        try:
            logger.info("Generating TTS audio via gTTS", language=lang, path=output_path)
            # Use gTTS to synthesize the voice response
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(output_path)
            logger.info("Speech generation successful", file_path=output_path)
            
            # Returns relative URL path or local path depending on mounting
            return f"/static/audio/{filename}"
            
        except Exception as e:
            logger.error("TTS generation failed", error=str(e))
            # Return dummy path
            return ""
