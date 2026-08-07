from app.memory.api.models import MemorySubmitResponse
from app.memory.models.event import MemoryEvent, MemoryEventStatus
from app.memory.events import MemoryDomainEvent


class MemoryService:
    """The only external Memory API: retrieve(request) and submit(request)."""

    def __init__(self, repository, read_pipeline, authorization_provider,
                 event_sink=None):
        self._repository = repository
        self.read_pipeline = read_pipeline
        self.authorization_provider = authorization_provider
        self.event_sink = event_sink

    def retrieve(self, request):
        try:
            context = self.read_pipeline.execute(request)
        except PermissionError as error:
            self._publish("memory.read.denied", {
                "trace_id": request.trace_id, "user_id": request.scope.user_id,
                "agent_id": request.scope.agent_id, "tenant_id": request.scope.tenant_id,
                "reason": str(error),
            })
            raise
        self._publish("memory.read.completed", {
            "trace_id": request.trace_id, "user_id": request.scope.user_id,
            "agent_id": request.scope.agent_id, "tenant_id": request.scope.tenant_id,
            "reference_count": len(context.references),
        })
        return context

    def submit(self, request):
        self.authorization_provider.authorize_ingest(
            request.principal, request.scope, request.source
        )
        event = MemoryEvent.from_submit_request(request)
        event = self._repository.save_event(event)
        return MemorySubmitResponse(
            accepted=True, event_id=event.event_id, status=event.status,
        )

    def _publish(self, event_type, payload):
        self._repository.add_outbox(MemoryDomainEvent(
            event_type=event_type,
            aggregate_id=payload.get("event_id", payload.get("trace_id", "")),
            payload=dict(payload),
        ))
