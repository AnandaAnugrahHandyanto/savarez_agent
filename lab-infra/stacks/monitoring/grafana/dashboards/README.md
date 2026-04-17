# Grafana Dashboards

Pre-built dashboards to import. Download JSON files and place them here — 
Grafana will auto-provision them on startup.

## Recommended Dashboards (import by ID from grafana.com)

| Dashboard | ID | What it shows |
|---|---|---|
| Node Exporter Full | 1860 | Full VPS metrics — CPU, RAM, disk, network |
| cAdvisor Docker | 14282 | Per-container CPU, RAM, network |
| Loki Logs | 13639 | Log explorer with search |
| Traefik v3 | 17346 | Request rates, errors, latency per service |
| VictoriaMetrics | 10229 | VM internal metrics |

## How to Import

1. Go to Grafana → Dashboards → Import
2. Enter the dashboard ID
3. Select VictoriaMetrics as the datasource
4. Save

Or download the JSON and drop it in this folder — it will auto-load on next restart.
