from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagators.aws import AwsXRayPropagator
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from utils.base_config import config

AUTH_FLOW_KEY = "auth.flow"
AUTH_STEP_KEY = "auth.step"

NHS_LOGIN_FLOW = "nhs-login"

# Auth journey step names recorded in the auth.step annotation.
AUTH_STEPS = {
    "authorize_redirect": "nhs-login-authorize-redirect",
    "authorization_response": "nhs-login-authorization-response",
    "token_exchange": "nhs-login-token-exchange",
    "userinfo": "nhs-login-userinfo",
    "session_write": "session-write",
    "jwt_validation": "jwt-validation",
}


def _redact_outbound_url(span, request):
    if span is None or not span.is_recording():
        return
    parts = urlsplit(request.url)
    redacted = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    for attribute in ("http.url", "url.full"):
        span.set_attribute(attribute, redacted)


def setup_telemetry():
    resource = Resource.create({"service.name": config.otel_service_name})
    provider = TracerProvider(resource=resource, id_generator=AwsXRayIdGenerator())

    processor = BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=config.otel_exporter_otlp_endpoint,
            insecure=config.otel_exporter_otlp_insecure,
        )
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    propagate.set_global_textmap(AwsXRayPropagator())
    RequestsInstrumentor().instrument(request_hook=_redact_outbound_url)
    RedisInstrumentor().instrument()


def get_tracer():
    return trace.get_tracer("active10.nhs-login-auth")


@contextmanager
def auth_step_span(step: str, flow: str = NHS_LOGIN_FLOW):
    """
    Times one step of NHS Login (e.g. token exchange) so we can find it in X-Ray.

    Tags the span with auth.step and auth.flow for filtering. On failure, records
    only the exception type — never tokens, codes, or user details.
    """
    with get_tracer().start_as_current_span(
        step,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute(AUTH_STEP_KEY, step)
        span.set_attribute(AUTH_FLOW_KEY, flow)
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise
