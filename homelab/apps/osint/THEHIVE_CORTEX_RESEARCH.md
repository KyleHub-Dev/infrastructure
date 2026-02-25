# TheHive + Cortex: Deep Dive Research

> Researched February 2026. Honest assessment, not marketing.

---

## 1. Architecture: How TheHive and Cortex Actually Work Together

### Components

**TheHive** is the case management / investigation platform. **Cortex** is the observable analysis engine. They are separate applications that communicate over REST API.

```
                    +-----------+
                    |  Analyst  |
                    +-----+-----+
                          |
                    +-----v-----+
                    |  TheHive   |  (Case mgmt, alerts, observables)
                    |  Port 9000 |
                    +-----+-----+
                          |  REST API (HTTP)
                    +-----v-----+
                    |   Cortex   |  (Analyzer orchestration)
                    |  Port 9001 |
                    +-----+-----+
                      |       |
              +-------+       +-------+
              |  Docker Socket        |
         +----v----+            +-----v----+
         |Analyzer1|            |Analyzer N|
         |(container)           |(container)|
         +---------+            +----------+

Databases:
  TheHive  -> Cassandra (data) + Elasticsearch (index/search) + MinIO (file storage)
  Cortex   -> Elasticsearch (its own instance, separate recommended)
```

### Data Flow

1. Analyst creates a case in TheHive, adds observables (IPs, domains, emails, usernames, hashes, files)
2. Analyst clicks "Analyze" on an observable -> TheHive sends a job request to Cortex via REST API
3. Cortex looks up which analyzers accept that data type, spins up the analyzer (as a Docker container or subprocess)
4. Analyzer receives JSON input (the observable + config), runs its logic, returns JSON output
5. Cortex stores the result and sends it back to TheHive
6. TheHive displays the report inline on the observable, with a taxonomy summary (colored tags like "malicious", "safe", "suspicious")

### Database Stack

| Component | TheHive 5 | Cortex |
|-----------|-----------|--------|
| Primary DB | Apache Cassandra 4.x (via JanusGraph) | Elasticsearch 7.x |
| Search/Index | Elasticsearch 7.x (separate instance recommended) | -- |
| File Storage | MinIO (S3-compatible) or local filesystem | -- |

**Key gotcha:** TheHive and Cortex should NOT share the same Elasticsearch instance. Different version requirements and index conflicts are a real risk.

---

## 2. Cortex Analyzers: The Practical Details

### Analyzer Structure

Every analyzer ("neuron") is a directory with at minimum:

```
analyzers/MyTool/
  MyTool_lookup.json      # Descriptor: defines name, data types, config params
  analyzer.py             # Python script (or any language)
  requirements.txt        # Python dependencies
```

### JSON Descriptor (MyTool_lookup.json)

```json
{
  "name": "MyTool_lookup",
  "version": "1.0",
  "author": "Your Name",
  "url": "https://github.com/you/your-analyzers",
  "license": "AGPL-V3",
  "description": "Runs MyTool against a username observable",
  "dataTypeList": ["other"],
  "baseConfig": "MyTool",
  "command": "MyTool/analyzer.py",
  "config": {
    "check_tlp": true,
    "max_tlp": 3,
    "check_pap": true,
    "max_pap": 3,
    "service": "lookup"
  },
  "configurationItems": [
    {
      "name": "timeout",
      "description": "Execution timeout in seconds",
      "type": "number",
      "multi": false,
      "required": false,
      "defaultValue": 120
    }
  ]
}
```

**Supported data types:** `domain`, `file`, `filename`, `fqdn`, `hash`, `ip`, `mail`, `mail-subject`, `url`, `user-agent`, `other`, `registry`, `regexp`, `uri_path`

For username-based OSINT tools (Maigret, Sherlock, etc.), you would use `other` or `mail` as the data type.

### Python Analyzer Template

