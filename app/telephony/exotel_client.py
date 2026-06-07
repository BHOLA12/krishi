import aiohttp
import asyncio
from app.core.config import settings
import structlog

logger = structlog.get_logger()

class ExotelClient:
    def __init__(self):
        self.api_key = settings.EXOTEL_API_KEY
        self.api_token = settings.EXOTEL_API_TOKEN
        self.subdomain = settings.EXOTEL_SUBDOMAIN
        self.virtual_number = settings.EXOTEL_VIRTUAL_NUMBER
        self.is_configured = (
            self.api_key and self.api_key != "your_exotel_api_key_here" and
            self.api_token and self.api_token != "your_exotel_api_token_here"  # nosec B105
        )
        if self.is_configured:
            logger.info("Exotel Client initialized successfully.")
        else:
            logger.warning("Exotel is not configured. Running in Mock Telephony mode.")

    async def make_outbound_call(self, to_number: str, callback_url: str) -> str:
        """
        Triggers an outbound call using Exotel's Call Connect API.
        If Exotel is not configured, it simulates a successful call initiation.
        """
        if not self.is_configured:
            logger.info("[MOCK EXOTEL TELEPHONY] Initiating outbound call", to=to_number, callback_url=callback_url)
            return f"mock-exotel-call-sid-{to_number}"

        # Standard Exotel Call Connect Endpoint
        url = f"https://api.exotel.com/v1/Accounts/{self.api_key}/Calls/connect.json"
        
        # Form-urlencoded data parameters for Exotel
        # From = The farmer's number (the number to call first)
        # To = The virtual number or flow ID (where to connect)
        # CallerId = The virtual number (outbound caller ID)
        # Url = Webhook to get IVR flow config XML
        payload = {
            "From": to_number,
            "To": self.virtual_number,
            "CallerId": self.virtual_number,
            "Url": callback_url,
            "CallType": "transo"
        }
        
        auth = aiohttp.BasicAuth(self.api_key, self.api_token)
        try:
            logger.info("Initiating Exotel outbound call", to=to_number, callback_url=callback_url)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, auth=auth) as response:
                    res_json = await response.json()
                    if response.status in [200, 201]:
                        call_sid = res_json.get("Call", {}).get("Sid")
                        logger.info("Exotel outbound call initiated successfully", call_sid=call_sid)
                        return call_sid
                    else:
                        logger.error("Exotel outbound call failed", status=response.status, response=res_json)
                        return f"failed-exotel-call-sid-{to_number}"
        except Exception as e:
            logger.error("Exotel outbound call request crashed", to=to_number, error=str(e))
            return f"failed-exotel-call-sid-{to_number}"

    async def send_sms(self, to_number: str, message_body: str) -> str:
        """
        Sends an SMS using Exotel's SMS API.
        If Exotel is not configured, it simulates a successful SMS send.
        """
        if not self.is_configured:
            logger.info("[MOCK EXOTEL TELEPHONY] Sending SMS", to=to_number, body=message_body)
            return f"mock-exotel-sms-sid-{to_number}"

        # Standard Exotel SMS Endpoint
        url = f"https://api.exotel.com/v1/Accounts/{self.api_key}/Sms/send.json"
        payload = {
            "From": self.virtual_number,
            "To": to_number,
            "Body": message_body
        }
        
        auth = aiohttp.BasicAuth(self.api_key, self.api_token)
        try:
            logger.info("Sending Exotel SMS", to=to_number)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, auth=auth) as response:
                    res_json = await response.json()
                    if response.status in [200, 201]:
                        sms_sid = res_json.get("SMSMessage", {}).get("Sid")
                        logger.info("Exotel SMS sent successfully", sms_sid=sms_sid)
                        return sms_sid
                    else:
                        logger.error("Exotel SMS failed", status=response.status, response=res_json)
                        return f"failed-exotel-sms-sid-{to_number}"
        except Exception as e:
            logger.error("Exotel SMS request crashed", to=to_number, error=str(e))
            return f"failed-exotel-sms-sid-{to_number}"
