"""Investigation models - GDPR-compliant case management."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ObservableType(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"


class LegalBasis(str, Enum):
    LEGITIMATE_INTEREST = "legitimate_interest"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTEREST = "vital_interest"


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class InvestigationCreate(BaseModel):
    """Request body for creating a new investigation.

    Requires legal basis and justification fields to enforce
    GDPR Article 6(1)(f) and DPIA documentation requirements.
    """

    query: str = Field(..., description="The target data point (username, email, domain, etc.)")
    observable_type: ObservableType
    legal_basis: LegalBasis = Field(..., description="GDPR legal basis for this investigation")
    purpose: str = Field(..., min_length=2, description="Specific purpose of this investigation")
    justification: str = Field(
        ...,
        min_length=20,
        description="Detailed justification, including Article 14 exemption rationale if applicable",
    )
    ttl_days: int = Field(default=365, ge=1, le=1825, description="Data retention period in days (max 5 years)")


class InvestigationResponse(BaseModel):
    """Investigation record returned by the API."""

    id: str
    query: str
    observable_type: ObservableType
    legal_basis: LegalBasis
    purpose: str
    justification: str
    ttl_days: int
    status: InvestigationStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    node_count: int = 0
    edge_count: int = 0
