from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .evaluator import benchmark_summary, evaluate_pipeline_result, format_benchmark_report, write_benchmark_report
    from .search import run_search_pipeline
except ImportError:
    from evaluator import benchmark_summary, evaluate_pipeline_result, format_benchmark_report, write_benchmark_report
    from search import run_search_pipeline


BENCHMARK_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "CE-001",
        "category": "current_events",
        "question": "Who is the current president of the United States?",
        "expected_keywords": ["president", "united states"],
    },
    {
        "id": "CE-002",
        "category": "current_events",
        "question": "What is the latest stable Python release?",
        "expected_keywords": ["python", "release"],
    },
    {
        "id": "CE-003",
        "category": "current_events",
        "question": "What is the current federal funds rate in the United States?",
        "expected_keywords": ["federal", "reserve", "rate"],
    },
    {
        "id": "CE-004",
        "category": "current_events",
        "question": "What is the latest NASA Artemis program update?",
        "expected_keywords": ["nasa", "artemis"],
    },
    {
        "id": "CE-005",
        "category": "current_events",
        "question": "What is the current Bitcoin price trend?",
        "expected_keywords": ["bitcoin", "price"],
    },
    {
        "id": "CE-006",
        "category": "current_events",
        "question": "What is the latest United States CPI inflation report?",
        "expected_keywords": ["cpi", "inflation"],
    },
    {
        "id": "CE-007",
        "category": "current_events",
        "question": "Who is the current CEO of Microsoft?",
        "expected_keywords": ["microsoft", "ceo"],
    },
    {
        "id": "CE-008",
        "category": "current_events",
        "question": "What is the latest OpenAI model announcement?",
        "expected_keywords": ["openai", "model"],
    },
    {
        "id": "SCI-001",
        "category": "science",
        "question": "What is CRISPR-Cas9 and how does it edit genes?",
        "expected_keywords": ["crispr", "cas9", "gene"],
    },
    {
        "id": "SCI-002",
        "category": "science",
        "question": "What is photosynthesis?",
        "expected_keywords": ["photosynthesis", "light", "carbon dioxide"],
    },
    {
        "id": "SCI-003",
        "category": "science",
        "question": "What is the difference between DNA and RNA?",
        "expected_keywords": ["dna", "rna"],
    },
    {
        "id": "SCI-004",
        "category": "science",
        "question": "What causes ocean tides?",
        "expected_keywords": ["moon", "gravity", "tides"],
    },
    {
        "id": "SCI-005",
        "category": "science",
        "question": "What is a black hole?",
        "expected_keywords": ["black hole", "gravity"],
    },
    {
        "id": "SCI-006",
        "category": "science",
        "question": "What is the greenhouse effect?",
        "expected_keywords": ["greenhouse", "heat", "atmosphere"],
    },
    {
        "id": "SCI-007",
        "category": "science",
        "question": "What is quantum entanglement?",
        "expected_keywords": ["quantum", "entanglement"],
    },
    {
        "id": "SCI-008",
        "category": "science",
        "question": "How do vaccines train the immune system?",
        "expected_keywords": ["vaccine", "immune", "antibodies"],
    },
    {
        "id": "SCI-009",
        "category": "science",
        "question": "What is plate tectonics?",
        "expected_keywords": ["plate", "tectonics"],
    },
    {
        "id": "HIS-001",
        "category": "history",
        "question": "What caused World War I?",
        "expected_keywords": ["world war", "alliance", "assassination"],
    },
    {
        "id": "HIS-002",
        "category": "history",
        "question": "When did the Roman Empire fall in the West?",
        "expected_keywords": ["476", "roman"],
    },
    {
        "id": "HIS-003",
        "category": "history",
        "question": "What was the Industrial Revolution?",
        "expected_keywords": ["industrial", "manufacturing"],
    },
    {
        "id": "HIS-004",
        "category": "history",
        "question": "Who was Mahatma Gandhi?",
        "expected_keywords": ["gandhi", "india"],
    },
    {
        "id": "HIS-005",
        "category": "history",
        "question": "What was the Cold War?",
        "expected_keywords": ["cold war", "united states", "soviet"],
    },
    {
        "id": "HIS-006",
        "category": "history",
        "question": "Why was the Magna Carta important?",
        "expected_keywords": ["magna carta", "king", "rights"],
    },
    {
        "id": "HIS-007",
        "category": "history",
        "question": "What was the Renaissance?",
        "expected_keywords": ["renaissance", "art", "europe"],
    },
    {
        "id": "HIS-008",
        "category": "history",
        "question": "What happened during the American Civil War?",
        "expected_keywords": ["civil war", "union", "confederacy"],
    },
    {
        "id": "TECH-001",
        "category": "technology",
        "question": "What is Kubernetes used for?",
        "expected_keywords": ["kubernetes", "containers"],
    },
    {
        "id": "TECH-002",
        "category": "technology",
        "question": "What is the difference between HTTP and HTTPS?",
        "expected_keywords": ["http", "https", "encryption"],
    },
    {
        "id": "TECH-003",
        "category": "technology",
        "question": "What is a vector database?",
        "expected_keywords": ["vector", "embedding", "search"],
    },
    {
        "id": "TECH-004",
        "category": "technology",
        "question": "What is retrieval augmented generation?",
        "expected_keywords": ["retrieval", "generation", "sources"],
    },
    {
        "id": "TECH-005",
        "category": "technology",
        "question": "What is a circuit breaker pattern in software architecture?",
        "expected_keywords": ["circuit breaker", "failure", "service"],
    },
    {
        "id": "TECH-006",
        "category": "technology",
        "question": "What is zero trust security?",
        "expected_keywords": ["zero trust", "security", "verify"],
    },
    {
        "id": "TECH-007",
        "category": "technology",
        "question": "What is observability in distributed systems?",
        "expected_keywords": ["observability", "logs", "metrics", "traces"],
    },
    {
        "id": "TECH-008",
        "category": "technology",
        "question": "What is model drift in machine learning?",
        "expected_keywords": ["model drift", "data", "performance"],
    },
    {
        "id": "TECH-009",
        "category": "technology",
        "question": "What is an API gateway?",
        "expected_keywords": ["api gateway", "routing", "authentication"],
    },
    {
        "id": "CODE-001",
        "category": "coding",
        "question": "How do Python context managers work?",
        "expected_keywords": ["python", "context manager", "__enter__", "__exit__"],
    },
    {
        "id": "CODE-002",
        "category": "coding",
        "question": "What is Big O notation?",
        "expected_keywords": ["big o", "complexity"],
    },
    {
        "id": "CODE-003",
        "category": "coding",
        "question": "What is the difference between a list and a tuple in Python?",
        "expected_keywords": ["list", "tuple", "mutable"],
    },
    {
        "id": "CODE-004",
        "category": "coding",
        "question": "How does async await work in JavaScript?",
        "expected_keywords": ["async", "await", "promise"],
    },
    {
        "id": "CODE-005",
        "category": "coding",
        "question": "What is SQL injection and how can it be prevented?",
        "expected_keywords": ["sql injection", "parameterized", "queries"],
    },
    {
        "id": "CODE-006",
        "category": "coding",
        "question": "What is dependency injection?",
        "expected_keywords": ["dependency injection", "dependencies"],
    },
    {
        "id": "CODE-007",
        "category": "coding",
        "question": "What is unit testing?",
        "expected_keywords": ["unit testing", "test"],
    },
    {
        "id": "CODE-008",
        "category": "coding",
        "question": "What is a REST API?",
        "expected_keywords": ["rest", "api", "http"],
    },
    {
        "id": "FIN-001",
        "category": "finance",
        "question": "What is compound interest?",
        "expected_keywords": ["compound interest", "principal", "interest"],
    },
    {
        "id": "FIN-002",
        "category": "finance",
        "question": "What is an ETF?",
        "expected_keywords": ["etf", "exchange traded fund"],
    },
    {
        "id": "FIN-003",
        "category": "finance",
        "question": "What is the difference between revenue and profit?",
        "expected_keywords": ["revenue", "profit"],
    },
    {
        "id": "FIN-004",
        "category": "finance",
        "question": "What is inflation?",
        "expected_keywords": ["inflation", "prices"],
    },
    {
        "id": "FIN-005",
        "category": "finance",
        "question": "What is a balance sheet?",
        "expected_keywords": ["balance sheet", "assets", "liabilities"],
    },
    {
        "id": "FIN-006",
        "category": "finance",
        "question": "What is diversification in investing?",
        "expected_keywords": ["diversification", "risk"],
    },
    {
        "id": "FIN-007",
        "category": "finance",
        "question": "What is market capitalization?",
        "expected_keywords": ["market capitalization", "share price"],
    },
    {
        "id": "FIN-008",
        "category": "finance",
        "question": "What is a bond yield?",
        "expected_keywords": ["bond", "yield"],
    },
]


