from uuid import uuid4

from api.schemas.ai import ProviderAIChatResponse
from api.services.ai.chat import AIChatContextBundle, answer_interactive_question


class FakeQuestionProvider:
    def answer_question(
        self, context: dict[str, object], question: str, language: str = "en"
    ) -> ProviderAIChatResponse:
        return ProviderAIChatResponse(
            answer="Explanação baseada na evidência.",
            uncertainties=[],
            referenced_finding_refs=["finding_1"],
        )


def test_answer_interactive_question_materializes_references() -> None:
    finding_id = uuid4()
    bundle = AIChatContextBundle(
        provider_context={"scope": "scan", "top_findings": []},
        finding_ids_by_ref={"finding_1": finding_id},
        display_values_by_ref={"finding_1": "OpenSSH issue"},
    )

    response = answer_interactive_question(
        FakeQuestionProvider(),
        bundle,
        question="O que devo corrigir primeiro?",
    )

    assert response.referenced_finding_ids == [finding_id]
