import asyncio
from app.core.config import settings
from app.telephony.twilio_client import TwilioClient
from app.telephony.exotel_client import ExotelClient
import structlog

logger = structlog.get_logger()

class TelephonyService:
    _twilio_client = None
    _exotel_client = None

    @classmethod
    def get_provider(cls):
        provider = settings.TELEPHONY_PROVIDER.lower()
        if provider == "twilio":
            if cls._twilio_client is None:
                cls._twilio_client = TwilioClient()
            return cls._twilio_client
        elif provider == "exotel":
            if cls._exotel_client is None:
                cls._exotel_client = ExotelClient()
            return cls._exotel_client
        else:
            # Default fallback to Twilio
            if cls._twilio_client is None:
                cls._twilio_client = TwilioClient()
            return cls._twilio_client

    @classmethod
    async def make_call_async(cls, to_number: str, callback_url: str) -> str:
        """
        Asynchronously initiates an outbound call to the farmer.
        """
        provider = cls.get_provider()
        if isinstance(provider, ExotelClient):
            return await provider.make_outbound_call(to_number, callback_url)
        else:
            # Run the synchronous Twilio client call in an executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                provider.make_outbound_call,
                to_number,
                callback_url
            )

    @classmethod
    async def send_sms_async(cls, to_number: str, message_body: str) -> str:
        """
        Asynchronously sends an SMS containing advisory details.
        """
        provider = cls.get_provider()
        if isinstance(provider, ExotelClient):
            return await provider.send_sms(to_number, message_body)
        else:
            # Run the synchronous Twilio client call in an executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                provider.send_sms,
                to_number,
                message_body
            )

    @classmethod
    def make_call_sync(cls, to_number: str, callback_url: str) -> str:
        """
        Synchronously initiates an outbound call (ideal for Celery task context).
        """
        provider = cls.get_provider()
        if isinstance(provider, TwilioClient):
            return provider.make_outbound_call(to_number, callback_url)
        else:
            # For async ExotelClient in a sync Celery context, run in a new/existing event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # Schedule task if loop is running
                future = asyncio.run_coroutine_threadsafe(
                    provider.make_outbound_call(to_number, callback_url), loop
                )
                return future.result()
            else:
                return loop.run_until_complete(provider.make_outbound_call(to_number, callback_url))

    @classmethod
    def send_sms_sync(cls, to_number: str, message_body: str) -> str:
        """
        Synchronously sends an SMS (ideal for Celery task context).
        """
        provider = cls.get_provider()
        if isinstance(provider, TwilioClient):
            return provider.send_sms(to_number, message_body)
        else:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    provider.send_sms(to_number, message_body), loop
                )
                return future.result()
            else:
                return loop.run_until_complete(provider.send_sms(to_number, message_body))

    @classmethod
    async def send_whatsapp_async(cls, to_number: str, message_body: str) -> str:
        """
        Asynchronously sends a WhatsApp message containing advisory details.
        """
        provider = cls.get_provider()
        if isinstance(provider, TwilioClient):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                provider.send_whatsapp_message,
                to_number,
                message_body
            )
        else:
            logger.warning("WhatsApp is not supported for the selected provider. Running mock.")
            return f"mock-whatsapp-sid-{to_number}"

