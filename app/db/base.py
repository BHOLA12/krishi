# Import all the models, so that Base has them before being
# imported by Alembic or migration scripts.
from app.db.session import Base  # noqa
from app.models.models import FarmerQuery, LocationAudit, SystemLog, AgriculturalAgent, AgentBooking  # noqa
