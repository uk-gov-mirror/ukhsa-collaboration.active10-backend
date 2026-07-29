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

STEP_AUTHORIZE_REDIRECT = "nhs-login-authorize-redirect"
STEP_AUTHORIZATION_RESPONSE = "nhs-login-authorization-response"
STEP_TOKEN_EXCHANGE = "nhs-login-token-exchange"
STEP_USERINFO = "nhs-login-userinfo"
STEP_SESSION_WRITE = "session-write"
STEP_JWT_VALIDATION = "jwt-validation"

tracer = trace.get_tracer("active10.nhs-login-auth")


def _strip_query(span, request):
    if not span.is_recording():
        return

    scheme, netloc, path, _, _ = urlsplit(request.url)
    clean = urlunsplit((scheme, netloc, path, "", ""))

    span.set_attribute("http.url", clean)
    span.set_attribute("url.full", clean)  # newer semconv name


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
    RequestsInstrumentor().instrument(request_hook=_strip_query)
    RedisInstrumentor().instrument()


@contextmanager
def auth_step_span(step: str, flow: str = NHS_LOGIN_FLOW):
    """
    Open a span around one step of the auth flow.

    :param step: Step name, one of the STEP_* constants above.
    :param flow: Flow name recorded in the auth.flow annotation.
    """
    with tracer.start_as_current_span(
        step,
        record_exception=False,  # exception messages can contain tokens/codes
        set_status_on_exception=False,
    ) as span:
        span.set_attribute(AUTH_STEP_KEY, step)
        span.set_attribute(AUTH_FLOW_KEY, flow)
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise
