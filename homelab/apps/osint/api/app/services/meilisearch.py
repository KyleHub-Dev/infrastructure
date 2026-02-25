"""Meilisearch document store client service."""

import meilisearch

from app.config import settings


class MeilisearchService:
    """Manages the Meilisearch client for raw payload indexing and search."""

    INDEX_NAME = "osint_documents"

    def __init__(self):
        self._client: meilisearch.Client | None = None

    def connect(self):
        """Initialize the Meilisearch client and ensure index exists."""
        self._client = meilisearch.Client(settings.meili_url)

        # Create or get the documents index
        try:
            self._client.get_index(self.INDEX_NAME)
        except meilisearch.errors.MeilisearchApiError:
            self._client.create_index(self.INDEX_NAME, {"primaryKey": "id"})

        # Configure searchable and filterable attributes
        index = self._client.index(self.INDEX_NAME)
        index.update_filterable_attributes([
            "investigation_id",
            "tool_source",
            "entity_type",
            "target_entity",
            "expires_at",
        ])
        index.update_searchable_attributes([
            "entity_value",
            "target_entity",
            "raw_content",
            "tool_source",
        ])

    @property
    def client(self) -> meilisearch.Client:
        if not self._client:
            raise RuntimeError("Meilisearch client not initialized. Call connect() first.")
        return self._client

    @property
    def index(self):
        return self.client.index(self.INDEX_NAME)

    def add_document(self, document: dict):
        """Index a single document."""
        self.index.add_documents([document])

    def add_documents(self, documents: list[dict]):
        """Index multiple documents."""
        self.index.add_documents(documents)

    def search(self, query: str, filters: str | None = None, limit: int = 50) -> dict:
        """Full-text search across indexed documents."""
        params: dict = {"limit": limit}
        if filters:
            params["filter"] = filters
        return self.index.search(query, params)

    def delete_by_investigation(self, investigation_id: str):
        """Delete all documents belonging to an investigation."""
        self.index.delete_documents({"filter": f"investigation_id = '{investigation_id}'"})

    def delete_by_entity(self, entity_value: str):
        """Delete all documents referencing a specific entity value."""
        self.index.delete_documents({"filter": f"entity_value = '{entity_value}'"})


# Singleton instance
meili_service = MeilisearchService()
