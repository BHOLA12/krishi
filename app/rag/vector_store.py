import os
from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Global variables to cache embeddings and vector store in memory
_embeddings = None
_vector_store = None

# Offline hardcoded agricultural facts database for instant keyword fallback
OFFLINE_FACTS_DB = [
    {
        "keywords": ["machli", "मछली", "oxygen", "ऑक्सीजन", "तालाब", "pond"],
        "text": "तालाब में घुलित ऑक्सीजन (Dissolved Oxygen) की कमी होने पर मछलियां पानी की सतह पर आकर हांफने लगती हैं। ऐसे समय में तालाब में नया पानी डालें, एरिएटर (हवा चलाने का यंत्र) चलाएं और मछलियों को पूरक आहार (दाना) देना तुरंत रोक दें।"
    },
    {
        "keywords": ["murgi", "मुर्गी", "अंडा", "egg", "गर्मी", "heat"],
        "text": "अत्यधिक गर्मी (Heat Stress) और पोषण संबंधी कमियों के कारण मुर्गियों में अंडा उत्पादन कम हो जाता है। मुर्गियों को छायादार ठंडे स्थानों में रखें, पीने के पानी में इलेक्ट्रोलाइट्स मिलाएं और प्रोटीन युक्त संतुलित दाना प्रदान करें।"
    },
    {
        "keywords": ["gay", "गाय", "भैंस", "fever", "बुखार", "animal", "cattle"],
        "text": "पशुओं में बुखार (Fever) होने पर शारीरिक तापमान बढ़ जाता है और वे चारा खाना बंद कर देते हैं। मवेशियों को तुरंत छायादार और हवादार स्थान पर रखें, ताजा साफ पानी पिलाएं और बिना देरी किए नजदीकी सरकारी पशु चिकित्सक से संपर्क करें।"
    },
    {
        "keywords": ["dhan", "धान", "paddy", "pili", "पीली", "pila", "pattiyan", "leaf"],
        "text": "धान की फसल में पत्तियों का पीला पड़ना आमतौर पर नाइट्रोजन पोषक तत्व की कमी के कारण होता है। प्रति एकड़ खेत में सिंचाई के बाद 20 से 25 किलोग्राम यूरिया का छिड़काव करने से पत्तियां पुनः हरी हो जाती हैं।"
    },
    {
        "keywords": ["kcc", "loan", "ऋण", "लोन", "kisan credit card", "केसीसी"],
        "text": "किसान क्रेडिट कार्ड (KCC) योजना के अंतर्गत किसानों को 3 लाख रुपये तक का कृषि ऋण 4% की रियायती ब्याज दर पर मिलता है। आवेदन के लिए आधार कार्ड, भूमि के मालिकाना हक के दस्तावेज (खतौनी) और बैंक पासबुक की आवश्यकता होती है।"
    },
    {
        "keywords": ["pm kisan", "पीएम किसान", "kisan samman nidhi", "6000", "रुपया"],
        "text": "प्रधानमंत्री किसान सम्मान निधि (PM-Kisan) योजना के अंतर्गत पात्र सीमांत किसानों को प्रति वर्ष 6000 रुपये की वित्तीय सहायता तीन समान किस्तों (2000 रुपये प्रत्येक) में सीधे उनके बैंक खातों में ट्रांसफर की जाती है।"
    }
]

def get_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    try:
        logger.info("Initializing HuggingFace Sentence Transformers (all-MiniLM-L6-v2) on CPU...")
        # Lightweight CPU embedding model (around 120MB)
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        logger.info("Embedding model initialized successfully.")
    except Exception as e:
        logger.error("Failed to load sentence-transformers model. RAG falls back to keyword matching.", error=str(e))
        _embeddings = None
    return _embeddings

def load_vector_store():
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    embeddings = get_embeddings()
    if embeddings is None:
        return None

    index_dir = settings.FAISS_INDEX_PATH
    if os.path.exists(os.path.join(index_dir, "index.faiss")):
        try:
            logger.info("Loading existing FAISS Vector Index...", path=index_dir)
            _vector_store = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
            logger.info("FAISS Vector Index loaded successfully.")
        except Exception as e:
            logger.error("Error loading FAISS index from disk", error=str(e))
            _vector_store = None
    else:
        logger.warning("FAISS Vector Index files not found. Creating a temporary fallback index.")
        # Create a basic temporary FAISS index from our offline facts db to avoid crash
        try:
            docs = [Document(page_content=item["text"]) for item in OFFLINE_FACTS_DB]
            _vector_store = FAISS.from_documents(docs, embeddings)
            logger.info("Temporary FAISS index generated.")
        except Exception as e:
            logger.error("Failed to create temporary FAISS index", error=str(e))
            _vector_store = None

    return _vector_store

class RAGRetrievalService:
    @staticmethod
    def _keyword_search(query: str) -> str:
        """
        Fallback keyword match algorithm when vector stores cannot be loaded.
        """
        logger.info("Executing local keyword matcher fallback...")
        query_lower = query.lower()
        matched_texts = []
        
        for item in OFFLINE_FACTS_DB:
            for kw in item["keywords"]:
                if kw in query_lower:
                    matched_texts.append(item["text"])
                    break
                    
        if matched_texts:
            return "\n\n".join(matched_texts)
            
        return "सटीक जानकारी उपलब्ध नहीं है।"

    @classmethod
    async def retrieve_facts(cls, query: str, top_k: int = 2) -> str:
        """
        Retrieves the most semantically relevant facts from FAISS vector store.
        Falls back to local keyword searching if FAISS/Transformers are disabled.
        """
        vector_store = load_vector_store()
        
        if vector_store is None:
            return cls._keyword_search(query)

        try:
            logger.info("Searching FAISS vector database", query=query, top_k=top_k)
            # Run similarity search
            docs = vector_store.similarity_search(query, k=top_k)
            retrieved_content = "\n\n".join([doc.page_content for doc in docs])
            logger.info("Semantic retrieval successful", matched_count=len(docs))
            
            if not retrieved_content.strip():
                return cls._keyword_search(query)
                
            return retrieved_content
            
        except Exception as e:
            logger.error("FAISS similarity search crashed, falling back to keyword search", error=str(e))
            return cls._keyword_search(query)
