# Krishi-Vani: Multilingual Rural Intelligence AI Platform for India

Krishi-Vani is a complete, production-grade, low-latency AI advisory system designed to support farmers across rural India. It handles user inputs from IVR voice calls and SMS queries using feature phones over low-bandwidth channels.

The backend automatically:
1. Receives voice or SMS query data.
2. Identifies regional languages & specific dialects (e.g. Bhojpuri, Maithili, Magahi, Awadhi).
3. Translates/normalizes query representations into standard Hindi.
4. Identifies location context (coordinates/cell tower ID/IP address) and enriches environmental indicators (weather, soil parameters, active seasonal data).
5. Executes semantic searches on a locally indexed FAISS Vector Database built from verified ICAR/KVK/Government repositories.
6. Generates high-confidence, zero-hallucination structured responses using the Gemini API.
7. Translates the advisory back to the user's dialect and generates IVR-ready voice streams (via TTS) alongside compact SMS copy.

---

## Technical Stack

- **Framework**: Python 3.11 + FastAPI
- **Database**: PostgreSQL (SQLAlchemy + Asyncpg async driver)
- **Vector Database**: FAISS (Sentence-Transformers `all-MiniLM-L6-v2` embeddings on CPU)
- **AI Core**: Gemini API (with strict JSON Schema enforcement)
- **Transcription**: Faster-Whisper (CPU configuration, fallback enabled)
- **Language Detection**: Custom Unicode parser & Dialect keyword maps
- **Translation**: Bhashini API Client / Regex normalization maps
- **Broker / Task Pool**: Celery + Redis
- **Voice synthesis (TTS)**: gTTS / Bhashini TTS
- **Containerization**: Docker & Docker Compose

---

## Directory Layout

```
krishi/
├── app/
│   ├── api/
│   │   └── routes.py           # SMS, Voice, Location routes
│   ├── core/
│   │   ├── config.py           # Environment parsers
│   │   └── logging.py          # Structured logging definitions
│   ├── db/
│   │   ├── session.py          # Async/Sync connection configuration
│   │   └── base.py             # Schema registration registry
│   ├── models/
│   │   └── models.py           # Postgres storage models
│   ├── schemas/
│   │   └── schemas.py          # Validation rules
│   ├── services/
│   │   ├── ai_gemini.py        # Gemini client wrapper
│   │   ├── location.py         # Cell tower & IP geolocation lookup
│   │   ├── weather.py          # OpenWeatherMap & local telemetry
│   │   ├── whisper_transcription.py
│   │   ├── language_detector.py
│   │   ├── translation.py
│   │   └── tts.py              # gTTS audio generation
│   ├── rag/
│   │   ├── vector_store.py     # RAG queries using FAISS
│   │   └── ingest.py           # Database bootstrapping
│   ├── workers/
│   │   └── celery_worker.py    # Background task worker
│   ├── utils/
│   │   └── helpers.py          # Audio transcoding & upload tools
│   └── main.py                 # App entrypoint
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Local Setup (Without Docker)

### 1. Prerequisites
Ensure you have Python 3.11 installed, along with `ffmpeg` (for transcoding audio queries).

### 2. Configure Environment
Copy `.env.example` into a new `.env` file:
```bash
cp .env.example .env
```
Fill in your `GEMINI_API_KEY`, `OPENWEATHERMAP_API_KEY`, etc. If left empty, the application will run in fully functional **mock fallback mode** using preconfigured static rule libraries.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Seed the FAISS Vector Store
Run the ingestion script to create and populate the local FAISS index:
```bash
python app/rag/ingest.py
```

### 5. Launch Services
Run the FastAPI development server:
```bash
python app/main.py
```

Run Celery background workers in a separate terminal:
```bash
celery -A app.workers.celery_worker.celery_app worker --loglevel=info
```

---

## Containerized Deployment (Docker Compose)

Launch all components (PostgreSQL, Redis, Celery, FastAPI) simultaneously:

```bash
docker-compose up --build
```
The FastAPI documentation will be available at: `http://localhost:8000/docs`.

---

## API Endpoints

### 1. Process SMS Query
- **Endpoint**: `POST /api/v1/sms/query`
- **Request Body**:
```json
{
  "query_text": "murgi anda kam de rahi hai",
  "sender_phone": "+919876543210",
  "location": {
    "latitude": 25.611,
    "longitude": 85.144
  }
}
```
- **Response**: Returns standard structured advisory mapping RAG-grounded insights, dialect adjustments, and weather metrics.

