---
type: note
created: 2026-10-01
---
# Caddy in front of every service
Caddy runs in the same Docker Compose network as the services and proxies to them by service name (`reverse_proxy app:8080`).
