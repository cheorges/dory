---
type: note
created: 2026-10-01
---
Inside the Grafana container the Loki data source is `http://loki:3100`: containers in the same Docker Compose network reach each other by service name, never by localhost.
