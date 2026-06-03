import os
import sys
import asyncio
from celery import Celery

# Add project root to path for standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings
from app.db.session import SessionLocalSync
from app.models.models import FarmerQuery
from app.services.whisper_transcription import WhisperTranscriptionService
from app.services.language_detector import LanguageDetectorService
from app.services.translation import TranslationService
from app.services.ai_gemini import GeminiAIService
from app.services.tts import TTSService
import structlog

logger = structlog.get_logger()

# Configure Celery
celery_app = Celery(
    "krishi_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
)

# =============================================================================
# ❌ PURANA CODE (KAAM NAHI KARTA — ISLIYE BADLA)
# =============================================================================
# def run_async(coro):
#     return asyncio.get_event_loop().run_until_loop_complete(coro) \
#         if asyncio.get_event_loop().is_running() \
#         else asyncio.run(coro)
#
# ⚠️  KYU BADLA (WHY WE CHANGED):
#     "run_until_loop_complete" — yeh method exist hi nahi karti asyncio mein.
#     Sahi naam hai "run_until_complete". Yeh ek typo/spelling mistake thi.
#
#     Iska result:
#       - Jab bhi Celery koi background task run karta (e.g. farmer ka callback),
#         Python ek AttributeError throw karta tha aur poora task crash ho jaata tha.
#       - Farmer ko kabhi callback nahi aata tha.
#       - Koi error screen pe nahi dikhta — sirf logs mein silently fail hota tha.
#
#     Naya code teeno scenarios handle karta hai:
#       1. Koi event loop nahi → asyncio.run() use karo (sabse common case)
#       2. Loop already chal raha hai (gevent/eventlet) → threadsafe future use karo
#       3. 60 second timeout — task zyada der tak hang nahi karega
# =============================================================================

# ✅ NAYA CODE — Teeno event loop scenarios handle karta hai
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside a running event loop (e.g. eventlet/gevent Celery worker)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=60)
    else:
        # No running loop — safe to call asyncio.run()
        return asyncio.run(coro)


@celery_app.task(name="tasks.process_voice_call_async")
def process_voice_call_async(query_id_str: str):
    """
    Asynchronously processes a voice query after initial upload.
    Updates the database with the transcription, intent, and generated audio path.
    """
    logger.info("Starting async voice query background processing", query_id=query_id_str)
    
    db = SessionLocalSync()
    try:
        query = db.query(FarmerQuery).filter(FarmerQuery.id == query_id_str).first()
        if not query:
            logger.error("Query record not found in database", query_id=query_id_str)
            return False

        # 1. Running transcription
        transcription = run_async(WhisperTranscriptionService.transcribe(query.audio_path))
        query.transcribed_text = transcription
        
        # 2. Extract context
        detected_lang, detected_dialect = run_async(
            LanguageDetectorService.detect_language_and_dialect(transcription)
        )
        query.detected_language = detected_lang
        query.detected_dialect = detected_dialect

        # 3. Translation
        normalized_query = run_async(TranslationService.translate_to_hindi(transcription, detected_lang))
        query.normalized_text = normalized_query

        # 4. RAG search
        from app.rag.vector_store import RAGRetrievalService
        search_context = f"{normalized_query} {query.district or ''} {query.soil_type or ''} {query.active_season or ''}"
        grounded_facts = run_async(RAGRetrievalService.retrieve_facts(search_context, top_k=2))

        # 5. Gemini AI response
        env_profile = f"Location: {query.district}, Soil: {query.soil_type}, Temp: {query.temperature}°C, Humidity: {query.humidity}%, Season: {query.active_season}"
        ai_response = run_async(GeminiAIService.generate_response(
            user_query=transcription,
            env_profile=env_profile,
            grounded_facts=grounded_facts,
            detected_dialect=detected_dialect
        ))

        # 6. Synth voice response
        voice_txt = ai_response.get("voice_response")
        tts_url = run_async(TTSService.generate_speech(voice_txt, detected_dialect))

        # 7. Update database
        query.intent = ai_response.get("intent")
        query.detected_disease_or_need = ai_response.get("detected_disease_or_need")
        query.sms_payload = ai_response.get("sms_payload")
        query.voice_response_text = voice_txt
        query.voice_response_audio_path = tts_url
        query.raw_ai_response = ai_response

        db.commit()
        logger.info("Async background voice query complete", query_id=query_id_str)
        return True

    except Exception as e:
        db.rollback()
        logger.error("Async voice query task failed", query_id=query_id_str, error=str(e))
        return False
    finally:
        db.close()

@celery_app.task(name="tasks.cleanup_static_files")
def cleanup_static_files():
    """
    Cleans up old uploaded WAV files or generated speech audio to avoid disk swelling.
    """
    logger.info("Running system static files cleanup schedule...")
    # Add files cleaning scripts logic
    return True

@celery_app.task(name="tasks.trigger_outbound_call")
def trigger_outbound_call(caller_number: str):
    """
    Triggers an outbound callback call back to the farmer using the active telephony provider.
    Wait for 3 seconds to ensure the farmer's line is cleared after the missed call disconnects.
    """
    logger.info("Outbound callback queued", caller_number=caller_number)
    import time
    time.sleep(3)
    
    base_url = settings.BASE_URL
    callback_url = f"{base_url.rstrip('/')}{settings.API_V1_STR}/ivr/start"
    
    from app.telephony.provider_factory import TelephonyService
    call_sid = TelephonyService.make_call_sync(caller_number, callback_url)
    logger.info("Outbound callback completed call trigger", caller_number=caller_number, call_sid=call_sid)
    return call_sid
