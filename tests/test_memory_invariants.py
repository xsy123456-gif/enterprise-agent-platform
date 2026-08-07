import unittest

from app.memory.api.models import MemoryPrincipal, MemoryRetrieveRequest
from app.memory.embedding.models import EmbeddingSpace
from app.memory.models.identity import MemoryIdentity
from app.memory.errors import MemoryInvariantViolation
from app.memory.models.item import MemoryItem, MemoryItemStatus
from app.memory.models.scope import MemoryScope
from tests.memory_repository import TestMemoryRepository


def memory_item(scope, identity, content, version=1):
    return MemoryItem(
        memory_key=identity.memory_key,
        type=identity.type,
        entity_id=identity.entity_id,
        attribute=identity.attribute,
        content=content,
        importance=0.8,
        confidence=0.9,
        source="invariant-test",
        tenant_id=scope.tenant_id,
        department_id=scope.department_id,
        user_id=scope.user_id,
        agent_id=scope.agent_id,
        version=version,
    )


class MemoryScopeIdentityTest(unittest.TestCase):
    def test_embedding_spaces_are_stable_and_distinct(self):
        first = EmbeddingSpace("ollama", "bge-m3", "v1", 3)
        same = EmbeddingSpace("ollama", "bge-m3", "v1", 3)
        different = EmbeddingSpace("openai", "bge-m3", "v1", 3)
        self.assertEqual(first.space_id, same.space_id)
        self.assertNotEqual(first.space_id, different.space_id)
    def test_scope_and_identity_are_trimmed_and_structured(self):
        scope = MemoryScope(" tenant ", " user ", " agent ", " dept ")
        identity = MemoryIdentity(" customer ", " a:b ", " budget ")
        self.assertEqual(
            ("tenant", "dept", "user", "agent"),
            (scope.tenant_id, scope.department_id, scope.user_id, scope.agent_id),
        )
        self.assertEqual(("customer", "a:b", "budget"), (
            identity.type, identity.entity_id, identity.attribute,
        ))

    def test_required_scope_and_identity_fields_reject_empty_values(self):
        for field, values in {
            "tenant": ("", "user", "agent", None),
            "user": ("tenant", " ", "agent", None),
            "agent": ("tenant", "user", "", None),
            "department": ("tenant", "user", "agent", " "),
        }.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                MemoryScope(*values)
        with self.assertRaises(ValueError):
            MemoryIdentity("customer", "", "budget")

    def test_structured_identity_does_not_depend_on_ambiguous_display_key(self):
        repository = TestMemoryRepository()
        scope = MemoryScope("tenant", "user", "agent", "dept")
        first = MemoryIdentity("a", "b:c", "d")
        second = MemoryIdentity("a", "b", "c:d")
        self.assertEqual(first.memory_key, second.memory_key)
        repository.create_item(memory_item(scope, first, "first"))
        repository.create_item(memory_item(scope, second, "second"))
        self.assertEqual("first", repository.find_active_head(scope, first).content)
        self.assertEqual("second", repository.find_active_head(scope, second).content)

    def test_repository_isolates_all_scope_dimensions(self):
        repository = TestMemoryRepository()
        identity = MemoryIdentity("customer", "customer_a", "budget")
        scopes = [
            MemoryScope("tenant-a", "user-a", "agent-a", "dept-a"),
            MemoryScope("tenant-b", "user-a", "agent-a", "dept-a"),
            MemoryScope("tenant-a", "user-a", "agent-a", "dept-b"),
            MemoryScope("tenant-a", "user-b", "agent-a", "dept-a"),
            MemoryScope("tenant-a", "user-a", "agent-b", "dept-a"),
            MemoryScope("tenant-a", "user-a", "agent-a", None),
        ]
        for index, scope in enumerate(scopes):
            repository.create_item(memory_item(scope, identity, index))

        for index, scope in enumerate(scopes):
            with self.subTest(scope=scope):
                self.assertEqual(
                    index, repository.find_active_head(scope, identity).content
                )
                self.assertEqual(
                    [index],
                    [item.content for item in repository.list_versions(scope, identity)],
                )

    def test_repository_rejects_or_reports_multiple_active_heads(self):
        repository = TestMemoryRepository()
        scope = MemoryScope("tenant", "user", "agent", "dept")
        identity = MemoryIdentity("customer", "a", "budget")
        first = memory_item(scope, identity, 100)
        second = memory_item(scope, identity, 120, version=2)
        repository.create_item(first)
        with self.assertRaises(MemoryInvariantViolation):
            repository.create_item(second)

        repository.items[second.id] = second
        with self.assertRaises(MemoryInvariantViolation):
            repository.find_active_head(scope, identity)

    def test_conflict_does_not_replace_active_head(self):
        repository = TestMemoryRepository()
        scope = MemoryScope("tenant", "user", "agent", "dept")
        identity = MemoryIdentity("customer", "a", "budget")
        active = memory_item(scope, identity, 100)
        conflict = memory_item(scope, identity, 80, version=2)
        conflict.status = MemoryItemStatus.CONFLICT
        repository.create_item(active)
        repository.create_item(conflict)
        self.assertEqual(active.id, repository.find_active_head(scope, identity).id)
        self.assertEqual(2, repository.get_latest_version(scope, identity))

    def test_vector_search_rejects_a_different_embedding_space(self):
        repository = TestMemoryRepository()
        scope = MemoryScope("tenant", "user", "agent", "dept")
        identity = MemoryIdentity("customer", "a", "budget")
        space_a = EmbeddingSpace("ollama", "model-a", "v1", 3)
        space_b = EmbeddingSpace("ollama", "model-b", "v2", 3)
        item = memory_item(scope, identity, "space-a")
        item.embedding = [1.0, 0.0, 0.0]
        item.embedding_space_id = space_a.space_id
        repository.create_item(item)
        request = MemoryRetrieveRequest(
            principal=MemoryPrincipal("user", "tenant", "user", "agent"),
            scope=scope, query="budget", trace_id="trace",
        )
        self.assertEqual([], repository.search_vector(
            request, [1.0, 0.0, 0.0], space_b.space_id
        ))
        self.assertEqual(1, len(repository.search_vector(
            request, [1.0, 0.0, 0.0], space_a.space_id
        )))


if __name__ == "__main__":
    unittest.main()
