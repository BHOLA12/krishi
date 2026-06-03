import os
from fastapi import FastAPI  , Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import router as api_router
from app.db.session import get_db, sync_engine, Base
import structlog
import redis

# HTML Landing Page Template
LANDING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>कृषि-वाणी (Krishi-Vani) - AI Rural Assistant</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+Devanagari:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: rgba(22, 27, 34, 0.8);
            --primary-gradient: linear-gradient(135deg, #2ea44f 0%, #1f6feb 100%);
            --accent-green: #3fb950;
            --accent-blue: #58a6ff;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --border-color: #30363d;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Outfit', 'Noto Sans Devanagari', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            overflow-x: hidden;
            position: relative;
        }
        /* Background decor elements */
        body::before {
            content: '';
            position: absolute;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle, rgba(46, 164, 79, 0.15) 0%, transparent 70%);
            top: -100px;
            left: -100px;
            z-index: 0;
            pointer-events: none;
        }
        body::after {
            content: '';
            position: absolute;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(31, 111, 235, 0.1) 0%, transparent 70%);
            bottom: -150px;
            right: -150px;
            z-index: 0;
            pointer-events: none;
        }
        .container {
            max-width: 900px;
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 40px;
            backdrop-filter: blur(16px);
            z-index: 10;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            animation: fadeIn 0.8s ease-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        header {
            text-align: center;
            margin-bottom: 40px;
        }
        .logo {
            font-size: 3.5rem;
            font-weight: 800;
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }
        .sub-logo {
            font-size: 1.3rem;
            color: var(--accent-green);
            font-weight: 600;
            margin-bottom: 15px;
            letter-spacing: 1px;
        }
        .description {
            font-size: 1.05rem;
            color: var(--text-muted);
            line-height: 1.6;
            max-width: 700px;
            margin: 0 auto;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .card:hover {
            transform: translateY(-5px);
            border-color: var(--accent-green);
            background: rgba(46, 164, 79, 0.02);
            box-shadow: 0 10px 20px rgba(46, 164, 79, 0.05);
        }
        .card h3 {
            font-size: 1.25rem;
            margin-bottom: 12px;
            color: var(--accent-blue);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card p {
            font-size: 0.95rem;
            color: var(--text-muted);
            line-height: 1.5;
        }
        .action-area {
            text-align: center;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 16px 36px;
            font-size: 1.1rem;
            font-weight: 600;
            color: #ffffff;
            background: var(--primary-gradient);
            border: none;
            border-radius: 12px;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(31, 111, 235, 0.3);
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(31, 111, 235, 0.5);
            opacity: 0.95;
        }
        footer {
            margin-top: 40px;
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-muted);
            border-top: 1px solid var(--border-color);
            padding-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">कृषि-वाणी</div>
            <div class="sub-logo">KRISHI-VANI CORE AI</div>
            <p class="description">
                किसान भाइयों के लिए अति-न्यून विलंभता (Ultra-low latency) बहुभाषी कृषि परामर्श प्रणाली। 
                यह सिस्टम IVR वॉइस कॉल और SMS के माध्यम से देश के सुदूर गांवों तक सीधा वैज्ञानिक परामर्श पहुँचाता है।
            </p>
        </header>

        <div class="grid">
            <div class="card">
                <h3>📞 IVR वॉइस कॉल API</h3>
                <p>किसान भाई फोन पर सीधे सवाल बोल सकते हैं। सिस्टम आवाज़ सुनकर बोली (Bhojpuri/Maithili) पहचानता है और उसी लहज़े में तुरंत बोलकर समाधान बताता है।</p>
            </div>
            <div class="card">
                <h3>💬 SMS संदेश सेवा API</h3>
                <p>कम नेटवर्क वाले क्षेत्रों में साधारण फीचर फोन के माध्यम से SMS द्वारा कम शब्दों में सटीक ब्रांड नाम और यूरिया/दवाइयों की मात्रा का सुझाव देता है।</p>
            </div>
            <div class="card">
                <h3>🌾 RAG वैज्ञानिक तथ्य</h3>
                <p>यह प्रणाली पूरी तरह से ICAR और कृषि विज्ञान केंद्र (KVK) के डेटा से सुरक्षित है। बिना पुष्टि किए कोई गलत दवा या सलाह (hallucination) नहीं दी जाती।</p>
            </div>
        </div>

        <div class="action-area">
            <a href="/docs" class="btn">🚀 Open Swagger API Documentation (APIs टेस्ट करें)</a>
        </div>

        <footer>
            कृषि-वाणी AI प्रोजेक्ट • भारत के ग्रामीण क्षेत्रों के लिए डिज़ाइन किया गया • CPU-Optimized Server v1.0.0
        </footer>
    </div>
</body>
</html>
"""

# Initialize Structured Logging
setup_logging()
logger = structlog.get_logger()

# =============================================================================
# ❌ PURANA CODE — APP BOOT NAHI HOTI THI (ISLIYE BADLA)
# =============================================================================
# app = FastAPI(
#     title=settings.PROJECT_NAME,
#     description="...",
#     version="1.0.0",
#     docs_url="/docs",      # ← Production mein bhi /docs khula tha
#     redoc_url="/redoc"     # ← Koi bhi API ka structure dekh sakta tha
# )
#
# ⚠️  KYU BADLA (WHY WE CHANGED):
#     docs_url="/docs" production mein bhi active tha. Matlab koi bhi
#     https://yoursite.com/docs khol ke dekh sakta tha ki kaun kaun se
#     endpoints hain — including woh unauthenticated /sms/send endpoint
#     jo Twilio billing ke liye khula tha.
#     Ab: Development mein /docs milega, Production mein nahi.
# =============================================================================

# ✅ NAYA CODE — Swagger sirf development mein dikhega
_docs_url = "/docs" if settings.ENV == "development" else None
_redoc_url = "/redoc" if settings.ENV == "development" else None

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Krishi-Vani: High-Performance Multilingual Audio/SMS Engine for Rural India",
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url
)

# =============================================================================
# ❌ PURANA CORS CODE — APP CRASH KARTI THI (ISLIYE BADLA)
# =============================================================================
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],       # ← Wildcard — sab allow
#     allow_credentials=True,    # ← Credentials bhi allow
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# ⚠️  KYU BADLA (WHY WE CHANGED):
#     W3C CORS specification ek rule define karti hai:
#       allow_origins=["*"]  +  allow_credentials=True  =  ILLEGAL COMBINATION
#
#     FastAPI/Starlette version 0.20+ is rule ko enforce karta hai.
#     Jaise hi app start hoti, Python yeh error throw karta:
#       RuntimeError: allow_origins cannot be ['*'] when allow_credentials is True
#     App completely band ho jaati — koi bhi request process nahi hoti.
#
#     Fix: ["*"] ki jagah specific URLs diye jo actually allowed hain.
#     Development mein localhost bhi add kiya gaya hai debugging ke liye.
# =============================================================================

# ✅ NAYA CODE — Specific origins, no wildcard
_cors_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    settings.BASE_URL,
] if settings.ENV == "development" else [
    settings.BASE_URL,
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Internal-API-Key"],
)

# Ensure static directories exist
STATIC_DIR = os.path.join(settings.BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "audio"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "uploads"), exist_ok=True)

# Mount Static paths to expose synthesized voice files and audio uploads
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
async def on_startup():
    logger.info("Initializing system dependencies...")
    
    # Bootstrap DB schema automatically for local development/MVP execution
    try:
        logger.info("Running database schema synchronization...")
        # Executing database creation on sync engine (blocking startup event)
        Base.metadata.create_all(bind=sync_engine)
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error("Failed to run database schema synchronization", error=str(e))
        
    # Verify Redis connectivity
    try:
        logger.info("Validating Redis connection status...")
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, socket_timeout=2)
        r.ping()
        logger.info("Redis server connection successful.")
    except Exception as e:
        logger.warning("Redis server is offline. Celery workers will operate in queued standby mode.", error=str(e))

    logger.info("System startup routine complete. Krishi-Vani ready.")

@app.get("/", response_class=HTMLResponse)
async def root_welcome():
    """
    Returns the user-friendly landing page welcoming visitors to Krishi-Vani.
    """
    return LANDING_PAGE_HTML

@app.get("/health")
async def system_health_audit(db: AsyncSession = Depends(get_db)):
    """
    Standard operations health check. Audits database connection and Redis status.
    """
    health_status = {
        "status": "healthy",
        "database": "offline",
        "redis": "offline",
        "gemini_service": "mock" if (not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here") else "active"
    }

    # 1. DB Ping
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "online"
    except Exception as e:
        logger.error("Health check DB query failure", error=str(e))
        health_status["status"] = "degraded"

    # 2. Redis Ping
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, socket_timeout=1)
        r.ping()
        health_status["redis"] = "online"
    except Exception as e:
        logger.error("Health check Redis query failure", error=str(e))
        health_status["redis"] = "offline"

    if health_status["database"] == "offline":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status

# Mount core API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
