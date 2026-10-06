# Operations and local observability

Production worker spans use the official OpenTelemetry SDK with a local logging
exporter. They cover a job, material download, local inference and submission.
Nested spans carry trace/span IDs and the durable job ID. This is manual worker
instrumentation, not distributed receipt-to-worker tracing or a latency guarantee.
Only approved metadata is exported. Source text, URLs, headers, exception messages,
LLM bodies and environment/resource values are excluded. No cloud exporter runs.

Docker JSON logs rotate at 10 MiB with three files per container. This is an
uncalibrated operational retention choice; logs may be lost after that bound.
The PostgreSQL inbox/outbox remains the durable evidence record.

The independent `eventdesk-monitor.timer` probes localhost once per minute. It
checks worker heartbeat, deadlines, rejected/expired predictions, encrypted backup
transfer age and the HTTPS origin. Alerts are logged only when conditions change;
an operational summary is logged once per UTC day, using cumulative receipt counts.
It cannot establish eligible daily calendar coverage or a live score.

The separate official observer retains read-only calendar and rolling-counter
snapshots. Host alerts check its failures/age and official reported delivery or
submission errors; [observation limits](OFFICIAL-OBSERVATIONS.md) remain explicit.

An origin-side HTTPS request cannot prove the external Lightsail inbound rule.
That alert also requires a separately recorded verified external probe. Public
443 is currently blocked; do not declare the webhook ready from a self-request.

Existing Telegram variables are optional. If blank, notifications remain local.
Langfuse variables are currently blank; no Langfuse service or account is assumed.
The monitor is independent of the competition worker and cannot submit predictions.

```sh
sudo journalctl -u eventdesk-monitor.service
sudo docker logs eventdesk-worker-1
sudo systemctl status eventdesk-backup.timer eventdesk-monitor.timer
```

The minute cadence, backup age guard and log retention are uncalibrated guesses.
Single-host failures can silence both worker and monitor. The two-host encrypted
restore drill is documented separately in [Recovery](RECOVERY.md).
