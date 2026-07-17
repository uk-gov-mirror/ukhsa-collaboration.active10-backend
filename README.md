# Active10 Backend Service

A FastAPI-based backend service for the Active10 mobile app, providing activity tracking, and NHS Login integration.

### Project Structure
```
├── api/                    # API endpoints
│   ├── v1/                # Version 1 API routes
│   ├── v2/                # Version 2 API routes
│   ├── nhs_login.py       # NHS Login authentication
│   └── healthcheck.py     # Health monitoring
├── auth/                  # Authentication & authorization
├── crud/                  # Database operations
├── db/                    # Database configuration & migrations
├── models/                # SQLAlchemy database models
├── schemas/               # Pydantic request/response schemas
├── service/               # Business logic layer
├── nhs/                   # NHS API integrations
├── gojauntly/             # GoJauntly integration
├── utils/                 # Utility functions
└── tests/                 # Test suites
```

## Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Docker

### Quick Start with Docker

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd active10-backend
   ```

2. **Start services:**
   ```bash
   docker compose up
   ```

3. **Access the application:**
   - API: `https://active10.localhost`
   - API Documentation: `https://active10.localhost/docs`

## OpenTelemetry Tracing (AWS X-Ray)

The backend emits OpenTelemetry traces for the NHS Login authentication journey. Spans are exported over OTLP(Open Telemetry Protocol) /gRPC (Google Remote Procedure Call) to an AWS Distro for OpenTelemetry (ADOT) Collector, which forwards them to AWS X-Ray:

```
Active10 backend (Open Telemetry) → ADOT Collector (OTLP :4317) → AWS X-Ray → CloudWatch console
```

The `adot-collector` service is part of `docker-compose.yml` and starts automatically with the stack.

### Prerequisites

Complete these **before** starting the stack — without them the app will not boot, or traces will silently never reach X-Ray:

1. **AWS credentials for the collector.** The collector reads `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from your shell environment (or `~/.aws`, which is mounted read-only). In AWS environments prefer an IAM role. Never commit keys.
2. **IAM permissions.** The identity used by the collector needs `AWSXRayDaemonWriteAccess` (or at minimum `xray:PutTraceSegments` + `xray:PutTelemetryRecords`). Anyone viewing traces needs `AWSXRayReadOnlyAccess`.
3. **Region.** `AWS_REGION` must match the region where you expect traces (defaults to `eu-west-2` in `collector-config.yaml`). Traces only appear in the console for that region.
4. **Required environment variables in `.env`** (loaded via `utils/base_config.py`):

  | Variable                      | Required                                | Purpose                                                 | Local value                  |
  | ----------------------------- | --------------------------------------- | ------------------------------------------------------- | ---------------------------- |
  | `OTEL_EXPORTER_OTLP_ENDPOINT` | **Yes — app fails to start without it** | Collector OTLP/gRPC address                             | `http://adot-collector:4317` |
  | `OTEL_EXPORTER_OTLP_INSECURE` | No (default `false`)                    | Allow plaintext OTLP; only for private/sidecar networks | `false`                      |
  | `OTEL_SERVICE_NAME`           | No (default `active10-auth`)            | Service name shown in X-Ray                             | `active10-auth`              |


### Setup

1. **Configure `.env`:**
  ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=http://adot-collector:4317
   OTEL_EXPORTER_OTLP_INSECURE=true
   OTEL_SERVICE_NAME=active10-auth
  ```
2. **Export AWS credentials** (local development only):
  ```bash
   export AWS_REGION=eu-west-2
   export AWS_ACCESS_KEY_ID=<your-key-id>
   export AWS_SECRET_ACCESS_KEY=<your-secret-key>
  ```
3. **Start the stack** (app + collector):
  ```bash
   docker compose up --build
  ```
4. **Generate traffic** — run the NHS Login flow (redirect + callback) or any authenticated API call.
5. **View traces** — AWS Console → CloudWatch → X-Ray traces (service `active10-auth`). Filter by auth step, e.g. `annotation.auth_step = "nhs-login-token-exchange"`.

### Troubleshooting


| Symptom                                                | Check                                                              |
| ------------------------------------------------------ | ------------------------------------------------------------------ |
| App exits on startup with a config validation error    | `OTEL_EXPORTER_OTLP_ENDPOINT` missing from `.env`                  |
| `Failed to export ... adot-collector:4317` in app logs | Collector container running? Both services on the `proxy` network? |
| No traces in the X-Ray console                         | Region mismatch, missing IAM write policy, or invalid credentials  |
| Export errors while running `make unit-tests`          | Expected noise — tests don't need a collector and still pass       |


## Testing

### Run Test Suite
```bash
# Run all unit tests
make unit-tests
```

### Test Configuration
Tests are configured in `pyproject.toml` with coverage reporting for:
- API endpoints (`api/`)
- Business logic (`service/`)
- Database operations (`crud/`)
- Models (`models/`)
- Authentication (`auth/`)
- NHS integrations (`nhs/`)

## License

This project is licensed under the [GNU GPLv3](./LICENSE.md).