def selected_benchmark_cases(limit: Optional[int] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    cases = BENCHMARK_QUESTIONS
    if category:
        cases = [case for case in cases if case["category"] == category]
    if limit:
        cases = cases[: max(1, int(limit))]
    return [dict(case) for case in cases]


def run_benchmark(
    limit: Optional[int] = None,
    category: Optional[str] = None,
    max_sources: int = 5,
    crawl_timeout: int = 4,
) -> Dict[str, Any]:
    evaluated_results: List[Dict[str, Any]] = []
    cases = selected_benchmark_cases(limit=limit, category=category)

    for case in cases:
        result = run_search_pipeline(
            case["question"],
            max_sources=max_sources,
            llm_client=None,
            crawl_timeout=crawl_timeout,
        )
        metrics = evaluate_pipeline_result(result, case)
        evaluated_results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected_keywords": case.get("expected_keywords", []),
                "answer": result.get("answer", ""),
                "duration_seconds": result.get("duration_seconds", 0),
                "confidence_score": result.get("confidence_score", 0),
                "metrics": metrics,
                "source_count": len(result.get("sources", [])),
                "sources_used_count": len(result.get("sources_used", [])),
                "conflict": result.get("verification", {}).get("conflict", {}),
            }
        )

    summary = benchmark_summary(evaluated_results)
    report_paths = write_benchmark_report(Path(__file__).resolve().parent / "nexora_data" / "reports", summary, evaluated_results)
    return {
        "summary": summary,
        "results": evaluated_results,
        "reports": report_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Nexora evaluation benchmark.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of questions for a quick smoke run.")
    parser.add_argument("--category", default=None, help="Run only one benchmark category.")
    parser.add_argument("--max-sources", type=int, default=5, help="Sources per question, from 5 to 10.")
    parser.add_argument("--crawl-timeout", type=int, default=4, help="Seconds to wait per source fetch.")
    args = parser.parse_args()

    benchmark = run_benchmark(
        limit=args.limit,
        category=args.category,
        max_sources=args.max_sources,
        crawl_timeout=args.crawl_timeout,
    )
    print(format_benchmark_report(benchmark["summary"], benchmark["results"]))
    print("")
    print(f"JSON report: {benchmark['reports']['json_report']}")
    print(f"Text report: {benchmark['reports']['text_report']}")


if __name__ == "__main__":
    main()
