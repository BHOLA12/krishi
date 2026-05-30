from twilio.rest import Client
from app.core.config import settings
import structlog

logger = structlog.get_logger()

class TwilioClient:
    def __init__(self):
        self.sid = settings.TWILIO_ACCOUNT_SID
        self.token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.is_configured = (
            self.sid and self.sid != "your_twilio_account_sid_here" and
            self.token and self.token != "your_twilio_auth_token_here"
        )
        if self.is_configured:
            try:
                self.client = Client(self.sid, self.token)
                logger.info("Twilio API Client initialized successfully.")
            except Exception as e:
                logger.error("Failed to initialize Twilio REST Client", error=str(e))
                self.client = None
                self.is_configured = False
        else:
            self.client = None
            logger.warning("Twilio is not configured. Running in Mock Telephony mode.")

    def make_outbound_call(self, to_number: str, callback_url: str) -> str:
        """
        Triggers an outbound call using Twilio.
        If Twilio is not configured, it simulates a successful call initiation.
        """
        if self.is_configured and self.client:
            try:
                logger.info("Initiating Twilio outbound call", to=to_number, callback_url=callback_url)
                call = self.client.calls.create(
                    to=to_number,
                    from_=self.from_number,
                    url=callback_url
                )
                logger.info("Twilio outbound call initiated successfully", call_sid=call.sid)
                return call.sid
            except Exception as e:
                logger.error("Twilio outbound call failed", to=to_number, error=str(e))
                return f"failed-twilio-call-sid-{to_number}"
        else:
            logger.info("[MOCK TWILIO TELEPHONY] Initiating outbound call", to=to_number, callback_url=callback_url)
            return f"mock-twilio-call-sid-{to_number}"

    def send_sms(self, to_number: str, message_body: str) -> str:
        """
        Sends an SMS using Twilio.
        If Twilio is not configured, it simulates a successful SMS send.
        """
        if self.is_configured and self.client:
            try:
                logger.info("Sending Twilio SMS", to=to_number)
                message = self.client.messages.create(
                    to=to_number,
                    from_=self.from_number,
                    body=message_body
                )
                logger.info("Twilio SMS sent successfully", message_sid=message.sid)
                return message.sid
            except Exception as e:
                logger.error("Twilio SMS sending failed", to=to_number, error=str(e))
                return f"failed-twilio-sms-sid-{to_number}"
        else:
            logger.info("[MOCK TWILIO TELEPHONY] Sending SMS", to=to_number, body=message_body)
            return f"mock-twilio-sms-sid-{to_number}"
