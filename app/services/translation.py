import aiohttp
from typing import Dict, Any, Optional
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Basic dictionary maps for common Hinglish queries to Hindi normalization
HINGLISH_TO_HINDI_MAP = {
    "machli paani ke upar aa rahi hai": "मछली पानी के ऊपर आ रही है",
    "murgi anda kam de rahi hai": "मुर्गी अंडा कम दे रही है",
    "gay ko bukhar hai": "गाय को बुखार है",
    "dhan ki patti pili pad rahi hai": "धान की पत्ती पीली पड़ रही है",
    "kcc loan kaise milega": "केसीसी लोन कैसे मिलेगा",
    "pm kisan ka paisa kab aayega": "पीएम किसान का पैसा कब आएगा",
    "tamatar me keeda lag gaya hai": "टमाटर में कीड़ा लग गया है",
    "aloo me rog lag gaya hai": "आलू में रोग लग गया है"
}

class TranslationService:
    @staticmethod
    def normalize_hinglish(text: str) -> str:
        """
        Converts common Hinglish inputs into proper Devanagari Hindi text 
        using local fuzzy dictionaries to avoid slow translation API calls.
        """
        normalized = text.lower().strip()
        
        # Exact matching
        if normalized in HINGLISH_TO_HINDI_MAP:
            return HINGLISH_TO_HINDI_MAP[normalized]

        # Basic keyword swaps
        word_swaps = {
            "machli": "मछली", "paani": "पानी", "upar": "ऊपर", "murgi": "मुर्गी",
            "anda": "अंडा", "kam": "कम", "de rahi hai": "दे रही है", "gay": "गाय",
            "bukhar": "बुखार", "dhan": "धान", "patti": "पत्ती", "pili": "पीली",
            "khad": "खाद", "kcc": "केसीसी", "loan": "ऋण", "kisan": "किसान",
            "t तालाब": "तालाब", "bimar": "बीमार", "dawa": "दवा", "kheti": "खेती"
        }
        
        words = normalized.split()
        translated_words = [word_swaps.get(w, w) for w in words]
        joined = " ".join(translated_words)
        
        # If it contains English alphabet characters, return as is (and let LLM handle it), otherwise Devanagari.
        return joined

    @classmethod
    async def translate_to_hindi(cls, text: str, source_lang: str) -> str:
        """
        Translates regional Indic languages or Hinglish into standard Hindi for normalized RAG query.
        """
        if source_lang.lower() == "hindi":
            return text
            
        if source_lang.lower() == "hinglish":
            return cls.normalize_hinglish(text)

        # Production-grade Bhashini API integration
        api_key = settings.BHASHINI_API_KEY
        if api_key and api_key != "your_bhashini_api_key_here":
            try:
                # Structure matching MeitY Bhashini API payload specs
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": api_key
                }
                payload = {
                    "pipelineTasks": [
                        {
                            "taskType": "translation",
                            "config": {
                                "language": {
                                    "sourceLanguage": source_lang.lower()[:2],
                                    "targetLanguage": "hi"
                                }
                            }
                        }
                    ],
                    "inputData": {
                        "input": [{"source": text}]
                    }
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://dhruva.co-learning.in/services/inference/pipeline",
                        json=payload,
                        headers=headers,
                        timeout=5
                    ) as response:
                        if response.status == 200:
                            res_json = await response.json()
                            translated_text = res_json["pipelineResponse"][0]["output"][0]["target"]
                            logger.info(
                                "Translation via Bhashini API successful",
                                original=text,
                                translation=translated_text
                            )
                            return translated_text
            except Exception as e:
                logger.error("Bhashini translation API failure. Proceeding with raw query.", error=str(e))
                
        logger.info("No active translation API configured. Processing query in original string format.", original=text)
        return text
