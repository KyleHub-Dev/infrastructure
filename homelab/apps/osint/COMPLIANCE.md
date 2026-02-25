# OSINT Platform — GDPR & EU AI Act Compliance Guide

> **This document is a compliance framework, not legal advice.**
> Consult a qualified data protection officer before deploying in production.

---

## 1. Legal Basis for Processing

This platform processes publicly available personal data under **GDPR Article 6(1)(f) — Legitimate Interest**.

### Three-Part Balancing Test (Mandatory)

Before any investigation is initiated, the operator must document:

1. **Legitimate Interest** — A clear, lawful, specific purpose (e.g., fraud prevention, cybersecurity threat investigation, IP infringement, corporate due diligence)
2. **Necessity** — The data processing is strictly necessary; no less-invasive alternative exists
3. **Balancing** — The data subject's fundamental rights do not override the operator's interest

> ⚠️ The public nature of data does **not** nullify GDPR obligations. Algorithmic correlation of diverse datasets raises the risk profile significantly.

---

## 2. Technical Compliance Controls

### 2.1 Data Minimization (Article 5(1)(c))

| Control | Implementation |
|---|---|
| Ephemeral scraping | Workers parse raw output in-memory, discarding irrelevant metadata before persisting |
| Schema enforcement | Only fields defined in the normalized UCO schema are written to Neo4j |
| Raw payload indexing | Full raw outputs go to Meilisearch for search but are TTL-bound |

### 2.2 Purpose Limitation (Article 5(1)(b))

| Control | Implementation |
|---|---|
| Investigation isolation | Each investigation is a separate entity in Neo4j with its own subgraph |
| RBAC | API middleware enforces role-based access; users only see their own investigations |
| Audit trail | Every API action is logged with the authenticated `Remote-User` identity and timestamp |

### 2.3 Storage Limitation & Right to Erasure (Articles 5(1)(e) & 17)

| Control | Implementation |
|---|---|
| TTL enforcement | Every Neo4j node carries a `ttl` timestamp. A Celery Beat job runs daily to purge expired nodes and cascade-delete edges |
| Meilisearch TTL | Documents carry an `expires_at` field; the same cleanup job deletes expired documents |
| Manual erasure | API endpoint `DELETE /api/v1/observables/{id}` removes a node, all edges, and all Meilisearch documents referencing it |
| Default retention | Configurable via `DEFAULT_TTL_DAYS` (default: 365 days / 1 year) |

### 2.4 Transparency (Article 14)

Article 14 requires notification to data subjects when their data is collected indirectly. For covert investigations, exemptions under **Article 14(5)(b)** or **Member State derogations (Article 23)** may apply.

| Requirement | Implementation |
|---|---|
| DPIA logging | The API requires a `legal_basis` and `justification` field when creating an investigation |
| Exemption documentation | If Article 14 notification is waived, the investigation record must contain a written rationale |
| DPIA storage | Investigation metadata (purpose, legal basis, justification) is stored alongside the case in Neo4j |

---

## 3. EU AI Act Compliance

### 3.1 Prohibited Practices (Article 5)

The following are **banned by design** in this platform:

| Prohibition | How Enforced |
|---|---|
| **Social scoring** | No threat scoring, risk ranking, or behavioral classification of individuals |
| **Untargeted biometric scraping** | Workers are programmed to skip facial image extraction for biometric databases |
| **Predictive criminal profiling** | No ML models that predict criminal behavior from profiling alone |

### 3.2 High-Risk System Avoidance

If AI/ML is added (e.g., LLM summarization, entity extraction), the scope must be restricted to:
- Named Entity Recognition (NER) on scraped text
- Text summarization of raw documents
- Pattern matching / deduplication

The platform must **not** autonomously:
- Assess work performance, economic situation, or reliability
- Assign credibility or trustworthiness scores
- Make risk assessments without mandatory human-in-the-loop review

---

## 4. Data Protection Impact Assessment (DPIA)

A DPIA is mandatory before deploying this platform (GDPR Article 35). The DPIA must cover:

1. **Description** of the processing operations and purposes
2. **Necessity and proportionality** assessment
3. **Risk assessment** to data subjects' rights and freedoms
4. **Mitigation measures** (TTL, RBAC, audit logging, data minimization)

### DPIA in the Platform

Every investigation created through the API serves as a micro-DPIA record:

```json
{
  "investigation_id": "inv-2026-001",
  "created_by": "analyst@yourdomain.com",
  "created_at": "2026-02-25T20:00:00Z",
  "query": "jdoe_89",
  "observable_type": "username",
  "legal_basis": "legitimate_interest",
  "purpose": "Cybersecurity threat investigation — tracking compromised account resale",
  "justification": "Target username linked to credential dumps on dark web forums. Article 14(5)(b) exemption applied: notification would alert the threat actor.",
  "ttl_days": 180,
  "status": "active"
}
```

---

## 5. Copyright & Terms of Service

### Database Directive (Sui Generis Right)

Scraping substantial portions of a protected database (e.g., systematically extracting a corporate directory) infringes the EU Database Directive's *sui generis* right. Workers should:
- Scrape only data directly relevant to the target observable
- Respect `robots.txt` where legally required
- Avoid systematic bulk extraction of any single platform

### Terms of Service (Ryanair v PR Aviation)

Website ToS can contractually restrict scraping even when no IP protection applies. Workers should:
- Implement configurable rate limiting per target platform
- Log which platforms were queried for audit purposes
- Allow disabling specific platform scrapers via configuration

---

## 6. Operator Responsibilities

| Responsibility | Frequency |
|---|---|
| Maintain written DPIA | Before deployment, reviewed annually |
| Document legal basis per investigation | Per investigation |
| Review and purge expired data | Automated (daily Celery Beat job) |
| Monitor for scope creep in AI usage | Ongoing |
| Respond to data subject access requests (Article 15) | Within 30 days of request |
| Report data breaches to supervisory authority | Within 72 hours (Article 33) |

---

## 7. Clearview AI Precedent

The €30.5M fine against Clearview AI (Dutch DPA, September 2024) established:

1. Public data is **not** exempt from GDPR
2. Failure to facilitate access/erasure requests is a severe violation
3. GDPR applies extraterritorially to any entity processing EU citizens' data

This platform's TTL enforcement, RBAC, erasure endpoints, and investigation-level DPIA logging are direct architectural responses to these enforcement precedents.

---

*Last updated: 2026-02-25*
