import os
import sys
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

# Setup PYTHONPATH so this can be executed as a standalone script
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings
from app.rag.vector_store import get_embeddings, OFFLINE_FACTS_DB
import structlog

logger = structlog.get_logger()

# Large set of scientific verified ICAR / KVK facts for agricultural domains
SEED_DOCUMENTS = [
    # Agriculture
    "धान की फसल में नाइट्रोजन की कमी के कारण पत्तियां पीली पड़ जाती हैं। प्रति एकड़ 20 से 25 किलोग्राम यूरिया का छिड़काव सिंचाई के बाद करें।",
    "गेहूं में रस्ट या गेरुई रोग (Rust disease) लगने पर पत्तियों पर पीले या भूरे रंग के धब्बे दिखाई देते हैं। इसकी रोकथाम हेतु प्रोपिकोनाजोल 25% ईसी (Propiconazole 25% EC) की 200 मिलीलीटर मात्रा को 200 लीटर पानी में मिलाकर प्रति एकड़ छिड़काव करें। बाजार में इसे 'टिल्ट' (Tilt) नाम से जाना जाता है।",
    "गन्ने की फसल में तना छेदक (Stem Borer) कीट के नियंत्रण के लिए ट्राइकोकार्ड (Trichocard) का प्रयोग करें अथवा फेनप्रोपैथ्रिन (Fenpropathrin) दवा का छिड़काव 2 मिलीलीटर प्रति लीटर पानी की दर से करें।",
    "मक्का की फसल में फॉल आर्मीवर्म (Fall Armyworm) के नियंत्रण के लिए इमामेक्टिन बेंजोएट 5% एसजी (Emamectin Benzoate 5% SG) जिसे 'प्रोक्लेम' (Proclaim) कहा जाता है, उसकी 80 ग्राम मात्रा को 200 लीटर पानी में घोलकर प्रति एकड़ छिड़काव करें।",

    # Dairy / Animal Husbandry
    "गाय या भैंस को बुखार (Fever) होने पर पशु सुस्त हो जाता है, जुगाली करना बंद कर देता है और शरीर का तापमान 104 से 106 डिग्री फ़ारेनहाइट तक पहुंच जाता है। ऐसे में पशु को तुरंत धूप से बचाकर हवादार छांव में रखें और ताजी हवा और ठंडा पानी दें। पशु चिकित्सक की देखरेख में मेलोक्सिकैम (Meloxicam) का इंजेक्शन या दर्द निवारक दवा दें।",
    "पशुओं में खुरपका-मुंहपका (FMD) रोग की रोकथाम के लिए वर्ष में दो बार (सितंबर और मार्च) टीकाकरण अवश्य करवाएं। संक्रमित पशुओं के खुरों को लाल दवा (पोटैशियम परमैंगनेट) के घोल से साफ करें।",
    "दूध उत्पादन बढ़ाने के लिए दुधारू पशुओं को रोजाना 30 से 40 ग्राम खनिज मिश्रण (Mineral Mixture) और संतुलित हरा चारा व सूखा भूसा मिलाकर दें। साफ पानी चौबीस घंटे उपलब्ध रहना चाहिए।",

    # Fish Farming (Aquaculture)
    "तालाब में घुलित ऑक्सीजन (Dissolved Oxygen) की कमी मुख्यतः भोर या तड़के (4 से 6 बजे सुबह) होती है। इससे मछलियां सतह पर आकर मुंह चलाती हैं। इसका समाधान करने के लिए तुरंत तालाब में नया पानी भरें, एरिएटर (Aerator) चालू करें और कम से कम एक दिन के लिए कृत्रिम चारा (फीड) देना बिल्कुल बंद कर दें।",
    "मछली पालन में तालाब के पानी का पीएच (pH) स्तर हमेशा 6.5 से 8.5 के बीच होना चाहिए। यदि पीएच 6.5 से कम (अम्लीय) हो तो 100 किलोग्राम चूना प्रति एकड़ की दर से तालाब के पानी में डालें।",
    "रोहू और कतला मछली पालन में फंगल इन्फेक्शन या लाल धब्बा रोग (Epizootic Ulcerative Syndrome - EUS) होने पर पानी में 5 किलोग्राम पोटैशियम परमैंगनेट प्रति एकड़ की दर से छिड़काव करें।",

    # Poultry
    "गर्मियों में मुर्गियों में लू या हीट स्ट्रेस (Heat Stress) होने से वे मुंह खोलकर सांस लेती हैं और अंडा उत्पादन गिर जाता है। इससे बचाव के लिए शेड की छतों पर चूना लगाएं, कूलर का उपयोग करें और पीने के पानी में ग्लूकोज व इलेक्ट्रोलाइट (ओआरएस) अवश्य मिलाएं।",
    "मुर्गियों में रानीखेत रोग (Ranikhet / Newcastle Disease) अत्यधिक संक्रामक है। इससे बचाव के लिए पहले सप्ताह में ही एफ-1 (F1) वैक्सीन का टीका और 21वें दिन लासोटा (LaSota) वैक्सीन का टीका अवश्य लगवाएं। इस बीमारी का कोई इलाज नहीं है, केवल टीकाकरण ही एकमात्र उपाय है।",

    # Government Schemes
    "प्रधानमंत्री किसान सम्मान निधि (PM-Kisan) योजना के अंतर्गत सभी पात्र किसान परिवारों को प्रति वर्ष 6,000 रुपये की वित्तीय सहायता दी जाती है, जो 2,000 रुपये की तीन किस्तों में सीधे उनके बैंक खातों में ट्रांसफर की जाती है। पंजीकरण के लिए आधार कार्ड और भूलेख रिकॉर्ड आवश्यक हैं।",
    "किसान क्रेडिट कार्ड (KCC) योजना के तहत किसानों को फसलों के उत्पादन के लिए 3 लाख रुपये तक का अल्पकालिक ऋण दिया जाता है। समय पर भुगतान करने वाले किसानों को केवल 4% वार्षिक ब्याज दर देनी होती है। आवेदन नजदीकी बैंक शाखा में किया जा सकता है।"
]

def run_ingestion():
    """
    Reads the predefined list of seed documents, instantiates the embedding model,
    builds the FAISS vector index, and stores it on disk.
    """
    logger.info("Starting database document ingestion pipeline...")
    
    embeddings = get_embeddings()
    if embeddings is None:
        logger.error("Embedding model unavailable. Ingestion terminated.")
        return False
        
    # Combine Seed documents and Offline fact snippets
    all_facts = SEED_DOCUMENTS.copy()
    for item in OFFLINE_FACTS_DB:
        if item["text"] not in all_facts:
            all_facts.append(item["text"])

    docs = [Document(page_content=fact) for fact in all_facts]
    
    logger.info("Encoding documents and building index", count=len(docs))
    try:
        vector_store = FAISS.from_documents(docs, embeddings)
        
        index_dir = settings.FAISS_INDEX_PATH
        os.makedirs(index_dir, exist_ok=True)
        
        logger.info("Saving index files locally", directory=index_dir)
        vector_store.save_local(index_dir)
        logger.info("RAG data ingestion completed successfully.")
        return True
    except Exception as e:
        logger.error("Ingestion process execution failed", error=str(e))
        return False

if __name__ == "__main__":
    success = run_ingestion()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