```python
#!/usr/bin/env python3
from cortexutils.analyzer import Analyzer

class MyToolAnalyzer(Analyzer):
    def __init__(self):
        Analyzer.__init__(self)
        self.timeout = self.get_param('config.timeout', 120)

    def run(self):
        try:
            observable = self.get_data()  # e.g. "johndoe"
            data_type = self.data_type    # e.g. "other"

            # YOUR LOGIC HERE - call API, run CLI tool, etc.
            result = {"found": True, "profiles": ["twitter", "github"]}

            self.report(result)
        except Exception as e:
            self.error(str(e))

    def summary(self, raw):
        taxonomies = []
        count = len(raw.get('profiles', []))
        level = 'info' if count > 0 else 'safe'
        taxonomies.append(self.build_taxonomy(
            level=level,
            namespace='MyTool',
            predicate='Profiles',
            value=str(count)
        ))
        return {'taxonomies': taxonomies}

if __name__ == '__main__':
    MyToolAnalyzer().run()
```

### Wrapping CLI Tools (Maigret, Sherlock, Holehe, Blackbird)

This is straightforward. The pattern is: `subprocess.run()` the CLI tool, parse its output (JSON preferred), return via `self.report()`.

```python
#!/usr/bin/env python3
import subprocess
import json
from cortexutils.analyzer import Analyzer

class MaigretAnalyzer(Analyzer):
    def __init__(self):
        Analyzer.__init__(self)
        self.timeout = self.get_param('config.timeout', 300)

    def run(self):
        try:
            username = self.get_data()

            cmd = [
                'maigret', username,
                '--json', 'simple',
                '--timeout', '10',
                '-a',  # all sites
                '--no-color'
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                # Maigret outputs JSON to file; parse it
                output = json.loads(result.stdout)
                self.report(output)
            else:
                self.error(f"Maigret failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            self.error("Maigret timed out")
        except Exception as e:
            self.error(str(e))

    def summary(self, raw):
        taxonomies = []
        # Count found accounts
        found = len([s for s in raw.get('sites', []) if s.get('status') == 'Claimed'])
        taxonomies.append(self.build_taxonomy(
            level='info',
            namespace='Maigret',
            predicate='Accounts',
            value=str(found)
        ))
        return {'taxonomies': taxonomies}

if __name__ == '__main__':
    MaigretAnalyzer().run()
```

**Difficulty assessment for wrapping each tool:**

| Tool | Difficulty | Notes |
|------|-----------|-------|
| Maigret | Easy | Has `--json simple` output. Wrap subprocess, parse JSON. Main issue: slow (scans 3000+ sites). |
| Sherlock | Easy | Has `--json` flag for JSON output. Straightforward. |
| Holehe | Easy | Has `--csv` and programmatic Python API (`import holehe`). Can call directly without subprocess. |
| Blackbird | Easy-Medium | JSON output available. Some versions are web-only. Use the CLI mode. |

