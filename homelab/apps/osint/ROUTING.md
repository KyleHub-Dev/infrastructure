# OSINT Stack — Pangolin Routing Configuration

Single NEWT tunnel for the entire stack. Configure the following resources/routes in your Pangolin dashboard.

## Pangolin Site Setup

1. Create **one site** in Pangolin for this stack (e.g. `osint`)
2. Use the generated NEWT_ID and NEWT_SECRET in your `.env`
3. Add the routes below as **resources** under that site

## Routes

| Route (subdomain or path) | Target (internal)              | Service         | Port | Notes                                      |
|----------------------------|--------------------------------|-----------------|------|--------------------------------------------|
| `/spiderfoot`              | `osint-spiderfoot:5001`        | SpiderFoot      | 5001 | Main OSINT dashboard, 200+ modules         |
| `/files`                   | `osint-viewer:80`              | FileBrowser     | 80   | Browse generated HTML/PDF reports          |
| `/social`                  | `osint-social-analyzer:9000`   | Social Analyzer | 9000 | Username profiling across 1000+ sites      |
| `/blackbird`               | `osint-blackbird:9797`         | Blackbird       | 9797 | Fast username enumeration web UI           |

> **Note:** Some web UIs may not work well under a subpath due to hardcoded asset paths.
> If you run into issues, use **subdomain-based routing** instead:
>
> | Subdomain                  | Target                         |
> |----------------------------|--------------------------------|
> | `spiderfoot.osint.yourdomain.com` | `osint-spiderfoot:5001` |
> | `files.osint.yourdomain.com`      | `osint-viewer:80`       |
> | `social.osint.yourdomain.com`     | `osint-social-analyzer:9000` |
> | `blackbird.osint.yourdomain.com`  | `osint-blackbird:9797`  |

## Services NOT Exposed

| Service      | Container        | Reason                              |
|--------------|------------------|-------------------------------------|
| Tor Proxy    | `osint-tor`      | Internal only, outgoing SOCKS5      |
| Tool Runner  | `osint-runner`   | CLI only, invoked via `docker exec` |

## Authentication

Auth is handled at the Pangolin level. All services behind the tunnel inherit your Pangolin auth policy. FileBrowser runs with `--noauth` since Pangolin gates access.
