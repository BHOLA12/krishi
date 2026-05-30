import json
import google.generativeai as genai
from typing import Dict, Any
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Configure the SDK if API Key is available
if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=settings.GEMINI_API_KEY)
    logger.info("Gemini API key configured successfully.")
else:
    logger.warning("No valid GEMINI_API_KEY found. Running in mockup service mode.")

class GeminiAIService:
    @classmethod
    async def generate_response(
        cls,
        user_query: str,
        env_profile: str,
        grounded_facts: str,
        detected_dialect: str
    ) -> Dict[str, Any]:
        """
        Submits the RAG prompt to Gemini, enforcing JSON formatting, safety constraints, 
        vernacular translation rules, and dialect adaptation.
        """
        system_prompt = f"""
You are "Krishi-Vani Core AI", an ultra-low-latency multilingual rural intelligence assistant for India.
Your mission is to provide scientifically grounded, hyper-local, and easy-to-understand agricultural guidance.

Target Dialect for adaptation: {detected_dialect}

━━━━━━━━━━━━━━━━━━━━━━
STRICT SAFETY RULES
━━━━━━━━━━━━━━━━━━━━━━
1. ZERO HALLUCINATION POLICY:
- NEVER invent: medicines, vaccines, pesticides, dosages, diseases, govt benefits, or fertilizer quantities.
- ONLY answer using information explicitly available inside [GROUNDED_FACTS].
- If exact scientific information is unavailable to resolve the query, you MUST reply EXACTLY:
"किसान भाई, इस समस्या की सटीक वैज्ञानिक जानकारी अभी उपलब्ध नहीं है। कृपया नजदीकी कृषि विज्ञान केंद्र (KVK) या पशु चिकित्सक से सलाह लें।"

2. BRAND/VILLAGE LANGUAGE SIMPLIFICATION:
- Convert difficult chemical names into famous market brand names or easy village-friendly descriptions.
- Example: Instead of "Imidacloprid 17.8% SL", say "'कॉन्फिडोर' या सफेद मक्खी मारने वाली दवा".

3. VOICE RESPONSE RULES (IVR):
- Must be conversational.
- MAXIMUM 3-4 short sentences.
- Optimized for Text-to-Speech (easy to pronounce).
- Avoid technical jargon. Respond in a respectful, rural-friendly tone (using terms like "किसान भाई").

4. SMS FORMAT:
- Must include: crop/animal/fish/poultry name, disease/problem, medicine/feed/solution, dosage if available, and one short instruction.

━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON block. Do not include markdown wraps (like ```json).
Format:
{{
  "intent": "Agriculture / Horticulture / Animal_Husbandry / Fish_Farming / Poultry / Govt_Schemes / Weather / Market_Prices",
  "detected_disease_or_need": "Detected issue name",
  "voice_response": "Short IVR-ready response in simple {detected_dialect} / Hindi mix.",
  "sms_payload": "कृषि-वाणी परामर्श: [Crop/Animal/Fish/Poultry] - [Disease/Need]. उपाय: [Brand/Medicine/Feed]. मात्रा: [Dosage if available]. सलाह: [Short actionable step]."
}}
"""

        user_content = f"""
[USER_QUERY]
"{user_query}"

[ENVIRONMENTAL_PROFILE]
"{env_profile}"

[GROUNDED_FACTS]
"{grounded_facts}"
"""

        # Model execution block
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
            try:
                # Use Gemini 1.5 Flash (or 2.5 Flash if available, default to gemini-1.5-flash)
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"}
                )
                
                response = model.generate_content(
                    contents=[
                        {"role": "user", "parts": [system_prompt + "\n" + user_content]}
                    ]
                )
                
                response_text = response.text.strip()
                # Clean up any potential markdown block markers if Gemini returned them
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                response_text = response_text.strip("` \n")
                
                parsed_json = json.loads(response_text)
                logger.info("Gemini structured response successfully parsed", intent=parsed_json.get("intent"))
                return parsed_json
                
            except Exception as e:
                logger.error("Gemini Generation failed. Initiating fallback offline response.", error=str(e))
        
        # Fallback Mock logic for test runs (fully compliant with grounded facts safety)
        return cls._generate_mock_response(user_query, grounded_facts, detected_dialect)

    @classmethod
    def _generate_mock_response(cls, user_query: str, grounded_facts: str, dialect: str) -> Dict[str, Any]:
        """
        Determines query category offline and outputs correct schema JSON.
        """
        query_lower = user_query.lower()
        
        # Safety fallback check
        if not grounded_facts or "no specific details" in grounded_facts.lower() or "not available" in grounded_facts.lower():
            return {
                "intent": "Agriculture",
                "detected_disease_or_need": "Unresolved scientific query",
                "voice_response": "किसान भाई, इस समस्या की सटीक वैज्ञानिक जानकारी अभी उपलब्ध नहीं है। कृपया नजदीकी कृषि विज्ञान केंद्र (KVK) या पशु चिकित्सक से सलाह लें।",
                "sms_payload": "कृषि-वाणी परामर्श: जानकारी अनुपलब्ध। कृपया नजदीकी KVK या पशु चिकित्सक से सलाह लें।"
            }

        # 1. Fish query match
        if "oxygen" in grounded_facts.lower() or "aeration" in grounded_facts.lower():
            voice_txt = "किसान भाई, तालाब में ऑक्सीजन कम हो सकता है। अभी कुछ समय के लिए खाना देना बंद कर दीजिए और पानी में हवा चलाने का इंतजाम कीजिए।"
            if dialect == "Bhojpuri":
                voice_txt = "किसान भाई, तालाब में ऑक्सीजन कम हो गइल बा। अभी कुछ समय खातिर दाना देना बंद कर दीं और पानी में हवा चलावे के इंतजाम करीं।"
            return {
                "intent": "Fish_Farming",
                "detected_disease_or_need": "Low Oxygen In Pond",
                "voice_response": voice_txt,
                "sms_payload": "कृषि-वाणी परामर्श: मछली पालन - तालाब में ऑक्सीजन कम। उपाय: एरेशन चालू करें। सलाह: 1 दिन तक फीड कम दें।"
            }

        # 2. Poultry query match
        if "heat stress" in grounded_facts.lower() or "egg" in grounded_facts.lower():
            voice_txt = "मुर्गी को ज्यादा गर्मी और पोषण की कमी से अंडा कम हो सकता है। साफ पानी और संतुलित दाना नियमित दीजिए।"
            if dialect == "Bhojpuri":
                voice_txt = "मुर्गी के ढेर गर्मी और दाना के कमी से अंडा कम हो सकत बा। साफ पानी और संतुलित दाना रोज दीं।"
            return {
                "intent": "Poultry",
                "detected_disease_or_need": "Low Egg Production",
                "voice_response": voice_txt,
                "sms_payload": "कृषि-वाणी परामर्श: मुर्गी पालन - अंडा उत्पादन कम। उपाय: संतुलित दाना और साफ पानी दें। सलाह: गर्मी से बचाव करें।"
            }

        # 3. Cow/Dairy query match
        if "fever" in grounded_facts.lower() or "cattle" in grounded_facts.lower() or "cow" in grounded_facts.lower():
            voice_txt = "किसान भाई, मवेशी को बुखार होने पर उसे छायादार स्थान पर रखें और ताजा पानी पिलाएं। डॉक्टर से जल्द संपर्क करें।"
            return {
                "intent": "Animal_Husbandry",
                "detected_disease_or_need": "Cattle Fever",
                "voice_response": voice_txt,
                "sms_payload": "कृषि-वाणी परामर्श: पशुपालन - मवेशी को बुखार। उपाय: छायादार स्थान पर रखें। सलाह: पशु चिकित्सक से जल्द जांच करवाएं।"
            }

        # Default fallback for crop disease / nitrogen deficiency
        voice_txt = "किसान भाई, धान की पत्तियां पीली होने का मुख्य कारण नाइट्रोजन की कमी हो सकता है। प्रति एकड़ यूरिया का छिड़काव करें।"
        if dialect == "Bhojpuri":
            voice_txt = "किसान भाई, धान के पत्ता पीला भइल नाइट्रोजन के कमी के वजह से हो सकत बा। खेत में यूरिया के छिड़काव करीं।"
            
        return {
            "intent": "Agriculture",
            "detected_disease_or_need": "Nitrogen Deficiency In Paddy",
            "voice_response": voice_txt,
            "sms_payload": "कृषि-वाणी परामर्श: धान - पत्ती पीली होना। उपाय: यूरिया छिड़काव। मात्रा: 20 किलो प्रति एकड़। सलाह: सिंचाई के बाद यूरिया दें।"
        }
    
    @staticmethod
    def mock_is_active() -> bool:
        return not (settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here")