The main challenge is NOT writing the wrapper -- it is handling **timeouts** (Maigret can take 5-10 minutes) and **output parsing** (each tool's JSON schema is different, you need to normalize it for a useful TheHive report).

### Analyzer Deployment Options

**Option A: Subprocess (legacy)**
Cortex runs the analyzer as a local Python process. You must install all dependencies on the Cortex host. Messy.

**Option B: Docker containers (recommended, available since Cortex 3.0)**
Each analyzer runs as an isolated Docker container. Cortex communicates via Docker socket.

```dockerfile
FROM python:3.11-alpine
WORKDIR /worker
COPY requirements.txt MaigretAnalyzer/
RUN pip install --no-cache-dir -r MaigretAnalyzer/requirements.txt
COPY . MaigretAnalyzer/
ENTRYPOINT ["python", "MaigretAnalyzer/analyzer.py"]
```

**Cortex Docker config requirements:**
```yaml
cortex:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock   # Access to Docker daemon
    - /tmp/cortex-jobs:/tmp/cortex-jobs            # Shared job directory
  command: >
    --analyzer.urls=["https://download.thehive-project.org/analyzers.json","/opt/custom/analyzers.json"]
    --job-directory=/tmp/cortex-jobs
    --docker-job-directory=/tmp/cortex-jobs
```

**Catalog file (analyzers.json) for custom Dockerized analyzers:**
```json
[
  {
    "name": "Maigret_lookup",
    "version": "1.0",
    "description": "Username OSINT via Maigret",
    "dataTypeList": ["other"],
    "dockerImage": "your-registry/maigret-analyzer:1.0"
  }
]
```

Yes, analyzers absolutely can (and should) run in separate containers. Each analyzer invocation spins up a fresh container, runs, returns results, and the container is destroyed. This is the cleanest approach for OSINT tools with heavy or conflicting dependencies.

---

## 3. TheHive Dashboard & UI

### What the UI Actually Offers

TheHive 5 has a modern web UI (complete rewrite from v4). It is functional but not flashy:

- **Case list view:** Table of cases with status, severity, assignee, tags, dates. Filterable and sortable.
- **Case detail view:** Title, description, severity, TLP/PAP, custom fields, tasks, observables, timeline, attached files.
- **Observable panel:** List of all observables in a case. Each shows analyzer results as colored taxonomy tags (e.g., green "safe", red "malicious"). Click to see full analyzer reports.
- **Alert management:** Ingest alerts from MISP, Cortex, or API. Preview and promote to cases.
- **Task management:** Create tasks within cases, assign to analysts, track status.
- **Timeline:** Chronological view of case events and analyst actions.

### Custom Dashboards

TheHive 5 includes a dashboard builder with 8 widget types:
- Bar charts, line charts, counters, donut charts, tables
- Dashboards can be private or shared
- Widgets query case/alert/observable data with filters
- Exportable as images or CSV; dashboard definitions as JSON

**However:** The dashboard system is basic compared to Grafana or Kibana. It is good for operational metrics (cases per week, open vs closed, severity breakdown) but NOT a data exploration tool. There is a [Grafana dashboard for TheHive](https://grafana.com/grafana/dashboards/19190-thehive/) if you want better visualization.

### Graph / Relationship View

**No.** TheHive does NOT have a Maltego-style graph visualization. There is no entity relationship graph, no link analysis view, no visual network of connections between observables.

TheHive 5.5 added the ability to "link entities" to cases, but this is metadata linking, not visual graph exploration.

If you want graph visualization, you would need to:
1. Export data via API and visualize in a separate tool (Neo4j, Gephi, Maltego CE)
2. Use MISP's built-in correlation graph (if integrated)
3. Build something custom with the API

This is a significant gap if your use case is OSINT investigation where seeing relationships between usernames, emails, and accounts is the whole point.

---

## 4. Deployment

### Docker Compose

There is an official [Docker-Templates repo](https://github.com/TheHive-Project/Docker-Templates) and [official docs](https://docs.strangebee.com/thehive/installation/docker/). A minimal compose looks roughly like:

```yaml
services:
  cassandra:
    image: cassandra:4.1
    volumes:
      - cassandra-data:/var/lib/cassandra
    environment:
      - CASSANDRA_CLUSTER_NAME=TheHive

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.x
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - es-data:/usr/share/elasticsearch/data

  minio:
    image: quay.io/minio/minio
    command: server /data --console-address ":9090"
    volumes:
      - minio-data:/data

  thehive:
    image: strangebee/thehive:5.4
    depends_on:
      - cassandra
      - elasticsearch
      - minio
    ports:
      - "9000:9000"
    volumes:
      - thehive-data:/etc/thehive

  # Cortex needs its OWN Elasticsearch
  elasticsearch-cortex:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.x
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms256m -Xmx256m"

  cortex:
    image: thehiveproject/cortex:3.1.8
    depends_on:
      - elasticsearch-cortex
    ports:
      - "9001:9001"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /tmp/cortex-jobs:/tmp/cortex-jobs
```

That is **6 containers minimum** before any analyzers run. Each analyzer invocation adds another short-lived container.

### Resource Requirements (Honest Assessment)

| Component | Minimum RAM | Comfortable RAM |
|-----------|-------------|-----------------|
| Cassandra | 1 GB | 2-4 GB |
| Elasticsearch (TheHive) | 512 MB | 1-2 GB |
| Elasticsearch (Cortex) | 256 MB | 512 MB-1 GB |
| MinIO | 128 MB | 256 MB |
| TheHive | 512 MB | 1-2 GB |
| Cortex | 256 MB | 512 MB |
| **Total baseline** | **~2.5 GB** | **~6-10 GB** |

One community member reported running successfully on 2 cores / 4 GB RAM, but that is tight. **For a homelab, 8 GB RAM dedicated to this stack is realistic. 16 GB is comfortable.** Cassandra and Elasticsearch are the memory hogs.

You also need `vm.max_map_count=262144` set on the host for Elasticsearch.

### TheHive 5 vs TheHive 4

| Aspect | TheHive 4 | TheHive 5 |
|--------|-----------|-----------|
| License | AGPL v3 (true open source) | Proprietary freemium (StrangeBee) |
| Source code | Public on GitHub | **NOT public.** GitHub repo is archived. |
| UI | Functional but dated | Complete rewrite, modern |
| Alert preprocessing | Basic | Can run Cortex analyzers on alerts before promoting to cases |
| Multi-tenancy | Basic | Improved with organizations |
| API | v0/v1 | v1 (breaking changes from v4) |
| Dashboard | Basic | Rebuilt with widget system |
| Active development | No (EOL) | Yes (StrangeBee maintains it) |

**The big change:** TheHive 4 was genuinely AGPL open source. TheHive 5 is closed-source freemium. The GitHub repo for TheHive is now archived. Cortex remains AGPL-3.0 open source.

---

## 5. Integration Ecosystem

### MISP Integration
- TheHive can pull MISP events as alerts automatically
- Can export case observables/IOCs back to MISP
- Community license: 1 MISP server. Paid: multiple.
- Configuration is straightforward (API key + URL in TheHive config)

### Webhooks / Automation
- **Community license: NO webhooks.** This is locked behind Gold license.
- With Gold+, TheHive fires webhooks on events (case_create, alert_create, observable_update, etc.)
- Common pattern: TheHive webhook -> n8n/Shuffle/custom Flask endpoint -> trigger automation
- Without webhooks, you are limited to polling the API

### API
- Full REST API for everything: cases, alerts, observables, tasks, users
- Python client: `thehive4py` (works with TheHive 5 despite the name)
- Cortex also has a full API + `cortex4py` Python client
- API is well-documented and capable

### Automatic Scans
- You can configure Cortex to auto-run specific analyzers when observables are added to a case
- Responders can take actions (block IP, send email, create ticket) based on analyzer results
- With webhooks (paid): full event-driven automation

### Notifications
- Community: email notifications only (basic)
- Paid: Slack, Mattermost, Kafka integrations

---

## 6. Licensing: The Real Story

### TheHive 5

**TheHive 5 is NOT open source.** The source code is not publicly available. It is proprietary software distributed as a freemium product by StrangeBee.

| Tier | Cost | Key Limits |
|------|------|------------|
| **Community** | Free (registration required) | 2 users, 1 org, 1 Cortex server, 1 MISP server, no webhooks, no SSO, no custom views, community support only |
| **Gold** | Paid (per user) | 5+ users, 5 orgs, 5 Cortex/MISP servers, webhooks, LDAP/SSO, email+chat support |
| **Platinum** | Paid (higher) | Unlimited Cortex/MISP, priority support, consulting |

**Critical detail:** The Community license states the software is for "initial discovery, testing, training and education purposes." This is not a generous community edition -- it is a trial/evaluation license with a 2-user hard cap.

Starting with TheHive 5.3, you MUST register for a Community license on StrangeBee's portal or the UI goes **read-only mode**. This is a phone-home / registration requirement.

### Cortex

Cortex remains **AGPL-3.0**, genuinely open source. The analyzer repository (Cortex-Analyzers) is also open source. This is the one piece of the stack you can trust to stay free.

### TheHive 4

Was AGPL-3.0, truly open source. But it is **end-of-life** and no longer maintained. Running it in 2026 means no security patches.

### The Python libraries

`thehive4py` and `cortex4py` remain AGPL open source.

---

## 7. Alternatives

### IntelOwl

| Aspect | TheHive + Cortex | IntelOwl |
|--------|-----------------|----------|
| License | TheHive: proprietary. Cortex: AGPL | Fully AGPL-3.0 open source |
| Purpose | Case management + analysis | Pure observable analysis (no case management) |
| Analyzers | ~105 | ~127 |
| Setup time | ~15-30 min (complex) | ~7 min (simpler Docker setup) |
| UI admin | Good (Cortex web UI) | Limited (config files) |
| Custom analyzers | Python + JSON descriptor | Python (Django plugin system) |
| Case management | Yes (TheHive) | No (but integrates with TheHive) |
| Resource usage | Heavy (Cassandra + 2x ES + MinIO) | Lighter (PostgreSQL + Redis + RabbitMQ) |
| Active development | Yes | Yes (very active, Honeynet Project) |

**For your use case (OSINT investigation platform):** IntelOwl is a strong alternative to Cortex specifically. It is lighter, fully open source, and has more analyzers. But it does NOT replace TheHive's case management -- it replaces Cortex. You could run IntelOwl standalone or IntelOwl + TheHive (they integrate).

### Other Platforms Worth Considering

- **OpenCTI:** Threat intelligence platform with graph visualization (uses Neo4j). More CTI-focused than investigation-focused. Heavy resource requirements.
- **MISP:** Threat intelligence sharing. Has its own correlation engine and basic graph view. Not a case management tool.
- **Shuffle:** Open source SOAR (automation/orchestration). Complements TheHive, does not replace it.
- **SpiderFoot (already in your stack):** Actually covers a lot of what Cortex analyzers do for OSINT. Has its own web UI, runs scans, correlates results. Less structured than TheHive but simpler.

---

## 8. Realistic Assessment

### Pain Points and Gotchas

1. **Resource weight:** The full stack (Cassandra + 2x Elasticsearch + MinIO + TheHive + Cortex) is heavy for a homelab. You are running 6+ containers just for infrastructure before any actual analysis happens.

2. **Licensing bait-and-switch:** TheHive 4 was open source. TheHive 5 is not. The "Community" edition is marketing language for a locked-down free tier with a 2-user cap and mandatory registration. Webhooks -- arguably essential for automation -- are paywalled.

3. **No graph visualization:** If your goal is OSINT investigation with relationship mapping (like Maltego), TheHive does not do this. It is a case management system, not a link analysis tool.

4. **Elasticsearch version sensitivity:** TheHive and Cortex have specific ES version requirements. Mismatches cause silent failures. Running two separate ES instances wastes RAM.

5. **Docker socket exposure:** Cortex needs access to the Docker socket to spawn analyzer containers. This is a security concern (container escape risk). In a homelab this is acceptable; in production, less so.

6. **Analyzer timeouts:** OSINT tools like Maigret (3000+ sites) can run for 5-10 minutes. Cortex default timeouts may kill long-running analyzers. You need to tune this.

7. **TheHive 5.3+ registration requirement:** Your instance phones home to StrangeBee's license portal. If their service goes down or they change terms, your instance goes read-only.

8. **API breaking changes:** TheHive 4 -> 5 API is not backward compatible. Existing integrations (n8n nodes, custom scripts) may need rewriting.

### Community and Support

- Discord community exists, moderately active
- GitHub issues on Cortex-Analyzers are responsive
- TheHive issues go to StrangeBee (commercial support model)
- Stack Overflow / Reddit activity is sparse
- Most tutorials/blog posts are from 2020-2023; fewer recent ones

### Maintenance Status (as of early 2026)

- **TheHive:** Actively maintained by StrangeBee (commercial product). Last update Nov 2025.
- **Cortex:** Updated Feb 2026. Maintained but development pace is slow.
- **Cortex-Analyzers:** Community-contributed, active.
- **cortexutils:** Last update May 2025.

### Learning Curve

- **Cortex standalone:** Moderate. If you know Docker and Python, writing analyzers is straightforward.
- **TheHive:** Steep. The concepts (cases, alerts, observables, tasks, organizations, TLP/PAP) require understanding IR workflows. Configuration is spread across multiple files and the web UI.
- **Full stack deployment:** Steep. Getting Cassandra + ES + MinIO + TheHive + Cortex + Docker socket sharing all working together takes troubleshooting.

---

## 9. Verdict for Your Use Case

You already have a working OSINT stack with SpiderFoot, Maigret, Sherlock, Holehe, Blackbird in Docker. The question is whether TheHive + Cortex adds enough value.

### What TheHive + Cortex would give you:
- Structured case management (track investigations over time)
- Centralized observable analysis (run all tools against one username from one UI)
- Audit trail of what was searched and when
- Report generation per case

### What it would cost you:
- 6+ additional containers, 4-8 GB additional RAM
- Proprietary license with 2-user cap (Community)
- No graph visualization (your current SpiderFoot actually has better visual output)
- Significant setup and maintenance overhead
- Mandatory registration with StrangeBee

### Alternatives to consider for your stack:
1. **Keep SpiderFoot as your hub** -- it already does multi-source correlation with a web UI
2. **Add IntelOwl** instead of Cortex -- lighter, fully open source, more analyzers, wraps CLI tools similarly
3. **Build a lightweight custom orchestrator** -- your `scan.sh` + a simple Flask/FastAPI dashboard could do 80% of what you need without the overhead
4. **Consider OpenCTI** if you specifically want graph visualization of entity relationships

---

## Sources

- [TheHive 5 Official Documentation](https://docs.strangebee.com/thehive/)
- [Cortex Installation Guide](https://docs.strangebee.com/cortex/installation-and-configuration/)
- [How to Create an Analyzer](https://thehive-project.github.io/Cortex-Analyzers/dev_guides/how-to-create-an-analyzer/)
- [Dockerize Custom Analyzers](https://thehive-project.github.io/Cortex-Analyzers/dev_guides/dockerize-your-custom-analyzers-responders/)
- [Cortex-Analyzers GitHub Repo](https://github.com/TheHive-Project/Cortex-Analyzers)
- [Docker-Templates GitHub Repo](https://github.com/TheHive-Project/Docker-Templates)
- [TheHive Pricing (On-Prem)](https://strangebee.com/thehive-pricing-on-prem/)
- [TheHive 5 License FAQ](https://medium.com/strangebee-announcements/faq-for-thehive-5s-upcoming-distribution-model-af0ccb95d18)
- [Cortex vs IntelOwl Comparison](https://ahmedmusaad.com/cortex-vs-intelowl/)
- [IntelOwl GitHub](https://github.com/intelowlproject/IntelOwl)
- [TheHive Dashboard Docs](https://docs.strangebee.com/thehive/user-guides/analyst-corner/dashboard/about-dashboards/)
- [TheHive MISP Integration](https://docs.strangebee.com/thehive/administration/misp-integration/about-misp-integration/)
- [TheHive System Requirements](https://docs.strangebee.com/thehive/installation/system-requirements/)
- [TheHive Docker Deployment](https://docs.strangebee.com/thehive/installation/docker/)
- [Grafana Dashboard for TheHive](https://grafana.com/grafana/dashboards/19190-thehive/)
- [cortexutils on PyPI](https://pypi.org/project/cortexutils/)
- [TheHive 5 Licensing](https://docs.strangebee.com/thehive/installation/licenses/about-licenses/)
- [Community License Terms PDF](https://strangebee.com/wp-content/uploads/2024/06/TheHive-5-Community-License-General-Terms-latest.pdf)
