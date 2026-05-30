import re
from typing import Dict, Tuple
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Dialect keyword indicators to robustly map vernacular variants
DIALECT_MARKERS = {
    "Bhojpuri": [
        r"बा\b", r"रउआ", r"का हाल", r"का समाचार", r"गोरू", r"बछरू", r"मछरी", r"तलाब", r"खादवा", r"केकरा"
    ],
    "Maithili": [
        r"अछि\b", r"अहाँ", r"कथी", r"कनियाँ", r"खाइत", r"करैत", r"धानक", r"गायब", r"तरकारी"
    ],
    "Magahi": [
        r"हथिन\b", r"हमर", r"काची", r"तोहर", r"गेला", r"खैला", r"जाही"
    ],
    "Awadhi": [
        r"रहा\b", r"का भवा", r"मोर", r"तोरे", r"गयूं", r"बबा", r"नीक"
    ],
    "Hinglish": [
        r"\bfertilizer\b", r"\bpest\b", r"\bdisease\b", r"\bweather\b", r"\bscheme\b", r"\bloan\b",
        r"\burea\b", r"\bpotash\b", r"\bmedicines\b", r"\bfeed\b", r"\bdoctor\b", r"\btemp\b"
    ]
}

# FastText language lookup mappings
LANG_ISO_MAP = {
    "__label__hin": "Hindi",
    "__label__ben": "Bengali",
    "__label__mar": "Marathi",
    "__label__tam": "Tamil",
    "__label__tel": "Telugu",
    "__label__pan": "Punjabi",
    "__label__guj": "Gujarati",
    "__label__eng": "English"
}

class LanguageDetectorService:
    @staticmethod
    def detect_dialect(text: str) -> str:
        """
        Scans normalized query text to spot vernacular keywords matching 
        Bhojpuri, Maithili, Magahi, Awadhi or Hinglish profiles.
        """
        normalized_text = text.lower()
        
        # Scrape markers
        for dialect, markers in DIALECT_MARKERS.items():
            for marker in markers:
                if re.search(marker, normalized_text):
                    logger.info("Dialect matched by keyword marker", dialect=dialect, marker=marker)
                    return dialect
                    
        return "Hindi"

    @classmethod
    async def detect_language_and_dialect(cls, text: str) -> Tuple[str, str]:
        """
        Uses rule-based heuristics and fastText models (if loaded) to identify
        the main language and any specific rural dialect variant.
        """
        if not text or not text.strip():
            return "Hindi", "Hindi"

        detected_lang = "Hindi"  # Default
        detected_dialect = "Hindi"

        # 1. Look for English/Hinglish characters
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(text)
        
        if total_chars > 0 and (english_chars / total_chars) > 0.4:
            detected_lang = "Hinglish"
            detected_dialect = "Hinglish"
            logger.info("Language classified as Hinglish based on alphabet ratios")
            return detected_lang, detected_dialect

        # 2. Check for regional Indic keywords (Tamil, Telugu, Bengali)
        # Using basic unicode block checks
        # Tamil range: 0B80 - 0BFF
        # Telugu range: 0C00 - 0C7F
        # Bengali range: 0980 - 09FF
        tamil_chars = len(re.findall(r'[\u0b80-\u0bff]', text))
        telugu_chars = len(re.findall(r'[\u0c00-\u0c7f]', text))
        bengali_chars = len(re.findall(r'[\u0980-\u09ff]', text))
        marathi_devanagari = len(re.findall(r'[\u0900-\u097f]', text))

        if tamil_chars > 2:
            detected_lang = "Tamil"
            detected_dialect = "Tamil"
        elif telugu_chars > 2:
            detected_lang = "Telugu"
            detected_dialect = "Telugu"
        elif bengali_chars > 2:
            detected_lang = "Bengali"
            detected_dialect = "Bengali"
        else:
            # Analyze dialect markers on top of Devanagari text
            detected_dialect = cls.detect_dialect(text)
            detected_lang = "Hindi"

        logger.info(
            "Language and dialect classification final",
            detected_language=detected_lang,
            detected_dialect=detected_dialect,
            original_query=text
        )

        return detected_lang, detected_dialect
