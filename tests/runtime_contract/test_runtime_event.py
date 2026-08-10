import json
import unittest

from app.runtime.contracts import RuntimeEvent, RuntimeEventType


class RuntimeEventTest(unittest.TestCase):
    def test_runtime_event_round_trips(self):
        event = RuntimeEvent(
            RuntimeEventType.NODE_COMPLETED, "task-1", "agent", payload={"ok": True},
        )
        restored = RuntimeEvent.from_dict(json.loads(json.dumps(event.to_dict())))
        self.assertEqual(event, restored)

    def test_unknown_event_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported Runtime event"):
            RuntimeEvent("platform.event", "task-1")
