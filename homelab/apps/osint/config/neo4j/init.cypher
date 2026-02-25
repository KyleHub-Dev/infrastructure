// ============================================================
// Neo4j Schema Initialization
// Run once on first deployment:
//   docker compose exec neo4j cypher-shell -u neo4j -p 'password' < config/neo4j/init.cypher
// ============================================================

// --- Constraints (enforce uniqueness) ---

CREATE CONSTRAINT username_unique IF NOT EXISTS
FOR (u:Username) REQUIRE u.value IS UNIQUE;

CREATE CONSTRAINT email_unique IF NOT EXISTS
FOR (e:Email) REQUIRE e.value IS UNIQUE;

CREATE CONSTRAINT domain_unique IF NOT EXISTS
FOR (d:Domain) REQUIRE d.value IS UNIQUE;

CREATE CONSTRAINT ip_unique IF NOT EXISTS
FOR (i:IPAddress) REQUIRE i.value IS UNIQUE;

CREATE CONSTRAINT platform_account_unique IF NOT EXISTS
FOR (a:PlatformAccount) REQUIRE a.value IS UNIQUE;

CREATE CONSTRAINT investigation_id_unique IF NOT EXISTS
FOR (inv:Investigation) REQUIRE inv.id IS UNIQUE;

// --- Indexes (query performance) ---

CREATE INDEX observable_value IF NOT EXISTS
FOR (n:Observable) ON (n.value);

CREATE INDEX node_ttl IF NOT EXISTS
FOR (n:Observable) ON (n.ttl);

CREATE INDEX investigation_created_by IF NOT EXISTS
FOR (inv:Investigation) ON (inv.created_by);

CREATE INDEX investigation_status IF NOT EXISTS
FOR (inv:Investigation) ON (inv.status);

// --- TTL Index ---
// Used by the GDPR purge job to efficiently find expired nodes

CREATE INDEX node_expiry IF NOT EXISTS
FOR (n:Observable) ON (n.ttl);
