from app.memory.api.models import MemorySubmitResponse
from app.memory.governance.policy import MemoryAccessDenied
from app.memory.models.event import MemoryEvent, MemoryEventStatus


class MemoryService:
    """The only external Memory API: retrieve(request) and submit(request)."""

    def __init__(self, repository, read_pipeline, event_publisher=None):
        self._repository = repository
        self.read_pipeline = read_pipeline
        self.event_publisher = event_publisher
        self.consumer = None

    def attach_consumer(self, consumer):
        self.consumer = consumer

    def retrieve(self, request):
        try:
            context = self.read_pipeline.execute(request)
        except MemoryAccessDenied as error:
            self._publish("memory.read.denied", {
                "trace_id": request.trace_id, "user_id": request.user_id,
                "agent_id": request.agent_id, "tenant_id": request.tenant_id,
                "reason": str(error),
            })
            raise
        self._publish("memory.read.completed", {
            "trace_id": request.trace_id, "user_id": request.user_id,
            "agent_id": request.agent_id, "tenant_id": request.tenant_id,
            "reference_count": len(context.references),
        })
        return context

    def submit(self, request):
        event = MemoryEvent(
            trace_id=request.trace_id, task_id=request.task_id,
            agent_id=request.agent_id, user_id=request.user_id,
            tenant_id=request.tenant_id, department_id=request.department_id,
            event_type=request.event_type, input=dict(request.input),
            output=dict(request.output), tool_results=list(request.tool_results),
            metadata=dict(request.metadata),
        )
        self._repository.save_event(event)
        if self.consumer is not None:
            self.consumer.enqueue(event.event_id)
        return MemorySubmitResponse(True, event.event_id, MemoryEventStatus.RECEIVED)

    def _publish(self, event_type, payload):
        if self.event_publisher:
            self.event_publisher(event_type, payload)
