from uuid import uuid4

from api.schemas.ai import ProviderAIChatResponse
from api.services.ai.orchestrator import AIOrchestrator


class FakeQuestionProvider:
    def __init__(self) -> None:
        self.context: dict[str, object] | None = None
        self.question: str | None = None

    def answer_question(
        self, context: dict[str, object], question: str, language: str = "en"
    ) -> ProviderAIChatResponse:
        self.context = context
        self.question = question
        return ProviderAIChatResponse(
            answer="Explanação baseada na evidência.",
            uncertainties=[],
            referenced_finding_refs=["finding_1"],
        )


def test_orchestrator_delegates_and_materializes_references() -> None:
    provider = FakeQuestionProvider()
    finding_id = uuid4()

    response = AIOrchestrator(provider).answer_question(
        context={"scan": {"finding_count": 1}},
        question="O que devo corrigir primeiro?",
        finding_references={"finding_1": finding_id},
    )

    assert provider.question == "O que devo corrigir primeiro?"
    assert provider.context == {"scan": {"finding_count": 1}}
    assert response.referenced_finding_ids == [finding_id]

