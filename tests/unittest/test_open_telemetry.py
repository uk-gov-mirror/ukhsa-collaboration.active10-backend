from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from main import _redact_query_string
from models import User
from service.open_telemetry_service import (
    AUTH_FLOW_KEY,
    AUTH_STEP_KEY,
    AUTH_STEPS,
    NHS_LOGIN_FLOW,
    _redact_outbound_url,
    auth_step_span,
    get_tracer,
)

_exporter = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(_exporter))


@pytest.fixture(autouse=True)
def span_exporter():
    _exporter.clear()
    yield _exporter


def test_auth_step_span_sets_filterable_annotations(span_exporter) -> None:
    with auth_step_span(AUTH_STEPS["token_exchange"]):
        pass

    span = span_exporter.get_finished_spans()[-1]
    assert span.name == AUTH_STEPS["token_exchange"]
    assert span.attributes[AUTH_STEP_KEY] == AUTH_STEPS["token_exchange"]
    assert span.attributes[AUTH_FLOW_KEY] == NHS_LOGIN_FLOW


def test_auth_step_span_records_only_exception_type_on_error(span_exporter) -> None:
    with pytest.raises(ValueError), auth_step_span(AUTH_STEPS["token_exchange"]):
        raise ValueError("message-that-could-echo-request-data")

    span = span_exporter.get_finished_spans()[-1]
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "ValueError"
    # The exception message must never be recorded on the span
    assert not span.events
    assert "message-that-could-echo-request-data" not in str(span.attributes)


def test_redact_query_string_removes_callback_query(span_exporter) -> None:
    scope = {"path": "/nhs_login/callback"}
    with get_tracer().start_as_current_span("server-span") as span:
        _redact_query_string(span, scope)

    recorded = span_exporter.get_finished_spans()[-1]
    assert recorded.attributes["http.target"] == "/nhs_login/callback"
    assert recorded.attributes["http.url"] == "/nhs_login/callback"
    assert recorded.attributes["url.full"] == "/nhs_login/callback"
    assert recorded.attributes["url.query"] == "REDACTED"


def test_redact_query_string_handles_missing_span() -> None:
    _redact_query_string(None, {"path": "/nhs_login/callback"})


def test_redact_outbound_url_strips_query(span_exporter) -> None:
    class OutboundRequest:
        url = "https://auth.example.nhs.uk/token?code=secret-code&state=abc"

    with get_tracer().start_as_current_span("client-span") as span:
        _redact_outbound_url(span, OutboundRequest())

    recorded = span_exporter.get_finished_spans()[-1]
    assert recorded.attributes["http.url"] == "https://auth.example.nhs.uk/token"
    assert recorded.attributes["url.full"] == "https://auth.example.nhs.uk/token"


def test_jwt_validation_span_emitted_for_authenticated_request(
    client: TestClient, authenticated_user: User, span_exporter
) -> None:
    resp = client.get(
        "/v1/users/", headers={"Authorization": f"Bearer {authenticated_user.token.token}"}
    )
    assert resp.status_code == HTTPStatus.OK

    spans = [
        s for s in span_exporter.get_finished_spans() if s.name == AUTH_STEPS["jwt_validation"]
    ]
    assert spans, "jwt-validation subsegment was not emitted"
    span = spans[-1]
    assert span.attributes[AUTH_STEP_KEY] == AUTH_STEPS["jwt_validation"]
    assert span.attributes[AUTH_FLOW_KEY] == NHS_LOGIN_FLOW
    assert "auth.cache_hit" in span.attributes


def test_no_authorization_code_in_trace_attributes(client: TestClient, span_exporter) -> None:
    secret_code = "super-secret-authorization-code"  # pragma: allowlist secret
    resp = client.get(
        f"/nhs_login/callback?code={secret_code}&state=active10_12345",
        follow_redirects=False,
    )
    assert resp.status_code == HTTPStatus.TEMPORARY_REDIRECT

    spans = span_exporter.get_finished_spans()
    assert spans
    for span in spans:
        for value in span.attributes.values():
            assert secret_code not in str(value)
