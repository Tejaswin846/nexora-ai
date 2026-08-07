from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from .citation import citation_ids_in_answer
    from .verifier import CONFLICT_MESSAGE, verification_summary
except ImportError:
    from citation import citation_ids_in_answer
    from verifier import CONFLICT_MESSAGE, verification_summary


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def average(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def evaluate_search_quality(sources: List[Dict[str, Any]], rejected_sources: Optional[List[Dict[str, Any]]] = None) -> int:
    rejected_sources = rejected_sources or []
    if not sources:
        return 0

    source_count_score = min(len(sources), 5) / 5 * 30
    avg_quality = average(float(source.get("quality_score", 50) or 0) for source in sources)
    trusted_count = sum(
        1
        for source in sources
        if source.get("trust_tier") in {"official", "research", "documentation", "trusted_news"}
    )
    trusted_score = min(trusted_count, 3) / 3 * 20
    avg_relevance = average(float(source.get("relevance_score", source.get("score", 0)) or 0) for source in sources)
    relevance_score = min(avg_relevance, 100) * 0.2
    rejection_penalty = min(len(rejected_sources), 5) * 2

    return clamp_score(source_count_score + avg_quality * 0.35 + trusted_score + relevance_score - rejection_penalty)


def evaluate_citation_quality(answer: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    cited_ids = citation_ids_in_answer(answer)
    available_ids = {str(source.get("citation_id")) for source in sources if source.get("citation_id")}
    valid_ids = [citation_id for citation_id in cited_ids if citation_id in available_ids]
    invalid_ids = [citation_id for citation_id in cited_ids if citation_id not in available_ids]

    answer_units = [
        unit
        for unit in re.split(r"(?<=[.!?])\s+|\n+", clean_text(answer))
        if len(unit.strip()) >= 30
    ]
    cited_units = [unit for unit in answer_units if re.search(r"\[S\d+\]", unit)]
    unit_coverage = len(cited_units) / len(answer_units) if answer_units else 0.0
    source_coverage = len(set(valid_ids)) / len(sources) if sources else 0.0
    valid_ratio = len(valid_ids) / len(cited_ids) if cited_ids else 0.0

    score = (
        min(len(set(valid_ids)), 3) / 3 * 35
        + unit_coverage * 35
        + source_coverage * 20
        + valid_ratio * 10
        - min(len(invalid_ids), 5) * 8
    )
    return {
        "score": clamp_score(score),
        "cited_source_ids": valid_ids,
        "invalid_citation_ids": invalid_ids,
        "citation_coverage_percent": round(unit_coverage * 100, 2),
        "source_coverage_percent": round(source_coverage * 100, 2),
    }


def evaluate_response_accuracy(
    answer: str,
    sources: List[Dict[str, Any]],
    benchmark_case: Optional[Dict[str, Any]] = None,
    conflict: Optional[Dict[str, Any]] = None,
) -> int:
    text = clean_text(answer).lower()
    benchmark_case = benchmark_case or {}
    conflict = conflict or {}
    expected_keywords = [clean_text(item).lower() for item in benchmark_case.get("expected_keywords", []) if clean_text(item)]

    if expected_keywords:
        matched = sum(1 for keyword in expected_keywords if keyword in text)
        keyword_score = matched / len(expected_keywords) * 70
    else:
        keyword_score = 45 if text else 0

    citation_score = 15 if citation_ids_in_answer(answer) else 0
    source_score = min(len(sources), 5) / 5 * 15
    conflict_penalty = 0
    if conflict.get("has_conflict") and CONFLICT_MESSAGE not in answer:
        conflict_penalty = 25
    elif conflict.get("has_conflict"):
        conflict_penalty = 8

    return clamp_score(keyword_score + citation_score + source_score - conflict_penalty)


def evaluate_response_speed(duration_seconds: float) -> int:
    try:
        duration = float(duration_seconds)
    except Exception:
        return 0
    if duration <= 5:
        return 100
    if duration <= 10:
        return 90
    if duration <= 20:
        return 75
    if duration <= 40:
        return 55
    if duration <= 75:
        return 35
    return 15


def compute_confidence_score(metrics: Dict[str, Any], conflict: Optional[Dict[str, Any]] = None) -> int:
    conflict = conflict or {}
    citation = metrics.get("citation_quality", {})
    score = (
        float(metrics.get("search_quality", 0)) * 0.25
        + float(citation.get("score", 0)) * 0.25
        + float(metrics.get("response_accuracy", 0)) * 0.35
        + float(metrics.get("response_speed", 0)) * 0.15
    )
    if conflict.get("has_conflict"):
        score -= 8
    return clamp_score(score)


def evaluate_pipeline_result(
    result: Dict[str, Any],
    benchmark_case: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    rejected_sources = result.get("rejected_sources") if isinstance(result.get("rejected_sources"), list) else []
    answer = str(result.get("answer", ""))
    query = str(result.get("query", benchmark_case.get("question", "") if benchmark_case else ""))
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else verification_summary(query, sources, rejected_sources)
    conflict = verification.get("conflict", {})

    citation_quality = evaluate_citation_quality(answer, sources)
    metrics = {
        "search_quality": evaluate_search_quality(sources, rejected_sources),
        "citation_quality": citation_quality,
        "response_accuracy": evaluate_response_accuracy(answer, sources, benchmark_case, conflict),
        "response_speed": evaluate_response_speed(float(result.get("duration_seconds", 0) or 0)),
    }
    metrics["confidence_score"] = compute_confidence_score(metrics, conflict)
    return metrics


def benchmark_summary(evaluated_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(evaluated_results)
    if not total:
        return {
            "total_questions": 0,
            "accuracy_percent": 0.0,
            "average_response_time": 0.0,
            "citation_coverage_percent": 0.0,
            "average_confidence_score": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    metrics = [item.get("metrics", {}) for item in evaluated_results]
    accuracy_values = [float(item.get("response_accuracy", 0) or 0) for item in metrics]
    citation_values = [
        float(item.get("citation_quality", {}).get("citation_coverage_percent", 0) or 0)
        for item in metrics
    ]
    confidence_values = [float(item.get("confidence_score", 0) or 0) for item in metrics]
    durations = [float(item.get("duration_seconds", 0) or 0) for item in evaluated_results]
    pass_count = sum(1 for item in metrics if float(item.get("response_accuracy", 0) or 0) >= 70)

    by_category: Dict[str, Dict[str, Any]] = {}
    for item in evaluated_results:
        category = str(item.get("category", "uncategorized"))
        bucket = by_category.setdefault(category, {"count": 0, "accuracy_values": [], "confidence_values": []})
        bucket["count"] += 1
        bucket["accuracy_values"].append(float(item.get("metrics", {}).get("response_accuracy", 0) or 0))
        bucket["confidence_values"].append(float(item.get("metrics", {}).get("confidence_score", 0) or 0))
    for bucket in by_category.values():
        bucket["average_accuracy"] = round(average(bucket.pop("accuracy_values")), 2)
        bucket["average_confidence"] = round(average(bucket.pop("confidence_values")), 2)

    return {
        "total_questions": total,
        "passed_questions": pass_count,
        "accuracy_percent": round(average(accuracy_values), 2),
        "pass_rate_percent": round(pass_count / total * 100, 2),
        "average_response_time": round(average(durations), 3),
        "citation_coverage_percent": round(average(citation_values), 2),
        "average_confidence_score": round(average(confidence_values), 2),
        "by_category": by_category,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def format_benchmark_report(summary: Dict[str, Any], evaluated_results: List[Dict[str, Any]]) -> str:
    lines = [
        "NEXORA EVALUATION BENCHMARK REPORT",
        "",
        f"Total Questions: {summary.get('total_questions', 0)}",
        f"Accuracy %: {summary.get('accuracy_percent', 0)}",
        f"Pass Rate %: {summary.get('pass_rate_percent', 0)}",
        f"Average Response Time: {summary.get('average_response_time', 0)} seconds",
        f"Citation Coverage %: {summary.get('citation_coverage_percent', 0)}",
        f"Average Confidence Score: {summary.get('average_confidence_score', 0)}",
        "",
        "CATEGORY BREAKDOWN",
    ]
    for category, bucket in sorted(summary.get("by_category", {}).items()):
        lines.append(
            f"- {category}: count={bucket.get('count', 0)}, "
            f"accuracy={bucket.get('average_accuracy', 0)}, "
            f"confidence={bucket.get('average_confidence', 0)}"
        )

    lines.extend(["", "QUESTION RESULTS"])
    for item in evaluated_results:
        metrics = item.get("metrics", {})
        lines.append(
            f"- {item.get('id')}: {item.get('category')} | "
            f"confidence={metrics.get('confidence_score', 0)} | "
            f"accuracy={metrics.get('response_accuracy', 0)} | "
            f"time={item.get('duration_seconds', 0)}s | "
            f"question={item.get('question', '')}"
        )
    return "\n".join(lines)


def write_benchmark_report(
    output_dir: Path,
    summary: Dict[str, Any],
    evaluated_results: List[Dict[str, Any]],
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evaluation_benchmark_report.json"
    text_path = output_dir / "evaluation_benchmark_report.txt"
    json_path.write_text(
        json.dumps({"summary": summary, "results": evaluated_results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    text_path.write_text(format_benchmark_report(summary, evaluated_results), encoding="utf-8")
    return {"json_report": str(json_path), "text_report": str(text_path)}