### 2. Process Voice Query
- **Endpoint**: `POST /api/v1/voice/query`
- **Request Type**: `multipart/form-data`
- **Form Fields**:
  - `sender_phone`: `+919876543210`
  - `latitude`: `25.611`
  - `longitude`: `85.144`
  - `audio_file`: (Upload a standard WAV/MP3 file)
- **Response**: Returns transcribed texts, RAG-grounded dialect voice text, and a downloadable URL for the synthesized IVR TTS file:
```json
{
  "query_id": "8a32b2a6-ef12-421b-a5d6-8451f2214432",
  "query_type": "voice",
  "detected_language": "Hindi",
  "detected_dialect": "Bhojpuri",
  "intent": "Poultry",
  "detected_disease_or_need": "Low Egg Production",
  "voice_response": "मुर्गी के ढेर गर्मी और दाना के कमी से अंडा कम हो सकत बा। साफ पानी और संतुलित दाना रोज दीं।",
  "voice_response_audio_url": "/static/audio/7e324ef2-12aa-4ff1-bf31-098845182903.mp3",
  "sms_payload": "कृषि-वाणी परामर्श: मुर्गी पालन - अंडा उत्पादन कम. उपाय: संतुलित दाना. सलाह: गर्मी से बचाएं।"
}
```

---

## RAG Safety Boundaries

- **Zero-Hallucination Policy**: If the RAG lookup fails to retrieve scientific matches from the vector index, the model returns:
  `"किसान भाई, इस समस्या की सटीक वैज्ञानिक जानकारी अभी उपलब्ध नहीं है। कृपया नजदीकी कृषि विज्ञान केंद्र (KVK) या पशु चिकित्सक से सलाह लें।"`
- **Language Simplification**: Complicated chemical labels are converted dynamically into brands like `'कॉन्फिडोर'` or readable local descriptions (e.g. `'सफेद मक्खी मारने वाली दवा'`).

---

## 📞 Missed Call & IVR Callback Endpoints

We implement a complete production-grade telephony workflow supporting both Twilio and Exotel providers:

### 1. Missed Call Webhook
- **Endpoint**: `GET / POST` `/api/v1/webhook/missed-call`
- **Function**: Receives incoming calls, queues an outbound callback Celery task, and rejects the call (returns `<Reject reason="busy"/>` XML) to ensure the user is not charged.

### 2. IVR Greeting
- **Endpoint**: `GET / POST` `/api/v1/ivr/start`
- **Function**: Webhook hit when the outbound call connects. Returns TwiML greeting the farmer in Hindi and prompting a voice recording.

### 3. Audio Recording Webhook
- **Endpoint**: `POST` `/api/v1/ivr/recording`
- **Function**: Receives recorded voice file, downloads it, triggers the core AI RAG pipeline, queues the SMS advisory, and returns a redirect to `/ivr/response`.

### 4. Audio Playback
- **Endpoint**: `GET / POST` `/api/v1/ivr/response`
- **Function**: Serves the synthesized TTS response file URL using the `<Play>` element.

---

## 🌐 ngrok Setup & Telephony Integration

To connect Twilio or Exotel to your local development instance, you must expose port 8000 using ngrok:

### Step 1: Install ngrok
Download and configure ngrok. Then expose port 8000:
```bash
ngrok http 8000
```
This will provide a public forwarding URL (e.g., `https://xxxx-xxxx.ngrok-free.app`).

### Step 2: Configure Environment
Add the forwarding URL to your `.env` file:
```env
BASE_URL=https://xxxx-xxxx.ngrok-free.app
TELEPHONY_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your_actual_sid
TWILIO_AUTH_TOKEN=your_actual_token
TWILIO_PHONE_NUMBER=your_twilio_number
```

### Step 3: Configure Telecom Webhooks
In the Twilio Console (or Exotel dashboard), configure the **Incoming Call webhook** of your virtual pho    ne number to:
```text
https://xxxx-xxxx.ngrok-free.app/api/v1/webhook/missed-call
```

When a farmer dials your number, the call will trigger the webhook, hang up automatically, initiate the outbound callback, record their query, play the generated TTS advisory, and send the SMS payload!

---

## 🧪 Local Verification Tests

You can verify the entire telephony workflow locally using the provided verification script. Make sure the FastAPI app is running:

```bash
# Run server
python app/main.py

# Execute local IVR testing script (in a separate terminal)
python scratch/test_ivr.py
```
The script will simulate the full cycle from webhook trigger to callback, recording download, AI analysis, playback redirect, and SMS dispatch, printing responses to the console.
