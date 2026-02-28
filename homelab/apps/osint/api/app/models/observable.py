"""Observable entity models - normalized OSINT data schema.

Inspired by the Unified Cyber Ontology (UCO) and MISP Core Format
for semantic interoperability across the intelligence graph.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Neo4j node labels for observable entities."""

    PERSON = "Person"
    USERNAME = "Username"
    EMAIL = "Email"
    DOMAIN = "Domain"
    IP_ADDRESS = "IPAddress"
    PLATFORM_ACCOUNT = "PlatformAccount"
    PHONE = "Phone"


class RelationshipType(str, Enum):
    """Neo4j edge types between entities."""

    OWNS = "OWNS"
    REGISTERED_ON = "REGISTERED_ON"
    RESOLVES_TO = "RESOLVES_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    DISCOVERED_BY = "DISCOVERED_BY"


class NormalizedDiscovery(BaseModel):
    """A single discovery from an OSINT tool, normalized to a common schema.

    This is the output format that every worker analyzer must produce.
    """

    target_entity: str = Field(..., description="The original queried value")
    observable_type: str = Field(..., description="Type of the original observable")
    tool_source: str = Field(..., description="Name of the OSINT tool that produced this")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    investigation_id: str = Field(..., description="Parent investigation ID")

    # Discovered entity
    entity_type: EntityType
    entity_value: str
    entity_metadata: dict[str, Any] = Field(default_factory=dict)

    # Relationship to target
    relationship: RelationshipType = RelationshipType.ASSOCIATED_WITH

    # GDPR
    ttl_timestamp: int = Field(..., description="Unix timestamp (ms) when this data expires")


class ObservableResponse(BaseModel):
    """Observable entity as returned by the API."""

    id: str
    entity_type: EntityType
    value: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_source: str
    confidence: float
    investigation_id: str
    created_at: datetime
    expires_at: datetime
