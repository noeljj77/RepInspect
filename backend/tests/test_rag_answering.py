from types import SimpleNamespace

from app.services.ai.grounding import Grounding
from app.services.ai.schemas import RawCitation
from app.services.rag.answering import ground_answer, renumber_markers, strip_markers
from app.services.rag.chat_jobs import history_and_question, search_text
from app.services.rag.schemas import RawChatAnswer

FILES = {
    "app/auth.py": "import argon2\n\ndef verify_password(plain, stored):\n    return argon2.verify(stored, plain)\n",
    "app/orders.py": "def cancel(order):\n    raise ValueError('already shipped')\n",
}


def grounding() -> Grounding:
    return Grounding(FILES, FILES.get)


def cite(path, quote, start=1):
    return RawCitation(path=path, start_line=start, end_line=start, quote=quote)


def test_markers_are_renumbered_and_unknown_ones_removed():
    text = "Hashes are checked [1]. Orders cannot be cancelled [2, 3]. Unsupported [4]."

    assert (
        renumber_markers(text, {1: 1, 2: 2, 3: 2})
        == "Hashes are checked [1]. Orders cannot be cancelled [2]. Unsupported."
    )


def test_markers_can_be_stripped_for_conversation_history():
    assert strip_markers("It hashes [1] and checks [2, 3].") == "It hashes and checks."


def test_only_quotes_found_in_the_code_survive_with_their_real_lines():
    raw = RawChatAnswer(
        answerable=True,
        answer="Passwords are verified with argon2 [1]. It also emails the admin [2]. Again [3].",
        citations=[
            cite("app/auth.py", "return argon2.verify(stored, plain)", start=1),  # really line 4
            cite("app/auth.py", "send_email(admin)"),  # invented
            cite("auth.py", "return argon2.verify(stored, plain)"),  # same place, short path
        ],
    )

    answer = ground_answer(raw, grounding(), sources=[])

    assert [(c.path, c.start_line) for c in answer.citations] == [("app/auth.py", 4)]
    assert (
        answer.answer
        == "Passwords are verified with argon2 [1]. It also emails the admin. Again [1]."
    )
    assert answer.removed_citations == 1


def test_files_the_answer_invents_are_listed():
    raw = RawChatAnswer(
        answerable=True, answer="Settings live in config/settings.py.", citations=[]
    )

    assert ground_answer(raw, grounding(), sources=[]).ungrounded_paths == ["config/settings.py"]


def message(position, role, content, status="completed"):
    return SimpleNamespace(position=position, role=role, content=content, status=status)


def test_history_keeps_only_finished_turns_before_the_question():
    messages = [
        message(1, "user", "What does auth do?"),
        message(2, "assistant", "It checks passwords [1]."),
        message(3, "user", "And orders?"),
        message(4, "assistant", "", status="failed"),
        message(5, "user", "Where is cancel?"),
        message(6, "assistant", "", status="pending"),
    ]

    history, question = history_and_question(messages, messages[-1], turns=3)

    assert question == "Where is cancel?"
    assert history == [("What does auth do?", "It checks passwords.")]
    assert history_and_question(messages, messages[-1], turns=0)[0] == []


def test_short_follow_up_questions_are_searched_with_the_previous_question():
    history = [("How are passwords checked?", "With argon2.")]

    assert search_text("and where is it called?", history) == (
        "How are passwords checked? and where is it called?"
    )
    long_question = "Which function cancels an order that has not been shipped yet?"
    assert search_text(long_question, history) == long_question
    assert search_text("why?", []) == "why?"
