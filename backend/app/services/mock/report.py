"""The end-of-interview report, computed from the graded turns.

No extra AI call: the report only gathers what the grades already say, so it cannot
contradict them, cannot fail, and costs nothing from the daily allowance.
"""

from collections import Counter, defaultdict

from app.models import MockTurn, TurnStatus
from app.services.interview.schemas import CATEGORIES

MAX_LISTED = 6


def build_report(turns: list[MockTurn]) -> dict:
    scored = [t for t in turns if t.status in (TurnStatus.GRADED, TurnStatus.SKIPPED)]
    questions = [t for t in scored if t.kind == "question"]
    follow_ups = [t for t in scored if t.kind == "follow_up"]

    def average(items: list[MockTurn]) -> float | None:
        return round(sum(t.score or 0 for t in items) / len(items), 2) if items else None

    by_category: dict[str, list[MockTurn]] = defaultdict(list)
    for turn in questions:
        by_category[turn.category].append(turn)

    strengths: list[str] = []
    gaps: list[str] = []
    contradicted: list[dict] = []
    files: Counter[str] = Counter()
    for turn in scored:
        grade = turn.grade or {}
        strengths += [s for s in grade.get("strengths", []) if s not in strengths]
        gaps += [g for g in grade.get("gaps", []) if g not in gaps]
        for claim in grade.get("claims", []):
            if claim["verdict"] == "contradicted":
                contradicted.append(claim)
                files.update(c["path"] for c in claim["citations"])
        for point in grade.get("missed_points", []):
            files.update(c["path"] for c in point.get("citations", []))

    overall = average(questions)
    return {
        "questions_answered": len(questions),
        "skipped": sum(1 for t in questions if t.status == TurnStatus.SKIPPED),
        "follow_ups_answered": len(follow_ups),
        "average_score": overall,  # 0 to 4
        "percent": round(overall / 4 * 100) if overall is not None else None,
        "follow_up_average": average(follow_ups),
        "by_category": [
            {
                "category": key,
                "label": CATEGORIES.get(key, key),
                "average": average(items),
                "count": len(items),
            }
            for key, items in sorted(by_category.items(), key=lambda kv: average(kv[1]) or 0)
        ],
        "strengths": strengths[:MAX_LISTED],
        "gaps": gaps[:MAX_LISTED],
        "contradicted_claims": contradicted[:MAX_LISTED],
        # Files behind missed points and contradicted claims: where to read up first.
        "files_to_review": [path for path, _ in files.most_common(MAX_LISTED)],
    }
