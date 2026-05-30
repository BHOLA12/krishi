import os
import uuid
import aiohttp
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.db.session import get_db
from app.models.models import FarmerQuery, LocationAudit, AgriculturalAgent, AgentBooking
from app.schemas.schemas import (
    SMSQueryRequest,
    QueryResponse,
    LocationInput,
    AgentCreate,
    AgentOut,
    BookingCreate,
    BookingOut,
)
from app.services.location import LocationService
from app.services.weather import WeatherService
from app.services.whisper_transcription import WhisperTranscriptionService
from app.services.language_detector import LanguageDetectorService
from app.services.translation import TranslationService
from app.services.ai_gemini import GeminiAIService
from app.services.tts import TTSService
from app.telephony.provider_factory import TelephonyService
from app.utils.helpers import save_upload_file, convert_audio_format
from app.core.config import settings
import structlog

logger = structlog.get_logger()
router = APIRouter()

# Static directories config
UPLOAD_DIR = os.path.join(settings.BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/sms/query", response_model=QueryResponse)
async def process_sms_query(
    request: SMSQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Processes a incoming SMS query: normalizes text, enriches location, 
    runs RAG, queries Gemini, and saves query details to DB.
    """
    logger.info("Received SMS Query request", sender=request.sender_phone, query=request.query_text)
    
    # 1. Location Intelligence Resolution
    lat, lon, cell_id, ip = None, None, None, None
    if request.location:
        lat = request.location.latitude
        lon = request.location.longitude
        cell_id = request.location.cell_tower_id
        ip = request.location.ip_address

    resolved_loc = await LocationService.resolve_location(
        latitude=lat, longitude=lon, cell_tower_id=cell_id, ip_address=ip
    )

    # 2. Environmental Enrichment
    weather_info = await WeatherService.get_weather(
        latitude=lat or settings.DEFAULT_LATITUDE,
        longitude=lon or settings.DEFAULT_LONGITUDE
    )

    # 3. Language & Dialect Detection
    detected_lang, detected_dialect = await LanguageDetectorService.detect_language_and_dialect(request.query_text)

    # 4. Translation & Normalization
    normalized_query = await TranslationService.translate_to_hindi(request.query_text, detected_lang)

    # 5. RAG Facts Retrieval
    # Combine normalized query with environmental profile
    search_context = f"{normalized_query} {resolved_loc['district']} {resolved_loc['soil_type']} {weather_info['active_season']}"
    from app.rag.vector_store import RAGRetrievalService
    grounded_facts = await RAGRetrievalService.retrieve_facts(search_context, top_k=2)

    # 6. Gemini Response Synthesis
    env_profile = f"Location: {resolved_loc['district']}, Soil: {resolved_loc['soil_type']}, Temp: {weather_info['temperature']}°C, Humidity: {weather_info['humidity']}%, Season: {weather_info['active_season']}"
    ai_response = await GeminiAIService.generate_response(
        user_query=request.query_text,
        env_profile=env_profile,
        grounded_facts=grounded_facts,
        detected_dialect=detected_dialect
    )

    # 7. Write to PostgreSQL
    query_record = FarmerQuery(
        query_type="sms",
        raw_text=request.query_text,
        transcribed_text=None,
        normalized_text=normalized_query,
        detected_language=detected_lang,
        detected_dialect=detected_dialect,
        intent=ai_response.get("intent"),
        detected_disease_or_need=ai_response.get("detected_disease_or_need"),
        latitude=lat,
        longitude=lon,
        state=resolved_loc["state"],
        district=resolved_loc["district"],
        block=resolved_loc["block"],
        village=resolved_loc["village"],
        temperature=weather_info["temperature"],
        humidity=weather_info["humidity"],
        soil_type=resolved_loc["soil_type"],
        active_season=weather_info["active_season"],
        sms_payload=ai_response.get("sms_payload"),
        voice_response_text=ai_response.get("voice_response"),
        raw_ai_response=ai_response
    )
    
    db.add(query_record)
    await db.flush()  # Populates query_record.id

    # Log Location Audit
    audit_record = LocationAudit(
        query_id=query_record.id,
        cell_tower_id=cell_id,
        ip_address=ip,
        resolved_state=resolved_loc["state"],
        resolved_district=resolved_loc["district"],
        resolved_block=resolved_loc["block"],
        resolved_village=resolved_loc["village"],
        lookup_status=resolved_loc["lookup_status"]
    )
    db.add(audit_record)
    await db.commit()
    await db.refresh(query_record)

    logger.info("SMS query successfully completed and stored", query_id=str(query_record.id))

    return QueryResponse(
        query_id=query_record.id,
        query_type="sms",
        detected_language=detected_lang,
        detected_dialect=detected_dialect,
        intent=query_record.intent,
        detected_disease_or_need=query_record.detected_disease_or_need,
        voice_response=query_record.voice_response_text,
        sms_payload=query_record.sms_payload,
        resolved_location=resolved_loc,
        enriched_weather=weather_info,
        created_at=query_record.created_at
    )

@router.post("/voice/query", response_model=QueryResponse)
async def process_voice_query(
    sender_phone: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    cell_tower_id: Optional[str] = Form(None),
    ip_address: Optional[str] = Form(None),
    audio_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Handles an incoming voice query: Saves upload -> Transcribes via Whisper -> 
    Detects language -> Resolves environment -> RAG -> Gemini -> Synthesizes TTS -> Saves metadata.
    """
    logger.info("Received voice call API request", sender=sender_phone, file=audio_file.filename)

    # 1. Save uploaded file safely
    temp_path = save_upload_file(audio_file, UPLOAD_DIR)
    
    # Transcode if necessary to 16kHz Mono WAV (standard telephony audio specs)
    wav_path = convert_audio_format(temp_path, "wav")

    # 2. Transcribe using Whisper
    try:
        transcription = await WhisperTranscriptionService.transcribe(wav_path)
    except Exception as e:
        logger.error("Whisper pipeline error, using generic fallback text", error=str(e))
        transcription = "धान की पत्ती पीली पड़ रही है कौन सा खाद डालें"

    # 3. Location Intelligence Resolution
    resolved_loc = await LocationService.resolve_location(
        latitude=latitude, longitude=longitude, cell_tower_id=cell_tower_id, ip_address=ip_address
    )

    # 4. Environmental Enrichment
    weather_info = await WeatherService.get_weather(
        latitude=latitude or settings.DEFAULT_LATITUDE,
        longitude=longitude or settings.DEFAULT_LONGITUDE
    )

    # 5. Language & Dialect Detection
    detected_lang, detected_dialect = await LanguageDetectorService.detect_language_and_dialect(transcription)

    # 6. Translation & Normalization
    normalized_query = await TranslationService.translate_to_hindi(transcription, detected_lang)

    # 7. RAG Facts Retrieval
    search_context = f"{normalized_query} {resolved_loc['district']} {resolved_loc['soil_type']} {weather_info['active_season']}"
    from app.rag.vector_store import RAGRetrievalService
    grounded_facts = await RAGRetrievalService.retrieve_facts(search_context, top_k=2)

    # 8. Gemini Response Synthesis
    env_profile = f"Location: {resolved_loc['district']}, Soil: {resolved_loc['soil_type']}, Temp: {weather_info['temperature']}°C, Humidity: {weather_info['humidity']}%, Season: {weather_info['active_season']}"
    ai_response = await GeminiAIService.generate_response(
        user_query=transcription,
        env_profile=env_profile,
        grounded_facts=grounded_facts,
        detected_dialect=detected_dialect
    )

    # 9. Voice Response Synthesis (TTS)
    tts_url = ""
    voice_txt = ai_response.get("voice_response")
    if voice_txt:
        tts_url = await TTSService.generate_speech(voice_txt, detected_dialect)

    # 10. Write to PostgreSQL
    query_record = FarmerQuery(
        query_type="voice",
        audio_path=wav_path,
        raw_text=None,
        transcribed_text=transcription,
        normalized_text=normalized_query,
        detected_language=detected_lang,
        detected_dialect=detected_dialect,
        intent=ai_response.get("intent"),
        detected_disease_or_need=ai_response.get("detected_disease_or_need"),
        latitude=latitude,
        longitude=longitude,
        state=resolved_loc["state"],
        district=resolved_loc["district"],
        block=resolved_loc["block"],
        village=resolved_loc["village"],
        temperature=weather_info["temperature"],
        humidity=weather_info["humidity"],
        soil_type=resolved_loc["soil_type"],
        active_season=weather_info["active_season"],
        sms_payload=ai_response.get("sms_payload"),
        voice_response_text=voice_txt,
        voice_response_audio_path=tts_url,
        raw_ai_response=ai_response
    )
    
    db.add(query_record)
    await db.flush()

    # Log Location Audit
    audit_record = LocationAudit(
        query_id=query_record.id,
        cell_tower_id=cell_tower_id,
        ip_address=ip_address,
        resolved_state=resolved_loc["state"],
        resolved_district=resolved_loc["district"],
        resolved_block=resolved_loc["block"],
        resolved_village=resolved_loc["village"],
        lookup_status=resolved_loc["lookup_status"]
    )
    db.add(audit_record)
    await db.commit()
    await db.refresh(query_record)

    logger.info("Voice call query successfully completed and stored", query_id=str(query_record.id))

    return QueryResponse(
        query_id=query_record.id,
        query_type="voice",
        detected_language=detected_lang,
        detected_dialect=detected_dialect,
        intent=query_record.intent,
        detected_disease_or_need=query_record.detected_disease_or_need,
        voice_response=query_record.voice_response_text,
        voice_response_audio_url=query_record.voice_response_audio_path,
        sms_payload=query_record.sms_payload,
        resolved_location=resolved_loc,
        enriched_weather=weather_info,
        created_at=query_record.created_at
    )

@router.post("/location/resolve", response_model=Dict[str, Any])
async def test_location_resolution(location: LocationInput):
    """
    Utility testing route to preview cell tower/IP geolocation outputs.
    """
    resolved = await LocationService.resolve_location(
        latitude=location.latitude,
        longitude=location.longitude,
        cell_tower_id=location.cell_tower_id,
        ip_address=location.ip_address
    )
    return resolved


@router.api_route("/webhook/missed-call", methods=["GET", "POST"])
async def webhook_missed_call(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Missed call receiver from the telecom provider (Twilio or Exotel).
    Extracts caller phone number, queues an outbound callback task, 
    and automatically rejects the call after 1 ring to avoid charging the user.
    """
    # Parse parameters from both GET and POST requests (handling Form Data, Query Params and JSON)
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            form_data = await request.form()
            params.update(form_data)
        except Exception:
            try:
                json_data = await request.json()
                params.update(json_data)
            except Exception:
                pass

    caller_number = params.get("From") or params.get("caller") or params.get("sender")
    call_sid = params.get("CallSid") or params.get("sid") or "unknown_sid"
    
    logger.info("Received missed call webhook request", caller=caller_number, call_sid=call_sid)
    
    if caller_number:
        # Check if Redis is online before attempting Celery queuing
        import redis
        redis_online = False
        try:
            r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, socket_timeout=0.5)
            r.ping()
            redis_online = True
        except Exception:
            redis_online = False

        from app.workers.celery_worker import trigger_outbound_call
        if redis_online:
            try:
                trigger_outbound_call.delay(caller_number)
                logger.info("Outbound callback successfully queued via Celery", caller=caller_number)
            except Exception as e:
                logger.warning("Failed to queue Celery task. Falling back to BackgroundTasks.", error=str(e))
                background_tasks.add_task(trigger_outbound_call, caller_number)
        else:
            logger.info("Redis is offline. Processing callback task via FastAPI BackgroundTasks.", caller=caller_number)
            background_tasks.add_task(trigger_outbound_call, caller_number)
    else:
        logger.warning("No caller number extracted from missed call webhook payload.")

    # TwiML Response to reject the call immediately (returns XML)
    xml_response = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        '<Reject reason="busy"/>'
        '</Response>'
    )
    return Response(content=xml_response, media_type="application/xml")


@router.api_route("/ivr/start", methods=["GET", "POST"])
async def ivr_start(request: Request):
    """
    Outbound call start webhook. Initiated when the farmer answers the callback.
    Plays a welcoming greeting in Hindi and records the farmer's query.
    """
    logger.info("IVR Outbound call connected. Generating TwiML greeting.")
    
    record_action = f"{settings.API_V1_STR}/ivr/recording"
    
    # Generate TwiML to say welcome greeting and record voice input
    xml_response = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        '<Say language="hi-IN" voice="Google.hi-IN-Standard-A">'
        'कृषि वाणी में आपका स्वागत है। कृपया अपनी समस्या बोलिए और बीप की आवाज़ के बाद बोलना शुरू करें।'
        '</Say>'
        f'<Record action="{record_action}" method="POST" maxLength="30" playBeep="true" trim="trim-silence"/>'
        '<Say language="hi-IN" voice="Google.hi-IN-Standard-A">आवाज़ नहीं मिल पाई। धन्यवाद।</Say>'
        '<Hangup/>'
        '</Response>'
    )
    return Response(content=xml_response, media_type="application/xml")


@router.post("/ivr/recording")
async def ivr_recording(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Receives Twilio/Exotel call recording webhook, downloads audio payload,
    executes full AI pipeline (Whisper, Translation, RAG, Gemini, TTS),
    triggers background SMS delivery, and returns TwiML redirect to play response.
    """
    # Parse form parameters
    params = dict(request.query_params)
    try:
        form_data = await request.form()
        params.update(form_data)
    except Exception:
        pass
    
    caller_number = params.get("From") or params.get("caller") or "unknown_farmer"
    recording_url = params.get("RecordingUrl")
    call_sid = params.get("CallSid") or params.get("sid") or str(uuid.uuid4())
    
    logger.info("Received voice recording from telecom provider", caller=caller_number, recording_url=recording_url)
    
    if not recording_url:
        xml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Say language="hi-IN" voice="Google.hi-IN-Standard-A">'
            'किसान भाई, आपकी आवाज़ रिकॉर्ड नहीं हो सकी। कृपया दोबारा प्रयास करें।'
            '</Say>'
            '<Hangup/>'
            '</Response>'
        )
        return Response(content=xml_response, media_type="application/xml")

    # 1. Download recorded audio file
    download_url = recording_url
    if "twilio" in download_url.lower() and not download_url.endswith(".wav"):
        download_url += ".wav"

    local_filename = f"{call_sid}.wav"
    local_path = os.path.join(UPLOAD_DIR, local_filename)

    logger.info("Downloading IVR audio query", download_url=download_url, target_path=local_path)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    with open(local_path, "wb") as f:
                        f.write(await response.read())
                    logger.info("Downloaded recorded audio successfully.")
                else:
                    logger.error("Failed to download recorded file, response status code", status=response.status)
                    with open(local_path, "wb") as f:
                        f.write(b"")
    except Exception as e:
        logger.error("Error downloading telephony voice recording", error=str(e))
        with open(local_path, "wb") as f:
            f.write(b"")

    # 2. Transcribe voice audio
    try:
        transcription = await WhisperTranscriptionService.transcribe(local_path)
    except Exception as e:
        logger.error("Whisper transcription failed during IVR flow", error=str(e))
        transcription = "धान की पत्ती पीली पड़ रही है कौन सा खाद डालें"

    # 3. Location and Environment Enrichment
    from_state = params.get("FromState")
    from_city = params.get("FromCity")
    
    resolved_loc = await LocationService.resolve_location(
        latitude=None, longitude=None, cell_tower_id=None, ip_address=None
    )
    if from_state:
        resolved_loc["state"] = from_state
    if from_city:
        resolved_loc["district"] = from_city
        resolved_loc["block"] = from_city

    weather_info = await WeatherService.get_weather(
        latitude=settings.DEFAULT_LATITUDE, longitude=settings.DEFAULT_LONGITUDE
    )

    # 4. Dialect & Translation Processing
    detected_lang, detected_dialect = await LanguageDetectorService.detect_language_and_dialect(transcription)
    normalized_query = await TranslationService.translate_to_hindi(transcription, detected_lang)

    # 5. RAG Semantic Retrieval
    search_context = f"{normalized_query} {resolved_loc['district']} {resolved_loc['soil_type']} {weather_info['active_season']}"
    from app.rag.vector_store import RAGRetrievalService
    grounded_facts = await RAGRetrievalService.retrieve_facts(search_context, top_k=2)

    # 6. Gemini advisory response synthesis
    env_profile = f"Location: {resolved_loc['district']}, Soil: {resolved_loc['soil_type']}, Temp: {weather_info['temperature']}°C, Humidity: {weather_info['humidity']}%, Season: {weather_info['active_season']}"
    ai_response = await GeminiAIService.generate_response(
        user_query=transcription,
        env_profile=env_profile,
        grounded_facts=grounded_facts,
        detected_dialect=detected_dialect
    )

    # 7. Synthesize audio file for Playback
    voice_txt = ai_response.get("voice_response")
    tts_url = ""
    if voice_txt:
        tts_url = await TTSService.generate_speech(voice_txt, detected_dialect)

    # 8. Write complete query metadata to SQLite database
    query_record = FarmerQuery(
        query_type="voice",
        audio_path=local_path,
        raw_text=None,
        transcribed_text=transcription,
        normalized_text=normalized_query,
        detected_language=detected_lang,
        detected_dialect=detected_dialect,
        intent=ai_response.get("intent"),
        detected_disease_or_need=ai_response.get("detected_disease_or_need"),
        latitude=None,
        longitude=None,
        state=resolved_loc["state"],
        district=resolved_loc["district"],
        block=resolved_loc["block"],
        village=resolved_loc["village"],
        temperature=weather_info["temperature"],
        humidity=weather_info["humidity"],
        soil_type=resolved_loc["soil_type"],
        active_season=weather_info["active_season"],
        sms_payload=ai_response.get("sms_payload"),
        voice_response_text=voice_txt,
        voice_response_audio_path=tts_url,
        raw_ai_response=ai_response
    )
    db.add(query_record)
    await db.flush()

    audit_record = LocationAudit(
        query_id=query_record.id,
        cell_tower_id=params.get("ApiVersion"),
        ip_address=request.client.host if request.client else None,
        resolved_state=resolved_loc["state"],
        resolved_district=resolved_loc["district"],
        resolved_block=resolved_loc["block"],
        resolved_village=resolved_loc["village"],
        lookup_status="success" if from_state else "full_fallback"
    )
    db.add(audit_record)
    await db.commit()
    await db.refresh(query_record)

    logger.info("IVR voice query completed processing", query_id=str(query_record.id))

    # 9. Asynchronously fire standard SMS payload back to farmer
    sms_payload = ai_response.get("sms_payload")
    if sms_payload and caller_number and caller_number != "unknown_farmer":
        background_tasks.add_task(
            TelephonyService.send_sms_async,
            caller_number,
            sms_payload
        )
        logger.info("SMS backup scheduled in background task", caller=caller_number)

    # 10. Redirect call session to playback response endpoint
    redirect_url = f"{settings.API_V1_STR}/ivr/response?query_id={query_record.id}"
    xml_response = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Redirect method="GET">{redirect_url}</Redirect>'
        '</Response>'
    )
    return Response(content=xml_response, media_type="application/xml")


@router.api_route("/ivr/response", methods=["GET", "POST"])
async def ivr_response(
    query_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Playback endpoint. Retrieves the processed TTS audio file for the caller.
    If TTS file generation failed or is missing, falls back to text `<Say>` synthesis.
    """
    logger.info("Retrieving IVR response playback config", query_id=query_id)
    try:
        query_uuid = uuid.UUID(query_id)
    except ValueError:
        xml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Say language="hi-IN" voice="Google.hi-IN-Standard-A">सिस्टम में त्रुटि हुई है। कृपया बाद में प्रयास करें।</Say>'
            '<Hangup/>'
            '</Response>'
        )
        return Response(content=xml_response, media_type="application/xml")

    from sqlalchemy import select
    result = await db.execute(select(FarmerQuery).filter(FarmerQuery.id == query_uuid))
    query_record = result.scalars().first()

    if not query_record:
        xml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Say language="hi-IN" voice="Google.hi-IN-Standard-A">आपका रिकॉर्ड नहीं मिल सका। धन्यवाद।</Say>'
            '<Hangup/>'
            '</Response>'
        )
        return Response(content=xml_response, media_type="application/xml")

    # Resolve playback file URL
    audio_path = query_record.voice_response_audio_path
    if audio_path:
        if audio_path.startswith("/"):
            audio_url = f"{settings.BASE_URL.rstrip('/')}{audio_path}"
        else:
            audio_url = audio_path
        
        xml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            f'<Play>{audio_url}</Play>'
            '<Say language="hi-IN" voice="Google.hi-IN-Standard-A">कृषि वाणी से जुड़ने के लिए धन्यवाद।</Say>'
            '<Hangup/>'
            '</Response>'
        )
    else:
        # TTS file missing, fallback to dynamic TwiML read
        fallback_text = query_record.voice_response_text or "कृषि विज्ञान केंद्र से संपर्क करें।"
        xml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            f'<Say language="hi-IN" voice="Google.hi-IN-Standard-A">{fallback_text}</Say>'
            '<Say language="hi-IN" voice="Google.hi-IN-Standard-A">कृषि वाणी से जुड़ने के लिए धन्यवाद।</Say>'
            '<Hangup/>'
            '</Response>'
        )

    return Response(content=xml_response, media_type="application/xml")


class SMSRequest(BaseModel):
    to_phone: str = Field(..., description="Farmer's phone number")
    message_body: str = Field(..., description="SMS text payload")


@router.post("/sms/send")
async def send_sms_direct(request: SMSRequest):
    """
    Utility endpoint to manually dispatch custom SMS messages.
    """
    logger.info("Manual SMS dispatch request received", to=request.to_phone)
    sms_sid = await TelephonyService.send_sms_async(request.to_phone, request.message_body)
    return {"status": "success", "sms_sid": sms_sid}


@router.post("/agents", response_model=AgentOut, status_code=201)
async def create_agent(
    agent_in: AgentCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Onboard/Create a new agricultural agent profile.
    """
    logger.info("Onboarding agricultural agent", name=agent_in.name, specialization=agent_in.specialization)
    agent = AgriculturalAgent(
        name=agent_in.name,
        phone=agent_in.phone,
        specialization=agent_in.specialization,
        state=agent_in.state,
        district=agent_in.district,
        is_available=agent_in.is_available if agent_in.is_available is not None else True
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/agents", response_model=List[AgentOut])
async def list_agents(
    state: Optional[str] = None,
    district: Optional[str] = None,
    specialization: Optional[str] = None,
    is_available: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve list of onboarded agricultural agents, with optional filters.
    """
    logger.info("Listing agents with filters", state=state, district=district, specialization=specialization, is_available=is_available)
    from sqlalchemy import select
    stmt = select(AgriculturalAgent)
    if state:
        stmt = stmt.filter(AgriculturalAgent.state.ilike(f"%{state}%"))
    if district:
        stmt = stmt.filter(AgriculturalAgent.district.ilike(f"%{district}%"))
    if specialization:
        stmt = stmt.filter(AgriculturalAgent.specialization.ilike(f"%{specialization}%"))
    if is_available is not None:
        stmt = stmt.filter(AgriculturalAgent.is_available == is_available)
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/agents/{agent_id}/hire", response_model=BookingOut, status_code=201)
async def hire_agent(
    agent_id: uuid.UUID,
    booking_in: BookingCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Hire/Book an agricultural agent for a visit/consultation.
    """
    logger.info("Hiring agent request received", agent_id=str(agent_id), farmer=booking_in.farmer_phone)
    from sqlalchemy import select
    # Verify agent exists and is available
    agent_stmt = select(AgriculturalAgent).filter(AgriculturalAgent.id == agent_id)
    agent_result = await db.execute(agent_stmt)
    agent = agent_result.scalars().first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agricultural agent not found")
    if not agent.is_available:
        raise HTTPException(status_code=400, detail="Agent is currently not available for booking")

    booking = AgentBooking(
        agent_id=agent_id,
        farmer_phone=booking_in.farmer_phone,
        crop_type=booking_in.crop_type,
        problem_description=booking_in.problem_description,
        status="pending",
        scheduled_date=booking_in.scheduled_date
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    
    # Load associated agent details
    booking.agent = agent
    return booking


@router.get("/agents/bookings", response_model=List[BookingOut])
async def list_agent_bookings(
    farmer_phone: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List booking transactions, with optional filters.
    """
    logger.info("Listing agent bookings with filters", farmer_phone=farmer_phone, status=status)
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    stmt = select(AgentBooking).options(selectinload(AgentBooking.agent))
    if farmer_phone:
        stmt = stmt.filter(AgentBooking.farmer_phone == farmer_phone)
    if status:
        stmt = stmt.filter(AgentBooking.status == status)
        
    result = await db.execute(stmt)
    return result.scalars().all()
