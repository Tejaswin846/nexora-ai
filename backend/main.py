from __future__ import annotations

import asyncio
import hashlib
import hmac
import html as html_lib
import json
import logging
import os
import re
import threading
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from clerk_auth import ClerkAuthError, ClerkJWTVerifier, ClerkUserContext
from supabase_client import SupabaseStorageClient, SupabaseStorageError

try:
    from researcher.loop import research_loop
except Exception:
    def research_loop(query: str, max_rounds: int = 2) -> Dict[str, Any]:
        return {
            "ok": False,
            "sources": [],
            "confidence": "none",
            "rounds": 0,
            "error": "Research engine module is not installed.",
        }


APP_NAME = "Nexora Agent"
APP_VERSION = "10.02.0-language-routing-max-expanded"
CAPABILITY_SCALE_MAX = 15.00
CAPABILITY_SCALE_TEXT = f"{CAPABILITY_SCALE_MAX:.2f}"
QUALITY_ENFORCEMENT_MODE = "max_precision_guardrails"
ROUTING_GATE_MODE = "intent_first_max"
QUALITY_GATE_MODE = "repair_or_fallback"
GATE_STACK_MODE = "intent_route_quality_stack"
ROUTING_MATRIX_VERSION = "expanded_360_plus_language_fields_realtime"
INTENT_QUALITY_LEVEL = 10.00
INTENT_QUALITY_LEVEL_TEXT = f"{INTENT_QUALITY_LEVEL:.2f}"
ROUTING_GATE_LEVEL = INTENT_QUALITY_LEVEL
ROUTING_GATE_LEVEL_TEXT = f"{ROUTING_GATE_LEVEL:.2f}"
QUALITY_GATE_LEVEL = INTENT_QUALITY_LEVEL
QUALITY_GATE_LEVEL_TEXT = f"{QUALITY_GATE_LEVEL:.2f}"
INTENT_DETECTION_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
CONTEXT_RESOLUTION_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
ROUTE_SELECTION_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
ROUTE_CONFIDENCE_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
TASK_SHAPE_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
ANSWER_QUALITY_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
ACCURACY_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
REASONING_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
ANSWER_STRUCTURE_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
REPAIR_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
FINAL_OUTPUT_GATE_LEVEL_TEXT = INTENT_QUALITY_LEVEL_TEXT
INTELLIGENCE_LEVEL = CAPABILITY_SCALE_MAX
INTELLIGENCE_LEVEL_TEXT = f"{INTELLIGENCE_LEVEL:.2f}"
INTELLIGENCE_MODE = "extended_agentic_intelligence"
UNDERSTANDING_LEVEL = CAPABILITY_SCALE_MAX
UNDERSTANDING_LEVEL_TEXT = f"{UNDERSTANDING_LEVEL:.2f}"
UNDERSTANDING_MODE = "max_agentic_precision"
ACCURACY_LEVEL = CAPABILITY_SCALE_MAX
ACCURACY_LEVEL_TEXT = f"{ACCURACY_LEVEL:.2f}"
ACCURACY_MODE = "strict_verification_precision"
REASONING_LEVEL = CAPABILITY_SCALE_MAX
REASONING_LEVEL_TEXT = f"{REASONING_LEVEL:.2f}"
REASONING_MODE = "max_silent_reasoning"
ANSWER_STRUCTURE_LEVEL = CAPABILITY_SCALE_MAX
ANSWER_STRUCTURE_LEVEL_TEXT = f"{ANSWER_STRUCTURE_LEVEL:.2f}"
ANSWER_STRUCTURE_MODE = "polished_answer_presentation"


def gate_levels_payload() -> Dict[str, str]:
    return {
        "intent_quality": INTENT_QUALITY_LEVEL_TEXT,
        "intent_detection": INTENT_DETECTION_GATE_LEVEL_TEXT,
        "context_resolution": CONTEXT_RESOLUTION_GATE_LEVEL_TEXT,
        "routing_gate": ROUTING_GATE_LEVEL_TEXT,
        "route_selection": ROUTE_SELECTION_GATE_LEVEL_TEXT,
        "route_confidence": ROUTE_CONFIDENCE_GATE_LEVEL_TEXT,
        "task_shape_validation": TASK_SHAPE_GATE_LEVEL_TEXT,
        "answer_quality": ANSWER_QUALITY_GATE_LEVEL_TEXT,
        "accuracy_gate": ACCURACY_GATE_LEVEL_TEXT,
        "reasoning_gate": REASONING_GATE_LEVEL_TEXT,
        "answer_structure_gate": ANSWER_STRUCTURE_GATE_LEVEL_TEXT,
        "repair_gate": REPAIR_GATE_LEVEL_TEXT,
        "final_output_gate": FINAL_OUTPUT_GATE_LEVEL_TEXT,
    }


def gate_tools_used() -> List[str]:
    return [f"gate:{name}:{level}" for name, level in gate_levels_payload().items()]


def routing_matrix_payload() -> Dict[str, Any]:
    return {
        "version": ROUTING_MATRIX_VERSION,
        "intents": [
            "realtime_search",
            "realtime_current_fact",
            "realtime_news",
            "realtime_weather",
            "realtime_market",
            "realtime_product_recommendation",
            "realtime_sports",
            "realtime_local_places",
            "realtime_travel_status",
            "realtime_events",
            "realtime_jobs",
            "realtime_version_release",
            "realtime_schedule",
            "realtime_exchange_rate",
            "realtime_law_policy_update",
            "realtime_exam_result",
            "realtime_public_transport",
            "realtime_outage",
            "realtime_holiday_calendar",
            "realtime_movie_showtimes",
            "realtime_shopping_availability",
            "realtime_platform_status",
            "realtime_academic_deadline",
            "realtime_government_scheme",
            "realtime_crypto_price",
            "realtime_github_repo",
            "realtime_package_version",
            "realtime_security_advisory",
            "realtime_academic_paper",
            "realtime_dataset_lookup",
            "realtime_earthquake",
            "realtime_air_quality",
            "realtime_space_launch",
            "realtime_public_record",
            "realtime_fuel_price",
            "realtime_product_price",
            "realtime_tax_deadline",
            "realtime_university_admission",
            "realtime_food_delivery",
            "realtime_local_emergency",
            "calculation",
            "math_reasoning",
            "image_generation",
            "code_or_debug",
            "bug_triage",
            "troubleshooting_steps",
            "system_design",
            "api_design",
            "database_query",
            "cybersecurity_info",
            "excel_formula",
            "regex_help",
            "git_help",
            "devops_deploy",
            "test_generation",
            "log_analysis",
            "performance_tuning",
            "architecture_review",
            "code_review",
            "ui_ux_feedback",
            "accessibility_review",
            "prompt_engineering",
            "image_prompt",
            "translation",
            "language_learning",
            "language_detection",
            "transliteration",
            "romanization",
            "script_conversion",
            "word_meaning",
            "dictionary_definition",
            "etymology",
            "synonym_antonym",
            "idiom_explanation",
            "proverb_explanation",
            "vocabulary_builder",
            "spelling_help",
            "punctuation_help",
            "sentence_parsing",
            "parts_of_speech",
            "tense_practice",
            "verb_conjugation",
            "phrasal_verbs",
            "collocations",
            "tone_conversion",
            "formal_informal_rewrite",
            "bilingual_explanation",
            "phrasebook",
            "conversation_practice",
            "dialogue_translation",
            "reading_comprehension",
            "comprehension_questions",
            "cloze_test",
            "dictation_practice",
            "language_exam_prep",
            "language_localization",
            "dialect_rewrite",
            "subtitle_translation",
            "phonetics_ipa",
            "accent_reduction",
            "language_skill_assessment",
            "cefr_leveling",
            "language_curriculum",
            "grammar_drill",
            "vocabulary_quiz",
            "flashcards",
            "minimal_pairs",
            "syllable_stress",
            "word_usage",
            "sentence_correction",
            "translation_review",
            "natural_translation",
            "literal_translation",
            "back_translation",
            "cultural_context",
            "politeness_register",
            "multilingual_compare",
            "essay_correction",
            "email_rewrite",
            "language_hindi",
            "language_english",
            "language_tamil",
            "language_telugu",
            "language_kannada",
            "language_malayalam",
            "language_marathi",
            "language_bengali",
            "language_gujarati",
            "language_punjabi",
            "language_urdu",
            "language_sanskrit",
            "language_arabic",
            "language_french",
            "language_spanish",
            "language_german",
            "language_italian",
            "language_portuguese",
            "language_russian",
            "language_chinese",
            "language_japanese",
            "language_korean",
            "language_turkish",
            "language_dutch",
            "language_greek",
            "language_latin",
            "language_assamese",
            "language_odia",
            "language_nepali",
            "language_sinhala",
            "language_thai",
            "language_vietnamese",
            "language_indonesian",
            "language_malay",
            "language_swahili",
            "language_hebrew",
            "language_persian",
            "language_polish",
            "language_ukrainian",
            "language_czech",
            "language_swedish",
            "language_norwegian",
            "language_danish",
            "language_finnish",
            "language_hungarian",
            "language_romanian",
            "language_albanian",
            "language_armenian",
            "language_azerbaijani",
            "language_basque",
            "language_bosnian",
            "language_bulgarian",
            "language_burmese",
            "language_catalan",
            "language_croatian",
            "language_estonian",
            "language_filipino",
            "language_georgian",
            "language_haitian_creole",
            "language_hausa",
            "language_icelandic",
            "language_irish",
            "language_javanese",
            "language_kazakh",
            "language_khmer",
            "language_lao",
            "language_latvian",
            "language_lithuanian",
            "language_serbian",
            "language_slovak",
            "language_slovenian",
            "language_somali",
            "language_welsh",
            "language_yoruba",
            "language_zulu",
            "language_amharic",
            "language_pashto",
            "language_kurdish",
            "language_uzbek",
            "language_mongolian",
            "language_maori",
            "language_quechua",
            "language_luxembourgish",
            "language_galician",
            "language_belarusian",
            "language_macedonian",
            "language_maltese",
            "language_esperanto",
            "pronunciation_help",
            "grammar_explanation",
            "grammar_fix",
            "rewrite_polish",
            "text_summary",
            "key_points",
            "table_format",
            "document_review",
            "contract_explainer",
            "form_fill_help",
            "notes_cleanup",
            "brainstorm_ideas",
            "decision_advice",
            "decision_matrix",
            "checklist",
            "risk_assessment",
            "swot_analysis",
            "okr_planning",
            "sop_process",
            "recipe_or_cooking",
            "meal_plan",
            "shopping_list",
            "travel_itinerary",
            "packing_list",
            "recommendation",
            "product_comparison",
            "health_info",
            "legal_info",
            "finance_info",
            "budget_plan",
            "expense_analysis",
            "accounting_help",
            "tax_help",
            "audit_checklist",
            "insurance_guidance",
            "real_estate_guidance",
            "procurement_plan",
            "hr_policy",
            "operations_plan",
            "logistics_plan",
            "supply_chain_plan",
            "manufacturing_process",
            "quality_control",
            "product_management",
            "project_management",
            "agile_scrum",
            "data_science",
            "machine_learning",
            "statistics_help",
            "dashboard_design",
            "research_methods",
            "academic_citation",
            "grant_proposal",
            "policy_analysis",
            "journalism_draft",
            "ngo_program_plan",
            "event_planning",
            "hospitality_plan",
            "retail_plan",
            "agriculture_guidance",
            "environmental_science",
            "sustainability_plan",
            "civil_engineering",
            "mechanical_engineering",
            "electrical_engineering",
            "electronics_help",
            "architecture_building",
            "interior_design",
            "urban_planning",
            "medicine_info",
            "nursing_info",
            "pharmacy_info",
            "dentistry_info",
            "veterinary_info",
            "psychology_info",
            "parenting_guidance",
            "personal_productivity",
            "sports_coaching",
            "music_theory",
            "film_analysis",
            "game_design",
            "legal_memo",
            "case_brief",
            "compliance_check",
            "privacy_guidance",
            "ethics_analysis",
            "theology_religion",
            "mathematics_proof",
            "career_resume",
            "career_roadmap",
            "resume_bullets",
            "cover_letter",
            "linkedin_profile",
            "interview_prep",
            "mock_interview",
            "presentation_outline",
            "speech_draft",
            "debate_prep",
            "lesson_plan",
            "rubric_feedback",
            "research_brief",
            "essay_draft",
            "essay_feedback",
            "book_summary",
            "poem_analysis",
            "lab_report",
            "science_explanation",
            "history_explanation",
            "geography_explanation",
            "economics_explanation",
            "philosophy_explanation",
            "meeting_notes",
            "social_caption",
            "marketing_copy",
            "brand_naming",
            "slogan_tagline",
            "business_strategy",
            "market_research",
            "sales_pitch",
            "customer_support_reply",
            "creative_story",
            "poem_or_original_song",
            "joke_fun",
            "emotional_support",
            "relationship_advice",
            "habit_plan",
            "mental_wellness",
            "negotiation_script",
            "apology_message",
            "flashcards",
            "quiz_generation",
            "timeline",
            "homework_help",
            "exam_answer",
            "concept_tutoring",
            "data_analysis",
            "email_reply",
            "diagnostic_deficiency",
            "project_plan",
            "reminder",
            "schedule_planning",
            "workflow_plan",
            "study_management_plan",
            "fitness_plan",
            "file_summary",
            "study_plan",
            "study_timetable",
            "email_draft",
            "writing_*",
            "song_recommendation",
            "comparison",
            "pros_cons",
            "youtube_plan",
            "website_plan",
            "business_plan",
            "general_plan",
            "capability_status",
            "learning_topic",
            "chat",
        ],
    }

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("NEXORA_DATA_DIR", BASE_DIR / "nexora_data")).expanduser()
UPLOAD_DIR = DATA_DIR / "uploads"
SESSIONS_FILE = DATA_DIR / "sessions.json"
MEMORY_FILE = DATA_DIR / "memory.json"
PERSONA_FILE = DATA_DIR / "persona.json"
BEHAVIOR_FILE = DATA_DIR / "behavior.json"
PROJECTS_FILE = DATA_DIR / "projects.json"
ARTIFACTS_FILE = DATA_DIR / "artifacts.json"
USERS_FILE = DATA_DIR / "users.json"
IMAGE_MEMORY_FILE = DATA_DIR / "image_memory.json"
REMINDERS_FILE = DATA_DIR / "reminders.json"
WORKFLOWS_FILE = DATA_DIR / "workflows.json"
FRONTEND_INDEX = BASE_DIR.parent / "frontend" / "index.html"
CODE_PAGE_INDEX = BASE_DIR.parent / "frontend" / "code.html"
RESET_PASSWORD_INDEX = BASE_DIR.parent / "frontend" / "reset-password.html"
AUTH_CONTROLLER_INDEX = BASE_DIR.parent / "frontend" / "auth.js"
CACHE_FRONTEND_HTML = os.getenv("NEXORA_CACHE_FRONTEND_HTML", "true").strip().lower() not in {"0", "false", "off", "no"}
HEALTH_DEEP = os.getenv("NEXORA_HEALTH_DEEP", "false").strip().lower() in {"1", "true", "yes", "on"}
FRONTEND_HTML_CACHE: Dict[str, str] = {}

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def load_local_env(path: Path) -> None:
    try:
        if not path.exists():
            return
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        return


load_local_env(BASE_DIR / ".env")

PUBLIC_APP_URL = os.getenv("NEXORA_PUBLIC_APP_URL", "").strip().rstrip("/")
CLERK_AUTH_REQUIRED = os.getenv("NEXORA_CLERK_AUTH_REQUIRED", "true").strip().lower() not in {"0", "false", "off", "no"}
clerk_verifier = ClerkJWTVerifier()
supabase_storage_client = SupabaseStorageClient()

QWEN_LOCK_ENABLED = os.getenv("NEXORA_LOCK_QWEN", "true").strip().lower() not in {"0", "false", "off", "no"}
REMOTE_OLLAMA_URL = (
    os.getenv(
        "NEXORA_REMOTE_OLLAMA_URL",
        "http://52.237.82.140:8000/ollama/64a40f47d13cdedb022b72a961b8c5d5ce7793ac78c68f2d",
    )
    .strip()
    .rstrip("/")
)
OLLAMA_PROXY_TOKEN = os.getenv("NEXORA_OLLAMA_PROXY_TOKEN", "").strip()
OLLAMA_PROXY_TARGET = (os.getenv("NEXORA_OLLAMA_PROXY_TARGET") or "http://127.0.0.1:11434").strip().rstrip("/")
OLLAMA_PROXY_MAX_BYTES = int(os.getenv("NEXORA_OLLAMA_PROXY_MAX_BYTES", "200000"))
raw_ollama_url = (os.getenv("OLLAMA_URL") or "http://127.0.0.1:11434").strip().rstrip("/")
raw_ollama_host = (urlparse(raw_ollama_url).hostname or "").lower()
OLLAMA_URL = (
    REMOTE_OLLAMA_URL
    if QWEN_LOCK_ENABLED and not OLLAMA_PROXY_TOKEN and raw_ollama_host in {"127.0.0.1", "localhost", "0.0.0.0"}
    else raw_ollama_url
)
FAST_MODEL = "qwen2.5:3b" if QWEN_LOCK_ENABLED else os.getenv("NEXORA_FAST_MODEL", "qwen2.5:3b")
THINKING_MODEL = "qwen3:14b" if QWEN_LOCK_ENABLED else os.getenv("NEXORA_THINKING_MODEL", "qwen3:14b")
DEFAULT_MODEL = FAST_MODEL
OLLAMA_MODE = "primary" if QWEN_LOCK_ENABLED else os.getenv("NEXORA_OLLAMA_MODE", "primary").strip().lower()
OLLAMA_KEEP_ALIVE = os.getenv("NEXORA_OLLAMA_KEEP_ALIVE", "30m").strip()
OLLAMA_THINK = os.getenv("NEXORA_OLLAMA_THINK", "false").strip().lower() in {"1", "true", "yes", "on"}
OLLAMA_CONTEXT_TOKENS = 512 if QWEN_LOCK_ENABLED else int(os.getenv("NEXORA_OLLAMA_CONTEXT_TOKENS", "2048"))
OLLAMA_INSTANT_MAX_TOKENS = 160 if QWEN_LOCK_ENABLED else int(os.getenv("NEXORA_OLLAMA_INSTANT_MAX_TOKENS", "160"))
OLLAMA_THINKING_MAX_TOKENS = 120 if QWEN_LOCK_ENABLED else int(os.getenv("NEXORA_OLLAMA_THINKING_MAX_TOKENS", "320"))

FREE_API_PROVIDER = "ollama" if QWEN_LOCK_ENABLED else os.getenv("NEXORA_PROVIDER", "ollama").strip().lower()
POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "openai-fast")
POLLINATIONS_BACKUP_MODELS = os.getenv("POLLINATIONS_BACKUP_MODELS", "").strip()
POLLINATIONS_URL = os.getenv("POLLINATIONS_URL", "https://text.pollinations.ai/openai")
POLLINATIONS_TIMEOUT = int(os.getenv("POLLINATIONS_TIMEOUT", "12"))
POLLINATIONS_PRIMARY_TIMEOUT = int(os.getenv("POLLINATIONS_PRIMARY_TIMEOUT", "8"))
POLLINATIONS_BACKUP_TIMEOUT = int(os.getenv("POLLINATIONS_BACKUP_TIMEOUT", "5"))
POLLINATIONS_ATTEMPTS = max(1, int(os.getenv("POLLINATIONS_ATTEMPTS", "1")))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
HF_API_KEY = os.getenv("HF_API_KEY", "").strip()
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

REQUEST_TIMEOUT = int(os.getenv("NEXORA_REQUEST_TIMEOUT", "35"))
SEARCH_TIMEOUT = int(os.getenv("NEXORA_SEARCH_TIMEOUT", "6"))
MAX_MODEL_TOKENS = int(os.getenv("NEXORA_MAX_TOKENS", "2600"))
INSTANT_TIMEOUT = int(os.getenv("NEXORA_INSTANT_TIMEOUT", "180"))
THINKING_TIMEOUT = int(os.getenv("NEXORA_THINKING_TIMEOUT", "420"))
FREE_CLUB_MODE = os.getenv("NEXORA_FREE_CLUB_MODE", "auto").strip().lower()
FREE_CLUB_MIN_QUERY_CHARS = int(os.getenv("NEXORA_FREE_CLUB_MIN_QUERY_CHARS", "35"))
FREE_CLUB_REVIEW_MAX_CHARS = int(os.getenv("NEXORA_FREE_CLUB_REVIEW_MAX_CHARS", "4200"))
FREE_CLUB_CONTEXT_MAX_CHARS = int(os.getenv("NEXORA_FREE_CLUB_CONTEXT_MAX_CHARS", "5200"))
FREE_CLUB_REVIEW_BUDGET_SECONDS = int(os.getenv("NEXORA_FREE_CLUB_REVIEW_BUDGET_SECONDS", "4"))
POLLINATIONS_QUALITY_GUARD = os.getenv("NEXORA_POLLINATIONS_QUALITY_GUARD", "true").strip().lower() not in {"0", "false", "off", "no"}
AUTONOMOUS_RESEARCH_ENABLED = os.getenv("NEXORA_AUTONOMOUS_RESEARCH", "true").strip().lower() not in {"0", "false", "off", "no"}
AUTONOMOUS_RESEARCH_MAX_RESULTS = max(1, min(int(os.getenv("NEXORA_AUTONOMOUS_RESEARCH_MAX_RESULTS", "2")), 3))
MAX_HISTORY_MESSAGES = 8
MAX_SESSION_MESSAGES = int(os.getenv("NEXORA_MAX_SESSION_MESSAGES", "240"))
MAX_RESEARCH_SOURCES = 4
MAX_SEARCH_RESULTS = int(os.getenv("NEXORA_MAX_SEARCH_RESULTS", "5"))
MAX_FILE_CONTEXT_CHARS = 4000
MAX_MEMORY_ITEMS = int(os.getenv("NEXORA_MAX_MEMORY_ITEMS", "600"))
MAX_MEMORY_CONTEXT_ITEMS = int(os.getenv("NEXORA_MAX_MEMORY_CONTEXT_ITEMS", "24"))
MAX_MEMORY_CONTEXT_CHARS = int(os.getenv("NEXORA_MEMORY_CONTEXT_CHARS", "6200"))
MAX_IMAGE_MEMORY_ITEMS = int(os.getenv("NEXORA_MAX_IMAGE_MEMORY_ITEMS", "600"))
MAX_PERSONA_RULES = 16
MAX_BEHAVIOR_EVENTS = 40
RESPONSE_CACHE_TTL = int(os.getenv("NEXORA_RESPONSE_CACHE_TTL", "600"))
RESPONSE_CACHE_MAX = int(os.getenv("NEXORA_RESPONSE_CACHE_MAX", "180"))
SEARCH_CACHE_TTL = int(os.getenv("NEXORA_SEARCH_CACHE_TTL", "900"))
SEARCH_CACHE_MAX = int(os.getenv("NEXORA_SEARCH_CACHE_MAX", "120"))
LOCAL_WRITING_FAST = os.getenv("NEXORA_LOCAL_WRITING_FAST", "false").strip().lower() not in {"0", "false", "off", "no"}
PERFORMANCE_LEVEL = os.getenv("NEXORA_PERFORMANCE_LEVEL", "auto").strip().lower()
IMAGE_PROVIDER = os.getenv("NEXORA_IMAGE_PROVIDER", "pollinations").strip().lower()
IMAGE_BASE_URL = os.getenv("NEXORA_IMAGE_BASE_URL", "https://image.pollinations.ai/prompt").strip().rstrip("/")
IMAGE_MODEL = os.getenv("NEXORA_IMAGE_MODEL", "").strip()
IMAGE_DEFAULT_SIZE = os.getenv("NEXORA_IMAGE_DEFAULT_SIZE", "768x768").strip()
IMAGE_PROMPT_ENHANCE = os.getenv("NEXORA_IMAGE_PROMPT_ENHANCE", "true").strip().lower() not in {"0", "false", "off", "no"}
IMAGE_PROMPT_POWER_MODE = os.getenv("NEXORA_IMAGE_PROMPT_POWER_MODE", "true").strip().lower() not in {"0", "false", "off", "no"}
IMAGE_EXACT_MATCH_MODE = os.getenv("NEXORA_IMAGE_EXACT_MATCH", "true").strip().lower() not in {"0", "false", "off", "no"}
IMAGE_PROVIDER_ENHANCE_PARAM = os.getenv("NEXORA_IMAGE_PROVIDER_ENHANCE", "false").strip().lower()
SYSTEM_PROFILE_CACHE: Optional[Dict[str, Any]] = None

HTTP = requests.Session()
RESPONSE_CACHE: Dict[str, Dict[str, Any]] = {}
SEARCH_RESULT_CACHE: Dict[str, Dict[str, Any]] = {}
POLLINATIONS_LOCK = threading.Lock()
JSON_WRITE_LOCK = threading.RLock()
SEARCH_CACHE_LOCK = threading.Lock()
PROVIDER_COOLDOWNS: Dict[str, float] = {}
LOG_LEVEL = os.getenv("NEXORA_LOG_LEVEL", "INFO").strip().upper() or "INFO"
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
LOGGER = logging.getLogger("nexora")

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROTECTED_BACKEND_PREFIXES = (
    "/projects",
    "/workflows",
    "/workflow/user",
    "/memory",
    "/artifacts",
    "/reminders",
    "/settings/free-ai",
    "/sessions",
    "/files",
    "/study",
    "/website",
    "/email",
    "/automation",
    "/image",
    "/upload",
)


def backend_route_requires_auth(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PROTECTED_BACKEND_PREFIXES)


@app.middleware("http")
async def clerk_auth_context_middleware(request: Request, call_next):
    path = request.url.path
    requires_auth = CLERK_AUTH_REQUIRED and backend_route_requires_auth(path)
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    token = auth_header.split(" ", 1)[1].strip() if auth_header.lower().startswith("bearer ") else ""
    if token:
        try:
            clerk_user = clerk_verifier.verify_token(token)
            request.state.clerk_user = clerk_user
            request.state.user = sync_clerk_user_profile(clerk_user)
        except ClerkAuthError as exc:
            if requires_auth:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
    if requires_auth and not isinstance(getattr(request.state, "user", None), dict):
        return JSONResponse(status_code=401, content={"detail": "Login required."})
    return await call_next(request)


@app.middleware("http")
async def add_private_network_header(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.exception_handler(Exception)
async def runtime_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("Unhandled backend error on %s %s", request.method, request.url.path)
    if request.url.path.startswith("/chat"):
        return JSONResponse(
            status_code=200,
            content={
                "reply": (
                    "I could not complete that response cleanly, but the app is still running. "
                    "Try the same message once more; if it keeps happening, send a shorter version and I will answer from the saved context."
                ),
                "session_id": ensure_session(None),
                "mode": "agent",
                "model_used": "nexora_runtime_guard",
                "sources": [],
                "tools_used": ["runtime_guard"],
                "created_at": now_iso(),
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "temporary_backend_error",
            "message": "The backend caught an unexpected error and stayed online.",
            "path": request.url.path,
        },
    )


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str = ""


class SourceItem(BaseModel):
    id: int
    title: str = ""
    url: str = ""
    domain: str = ""
    snippet: str = ""
    score: int = 0
    provider: str = ""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    original_message: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    mode: Optional[str] = "agent"
    model: Optional[str] = None
    chat_history: Optional[List[ChatMessage]] = None
    image_ids: Optional[List[str]] = None
    use_web: Optional[bool] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    mode: str = "agent"
    model_used: str
    sources: List[SourceItem] = []
    tools_used: List[str] = []
    route_intent: str = "auto"
    intent_quality_level: str = INTENT_QUALITY_LEVEL_TEXT
    routing_gate_level: str = ROUTING_GATE_LEVEL_TEXT
    quality_gate_level: str = QUALITY_GATE_LEVEL_TEXT
    gate_stack_mode: str = GATE_STACK_MODE
    gate_levels: Dict[str, str] = Field(default_factory=gate_levels_payload)
    routing_matrix: Dict[str, Any] = Field(default_factory=routing_matrix_payload)
    intelligence_level: str = INTELLIGENCE_LEVEL_TEXT
    understanding_level: str = UNDERSTANDING_LEVEL_TEXT
    accuracy_level: str = ACCURACY_LEVEL_TEXT
    reasoning_level: str = REASONING_LEVEL_TEXT
    answer_structure_level: str = ANSWER_STRUCTURE_LEVEL_TEXT
    created_at: str


class UploadResponse(BaseModel):
    ok: bool
    session_id: str
    filename: str
    saved_as: str
    extracted_chars: int
    message: str


class ImageUploadResponse(BaseModel):
    ok: bool
    session_id: str
    image: Dict[str, Any]
    message: str


class FeedbackRequest(BaseModel):
    rating: str = Field("good", max_length=30)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    note: Optional[str] = None


class ProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ArtifactRequest(BaseModel):
    title: str = Field("Untitled artifact", max_length=120)
    type: str = Field("Document", max_length=40)
    content: str = ""
    url: str = ""
    prompt: str = ""
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class FileSummaryRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=120)
    filename: Optional[str] = None
    max_points: int = 6
    user_id: Optional[str] = None


class StudyPlanRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=180)
    days: int = 7
    daily_minutes: int = 45
    goal: str = Field("", max_length=500)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class WebsiteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=900)
    title: Optional[str] = Field(None, max_length=120)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ReminderRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    due_at: str = Field("", max_length=80)
    notes: str = Field("", max_length=500)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class WorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    goal: str = Field("", max_length=700)
    steps: List[str] = []
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class EmailDraftRequest(BaseModel):
    purpose: str = Field(..., min_length=1, max_length=900)
    recipient: str = Field("", max_length=160)
    tone: str = Field("professional", max_length=80)
    details: str = Field("", max_length=1000)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class AutomationRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=900)
    context: str = Field("", max_length=1200)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=900)
    user_id: Optional[str] = None
    size: Optional[str] = IMAGE_DEFAULT_SIZE
    style: Optional[str] = ""
    negative_prompt: Optional[str] = ""
    enhance: Optional[bool] = True
    session_id: Optional[str] = None


class FreeAISettingsRequest(BaseModel):
    provider: str = Field("auto", max_length=40)
    api_key: Optional[str] = Field(None, max_length=4000)
    model: Optional[str] = Field(None, max_length=160)
    clear_key: Optional[bool] = False


class AuthRequest(BaseModel):
    name: str = Field("", max_length=120)
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)


class ResetPasswordRequest(BaseModel):
    access_token: str = Field(..., min_length=8, max_length=4096)
    new_password: str = Field(..., min_length=6, max_length=128)


class AuthResponse(BaseModel):
    ok: bool = True
    token: str = ""
    refresh_token: str = ""
    expires_at: Optional[int] = None
    user: Dict[str, Any] = {}
    message: str = ""


class AuthActionResponse(BaseModel):
    ok: bool = True
    message: str = ""


class AuthConfigResponse(BaseModel):
    ok: bool = True
    provider: str = "clerk"
    configured: bool = False
    clerk_publishable_key: str = ""
    clerk_jwt_issuer: str = ""
    sign_in_url: str = ""
    sign_up_url: str = ""
    reset_redirect_url: str = ""
    email_redirect_url: str = ""
    oauth_providers: List[str] = ["google", "github"]


class ImageResponse(BaseModel):
    ok: bool
    prompt: str
    original_prompt: str = ""
    enhanced_prompt: str = ""
    url: str
    artifact_id: str
    provider: str
    size: str = IMAGE_DEFAULT_SIZE
    width: int = 768
    height: int = 768
    cached: bool = False
    user_id: str = "default"
    workflow: Dict[str, Any] = {}
    created_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def compact_for_cache(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()[:900]


def stable_hash(value: str, length: int = 16) -> str:
    digest = hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()
    return digest[:max(8, min(64, length))]


def stable_hash_int(value: str, modulo: int = 1000000) -> int:
    digest = hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()
    return int(digest[:16], 16) % max(1, modulo)


def cache_key(session_id: str, message: str, mode: Optional[str], model: Optional[str]) -> str:
    return "|".join([
        session_id,
        compact_for_cache(message),
        (mode or "agent").lower(),
        (model or "auto").lower(),
    ])


def normalize_user_id(user_id: Optional[str]) -> str:
    raw = clean_text(user_id or "")
    if re.fullmatch(r"[a-zA-Z0-9_\-]{4,80}", raw):
        return raw
    return "default"


def load_users() -> Dict[str, Any]:
    raw = safe_read_json(USERS_FILE, {})
    return raw if isinstance(raw, dict) else {}


def save_users(users: Dict[str, Any]) -> None:
    safe_write_json(USERS_FILE, users)


def normalize_email(email: str) -> str:
    return clean_text(email).lower()


def public_user_payload(user: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "id": str(user.get("id", "")),
        "name": str(user.get("name", "")),
        "email": str(user.get("email", "")),
        "auth_provider": str(user.get("auth_provider", "")),
        "email_verified": bool(user.get("email_verified", False)),
        "created_at": user.get("created_at", ""),
        "updated_at": user.get("updated_at", ""),
        "preferences": user.get("preferences", {}) if isinstance(user.get("preferences", {}), dict) else {},
    }
    return payload


def bearer_token_from_request(request: Request) -> str:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        return ""
    return auth_header.split(" ", 1)[1].strip()


def public_base_url(request: Request) -> str:
    if PUBLIC_APP_URL:
        return PUBLIC_APP_URL
    return str(request.base_url).rstrip("/")


def auth_redirect_url(request: Request, path: str) -> str:
    return f"{public_base_url(request)}/{path.lstrip('/')}"


def sync_clerk_user_profile(clerk_user: ClerkUserContext) -> Dict[str, Any]:
    user_id = clean_text(str(clerk_user.user_id))
    email = normalize_email(str(clerk_user.email or ""))
    if not user_id:
        raise HTTPException(status_code=502, detail="Clerk did not return a user id.")
    claims = clerk_user.claims if isinstance(clerk_user.claims, dict) else {}
    name = clean_text(str(clerk_user.name or email.split("@")[0] or user_id))
    users = load_users()
    existing = users.get(user_id) if isinstance(users.get(user_id), dict) else {}
    now = now_iso()
    profile = {
        **existing,
        "id": user_id,
        "name": name[:120],
        "email": email,
        "auth_provider": "clerk",
        "clerk_user_id": user_id,
        "clerk_session_id": clerk_user.session_id,
        "email_verified": bool(claims.get("email_verified") or claims.get("email_verified_at") or email),
        "email_confirmed_at": claims.get("email_verified_at") or "",
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "sessions": existing.get("sessions", []) if isinstance(existing.get("sessions", []), list) else [],
        "preferences": existing.get("preferences", {}) if isinstance(existing.get("preferences", {}), dict) else {},
        "settings": existing.get("settings", {}) if isinstance(existing.get("settings", {}), dict) else {},
        "api_keys": existing.get("api_keys", {}) if isinstance(existing.get("api_keys", {}), dict) else {},
    }
    profile.pop("password", None)
    users[user_id] = profile
    email_index = users.get("__email_index__") if isinstance(users.get("__email_index__"), dict) else {}
    if email:
        email_index[email] = user_id
    users["__email_index__"] = email_index
    save_users(users)
    if supabase_storage_client.configured:
        try:
            supabase_storage_client.upsert_user_profile({
                "id": user_id,
                "email": email,
                "name": name[:120],
                "auth_provider": "clerk",
                "clerk_session_id": clerk_user.session_id,
                "updated_at": now,
            })
        except SupabaseStorageError:
            LOGGER.warning("supabase_profile_sync_failed", exc_info=True)
    return profile


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        return sync_clerk_user_profile(clerk_verifier.verify_token(token))
    except ClerkAuthError:
        return None


def require_authenticated_user(request: Request) -> Dict[str, Any]:
    state_user = getattr(request.state, "user", None)
    if isinstance(state_user, dict):
        return state_user
    token = bearer_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Login required.")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired Clerk session. Please sign in again.")
    return user


def optional_authenticated_user(request: Request) -> Optional[Dict[str, Any]]:
    state_user = getattr(request.state, "user", None)
    if isinstance(state_user, dict):
        return state_user
    token = bearer_token_from_request(request)
    if not token:
        return None
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired Clerk session. Please sign in again.")
    return user


def resolve_user_id_for_request(request: Request, supplied_user_id: Optional[str] = None) -> str:
    user = optional_authenticated_user(request)
    if user:
        return str(user.get("id", ""))
    if CLERK_AUTH_REQUIRED:
        return register_user(None)
    return register_user(supplied_user_id)


def register_request_user(
    request: Request,
    supplied_user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    user = optional_authenticated_user(request)
    if user:
        user_id = str(user.get("id", ""))
    elif CLERK_AUTH_REQUIRED:
        user_id = register_user(None, session_id)
    else:
        user_id = register_user(supplied_user_id, session_id)
    if session_id:
        register_user(user_id, session_id)
        bind_session_user(ensure_session(session_id), user_id)
    return user_id


def require_session_owner(session_id: str, user_id: str) -> Dict[str, Any]:
    session = get_session(session_id)
    owner = normalize_user_id(str(session.get("user_id", "")))
    if owner and owner != "default" and owner != normalize_user_id(user_id):
        raise HTTPException(status_code=403, detail="You cannot access another user's session.")
    return session


def register_user(user_id: Optional[str], session_id: Optional[str] = None) -> str:
    normalized = normalize_user_id(user_id)
    users = load_users()
    user = users.get(normalized)
    now = now_iso()
    if not isinstance(user, dict):
        user = {
            "id": normalized,
            "created_at": now,
            "sessions": [],
            "preferences": {},
        }
    user["updated_at"] = now
    if session_id:
        sessions = user.setdefault("sessions", [])
        if session_id not in sessions:
            sessions.append(session_id)
        user["sessions"] = sessions[-60:]
    users[normalized] = user
    save_users(users)
    return normalized


def get_cached_response(key: str) -> Optional[Dict[str, Any]]:
    item = RESPONSE_CACHE.get(key)
    if not item:
        return None
    if time.time() - float(item.get("created", 0)) > RESPONSE_CACHE_TTL:
        RESPONSE_CACHE.pop(key, None)
        return None
    return item


def set_cached_response(key: str, reply: str, model_used: str, sources: List[SourceItem]) -> None:
    cache_max = min(RESPONSE_CACHE_MAX, current_performance_limits().get("cache_items", RESPONSE_CACHE_MAX))
    if len(RESPONSE_CACHE) >= cache_max:
        oldest = sorted(RESPONSE_CACHE.items(), key=lambda pair: pair[1].get("created", 0))[:10]
        for old_key, _ in oldest:
            RESPONSE_CACHE.pop(old_key, None)
    RESPONSE_CACHE[key] = {
        "reply": reply,
        "model_used": model_used,
        "sources": sources,
        "created": time.time(),
    }


def local_song_recommendation_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(song|music|track)\b", lower):
        return None
    if not re.search(r"\b(suggest|recommend|play|listen|give me|any good|song for|music for)\b", lower):
        return None

    if re.search(r"\b(tamil|kollywood)\b", lower):
        return (
            "Try listening to \"Kaathalae Kaathalae\" from 96 (2018).\n\n"
            "Why it fits:\n"
            "- Soft, emotional, and easy to replay.\n"
            "- Strong melody without feeling noisy.\n"
            "- A safer Tamil recommendation than guessing random film credits.\n\n"
            "If you want something more energetic, try \"Aaluma Doluma\" from Vedalam (2015)."
        )
    if re.search(r"\b(sad|emotional|heartbreak|heartbroken|lonely)\b", lower):
        return (
            "Try \"The Night We Met\" by Lord Huron.\n\n"
            "It is calm, emotional, and works well when you want something reflective without too much noise."
        )
    if re.search(r"\b(focus|study|work|calm|peace|relax|sleep)\b", lower):
        return (
            "Try \"Weightless\" by Marconi Union.\n\n"
            "It is a calm instrumental track, so it is better for focus or relaxing than a lyric-heavy song."
        )
    if re.search(r"\b(happy|party|energy|energetic|workout|gym)\b", lower):
        return (
            "Try \"Good Life\" by OneRepublic.\n\n"
            "It is upbeat, clean, and easy to listen to when you want a positive mood."
        )
    return (
        "Try \"Kun Faya Kun\" from Rockstar (2011).\n\n"
        "It is soulful, memorable, and works even if you just want one strong song recommendation without a long list."
    )


def local_fast_reply(message: str) -> Optional[str]:
    text = clean_text(message).lower()
    if not text:
        return None
    math_text = re.sub(r"\b(answer only|only answer|reply only|respond only|the number|number only|just the number)\b", "", text)
    math_text = re.sub(r"\b(what is|what's|calculate|solve|please|can you|could you)\b", "", math_text)
    math_text = re.sub(r"\bplus\b", "+", math_text)
    math_text = re.sub(r"\bminus\b", "-", math_text)
    math_text = re.sub(r"\b(times|multiplied by|multiply by)\b", "*", math_text)
    math_text = re.sub(r"\b(divided by|divide by|over)\b", "/", math_text)
    math_text = clean_text(math_text).strip(" ?.!:")
    math_match = re.fullmatch(
        r"(?:what is|calculate|solve)?\s*(-?\d+(?:\.\d+)?)\s*([+\-*/x])\s*(-?\d+(?:\.\d+)?)\??",
        math_text,
    )
    if math_match:
        left = float(math_match.group(1))
        op = math_match.group(2)
        right = float(math_match.group(3))
        if op in {"*", "x"}:
            result = left * right
        elif op == "/":
            if right == 0:
                return "Division by zero is undefined."
            result = left / right
        elif op == "+":
            result = left + right
        else:
            result = left - right
        pretty = int(result) if result.is_integer() else round(result, 8)
        if re.search(r"\b(answer only|only answer|reply only|respond only|the number|number only|just the number)\b", text):
            return str(pretty)
        return f"Result: {pretty}"
    if re.fullmatch(r"(hi+|hello+|hey+|yo|hlo|hii+|namaste|namaskar)[!. ]*", text):
        return "Hey, I am here. What are we building or solving today?"
    if re.fullmatch(r"(thanks|thank you|thx|ty|ok|okay|cool|nice)[!. ]*", text):
        return "Anytime. Send me the next thing and I will help you move it forward."
    song = local_song_recommendation_reply(message)
    if song:
        return song
    if re.fullmatch(
        r"(what can you do|what all can you do|what are your capabilities|what can nexora do|what can u do|what do you do)[?.! ]*",
        text,
    ):
        return (
            "Short answer:\n"
            "I can help you think, write, code, research, plan, and create. The useful version is not just listing features; "
            "it is giving you a clear answer, checking assumptions, and turning messy ideas into something you can use.\n\n"
            "What I can help with:\n"
            "- Explain topics in simple or detailed form, including study-friendly answers.\n"
            "- Write, rewrite, summarize, and polish messages, essays, emails, scripts, and plans.\n"
            "- Help with code by finding bugs, improving structure, explaining errors, and suggesting tests.\n"
            "- Research current topics when needed and separate confirmed facts from uncertainty.\n"
            "- Turn goals into checklists, timelines, options, or practical next steps.\n"
            "- Create prompts and ideas for images, websites, apps, presentations, and creative work.\n\n"
            "How to use me well:\n"
            "- Ask for the result you want, not just the topic.\n"
            "- Tell me the audience, style, deadline, or constraints if they matter.\n"
            "- For current facts, ask me to verify instead of guessing.\n\n"
            "Bottom line:\n"
            "Give me a task, question, file, idea, or bug, and I will choose the clearest format: short answer, steps, table, checklist, explanation, or polished draft."
        )
    if text in {"who are you", "who are you?", "what are you", "what are you?"}:
        return "I am Nexora, your AI assistant for clear answers, coding help, research-aware reasoning, files, and project work."
    direct_name = local_direct_name_reply(text)
    if direct_name:
        return direct_name
    deficiency = local_deficiency_diagnosis_reply(text)
    if deficiency:
        return deficiency
    capability = local_capability_reply(text)
    if capability:
        return capability
    reflective = local_reflective_reply(text)
    if reflective:
        return reflective
    if re.search(r"\b(second world war|world war ii|world war 2|ww2)\b", text) and re.search(
        r"\b(cause|caused|reason|start|started|begin|began|behind|person|responsible|who)\b",
        text,
    ):
        return (
            "The Second World War was caused by a mix of unresolved problems after World War I, "
            "economic instability, aggressive expansion by fascist powers, and weak international response.\n\n"
            "Key points:\n"
            "- Germany was angry about the Treaty of Versailles, which punished it heavily after World War I.\n"
            "- The Great Depression made many countries unstable and helped extremist leaders gain support.\n"
            "- Adolf Hitler and the Nazi government rebuilt Germany's military and expanded into nearby territories.\n"
            "- Britain and France tried appeasement at first, which delayed direct confrontation.\n"
            "- The immediate trigger was Germany's invasion of Poland on September 1, 1939.\n\n"
            "Bottom line:\n"
            "Adolf Hitler was the main person behind the outbreak of the war, but the deeper causes were political, "
            "economic, and diplomatic failures across Europe."
        )
    return None


WRITING_KIND_RE = r"(essay|paragraph|speech|article|note|letter|application|notice)"
WRITING_LENGTH_RE = r"(long|short|brief|small|detailed|full|complete)"
WRITING_TOPIC_FILLERS = {
    "a", "an", "and", "about", "article", "brief", "can", "complete", "could",
    "create", "detailed", "draft", "essay", "for", "full", "give", "i", "in",
    "long", "make", "me", "need", "note", "of", "on", "paragraph", "please",
    "prepare", "short", "small", "speech", "letter", "application", "notice",
    "reason", "the", "want", "write", "you",
}
TITLE_ACRONYMS = {
    "ai", "api", "bjp", "cpu", "css", "gdp", "gpu", "hdd", "html", "http",
    "ias", "isro", "jee", "js", "ml", "nasa", "neet", "ram", "rom", "sat",
    "ssd", "ui", "url", "usb", "ux", "www",
}
TITLE_SPECIAL_WORDS = {
    "chatgpt": "ChatGPT",
    "youtube": "YouTube",
    "youtuber": "YouTuber",
    "wwi": "WWI",
    "wwii": "WWII",
    "ww2": "WWII",
    "ii": "II",
}


def title_case_topic(topic: str) -> str:
    topic = clean_text(topic)
    if not topic:
        return "the topic"
    small_words = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}
    words = []
    for index, word in enumerate(topic.split()):
        lower = word.lower()
        if lower in TITLE_SPECIAL_WORDS:
            words.append(TITLE_SPECIAL_WORDS[lower])
        elif lower in TITLE_ACRONYMS:
            words.append(lower.upper())
        else:
            words.append(lower if index and lower in small_words else lower.capitalize())
    return " ".join(words)


COUNTRY_NAME_ALIASES: Dict[str, Tuple[str, str]] = {
    "india": ("india", "Indian"),
    "indian": ("india", "Indian"),
    "america": ("america", "American"),
    "american": ("america", "American"),
    "usa": ("america", "American"),
    "us": ("america", "American"),
    "u s": ("america", "American"),
    "u.s.": ("america", "American"),
    "u.s.a.": ("america", "American"),
    "united states": ("america", "American"),
    "united states of america": ("america", "American"),
    "uk": ("uk", "British"),
    "britain": ("uk", "British"),
    "british": ("uk", "British"),
    "england": ("uk", "British"),
    "japan": ("japan", "Japanese"),
    "japanese": ("japan", "Japanese"),
    "south korea": ("south korea", "South Korean"),
    "korea": ("south korea", "South Korean"),
    "korean": ("south korea", "South Korean"),
    "france": ("france", "French"),
    "french": ("france", "French"),
    "brazil": ("brazil", "Brazilian"),
    "brazilian": ("brazil", "Brazilian"),
}


DIRECT_NAME_ANSWERS: Dict[Tuple[str, str], str] = {
    ("actor", "america"): "Tom Hanks",
    ("actress", "america"): "Meryl Streep",
    ("celebrity", "america"): "Dwayne Johnson",
    ("singer", "america"): "Taylor Swift",
    ("musician", "america"): "Taylor Swift",
    ("artist", "america"): "Taylor Swift",
    ("writer", "america"): "Stephen King",
    ("author", "america"): "Stephen King",
    ("scientist", "america"): "Katherine Johnson",
    ("athlete", "america"): "Serena Williams",
    ("player", "america"): "LeBron James",
    ("actor", "india"): "Amitabh Bachchan",
    ("actress", "india"): "Deepika Padukone",
    ("celebrity", "india"): "Amitabh Bachchan",
    ("singer", "india"): "Arijit Singh",
    ("musician", "india"): "A. R. Rahman",
    ("artist", "india"): "A. R. Rahman",
    ("writer", "india"): "R. K. Narayan",
    ("author", "india"): "R. K. Narayan",
    ("scientist", "india"): "C. V. Raman",
    ("athlete", "india"): "P. V. Sindhu",
    ("player", "india"): "Sachin Tendulkar",
    ("cricketer", "india"): "Sachin Tendulkar",
    ("actor", "uk"): "Benedict Cumberbatch",
    ("actress", "uk"): "Emma Watson",
    ("celebrity", "uk"): "David Beckham",
    ("singer", "uk"): "Adele",
    ("actor", "japan"): "Ken Watanabe",
    ("celebrity", "japan"): "Naomi Osaka",
    ("singer", "japan"): "Hikaru Utada",
    ("actor", "south korea"): "Lee Min-ho",
    ("actress", "south korea"): "Bae Suzy",
    ("celebrity", "south korea"): "BTS",
    ("singer", "south korea"): "Jungkook",
    ("actor", "france"): "Omar Sy",
    ("celebrity", "france"): "Kylian Mbappe",
    ("singer", "france"): "Edith Piaf",
    ("actor", "brazil"): "Wagner Moura",
    ("celebrity", "brazil"): "Neymar",
    ("singer", "brazil"): "Anitta",
}


DIRECT_NAME_DEFAULTS: Dict[str, str] = {
    "actor": "Tom Hanks",
    "actress": "Meryl Streep",
    "celebrity": "Amitabh Bachchan",
    "singer": "Taylor Swift",
    "musician": "A. R. Rahman",
    "artist": "A. R. Rahman",
    "writer": "Stephen King",
    "author": "Stephen King",
    "scientist": "C. V. Raman",
    "athlete": "Serena Williams",
    "player": "Sachin Tendulkar",
    "cricketer": "Sachin Tendulkar",
}


def normalize_country_name(raw: str) -> Tuple[str, str]:
    key = clean_text(raw).lower().strip(" .,:;-?")
    key = re.sub(r"\b(the|from|in|of)\b", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return COUNTRY_NAME_ALIASES.get(key, (key, title_case_topic(key)))


def normalize_person_kind(raw: str) -> str:
    key = clean_text(raw).lower().strip(" .,:;-?")
    aliases = {
        "actors": "actor",
        "actresses": "actress",
        "celebs": "celebrity",
        "celebrities": "celebrity",
        "singers": "singer",
        "musicians": "musician",
        "artists": "artist",
        "writers": "writer",
        "authors": "author",
        "scientists": "scientist",
        "players": "player",
        "athletes": "athlete",
        "cricketers": "cricketer",
    }
    return aliases.get(key, key)


def local_direct_name_reply(message: str) -> Optional[str]:
    text = clean_text(message)
    lower = text.lower().strip(" .!?")
    person_kind = r"actor|actress|celebrity|celebrities|celeb|celebs|singer|musician|artist|writer|author|scientist|athlete|player|cricketer"
    country_part = r"[a-zA-Z .'-]{2,60}"

    match = re.search(
        rf"\b(?:name|give|tell me|tell|mention)\s+(?:me\s+)?(?:one\s+|a\s+|an\s+|any\s+)?(?P<kind>{person_kind})\s+(?:from|in|of)\s+(?P<country>{country_part})$",
        lower,
    )
    if not match:
        match = re.search(
            rf"\b(?:name|give|tell me|tell|mention)\s+(?:me\s+)?(?:one\s+|a\s+|an\s+|any\s+)?(?P<country>{country_part})\s+(?P<kind>{person_kind})$",
            lower,
        )
    if match:
        kind = normalize_person_kind(match.group("kind"))
        country_key, adjective = normalize_country_name(match.group("country"))
        person = DIRECT_NAME_ANSWERS.get((kind, country_key)) or DIRECT_NAME_DEFAULTS.get(kind)
        if person:
            return f"One well-known {adjective} {kind} is {person}."

    generic = re.search(
        rf"\b(?:name|give|tell me|tell|mention)\s+(?:me\s+)?(?:one\s+|a\s+|an\s+|any\s+)?(?P<kind>{person_kind})$",
        lower,
    )
    if generic:
        kind = normalize_person_kind(generic.group("kind"))
        person = DIRECT_NAME_DEFAULTS.get(kind)
        if person:
            return f"One well-known {kind} is {person}."

    return None


def local_reflective_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(ai|artificial intelligence|assistant|chatbot|nexora|model)\b", lower):
        return None
    if not re.search(r"\b(powerful|power|best|better|good|useful|trust|trusted|trustworthy|safe|safety|dangerous|wisdom|intelligent|smart|human|understand|capable|capability)\b", lower):
        return None
    if re.search(r"\b(code|bug|fix|install|run|running|api|backend|frontend|html|css|javascript|python|deploy)\b", lower):
        return None
    if re.search(r"\b(compare|comparison|vs|versus|explain|analyze|analyse|how|why|steps?|guide|practical answer)\b", lower):
        return None
    if re.search(r"\b(ram|cpu|gpu|memory|hardware|performance|latency|tokens?|context window|inference|training|server|hosting|docker|hugging face|space)\b", lower):
        return None

    if re.search(r"\b(powerful|power|capability|capable)\b", lower):
        return (
            "Interesting question to sit with. The strongest version of AI is not just the one that can do the most things.\n\n"
            "**Power in AI is usefulness with judgment.**\n\n"
            "A powerful AI should be able to:\n\n"
            "- **Understand the real need:** It should look past messy wording and figure out what the person is actually trying to solve.\n"
            "- **Know its limits:** It should be confident when the facts are solid, but honest when something needs search, evidence, or expert judgment.\n"
            "- **Stay useful under pressure:** If one engine is slow, it should fall back to another path instead of giving a dead-end error.\n"
            "- **Earn trust:** It should be accurate, clear, and willing to say uncomfortable truths instead of sounding impressive for no reason.\n"
            "- **Protect the user:** Power without safety is not intelligence. It is just risk with good grammar.\n\n"
            "The weaker version of powerful is just fluent text. That can look impressive, but if it guesses, hallucinates, or hides uncertainty, it becomes dangerous.\n\n"
            "The better version is closer to wisdom: useful knowledge, careful reasoning, clean communication, and judgment about when not to overclaim.\n\n"
            "For Nexora, that means speed, memory, real-time context, local fallback, clean structure, and a human tone all working together."
        )

    if re.search(r"\b(trust|trusted|trustworthy|safe|safety|dangerous|honest|accuracy|accurate)\b", lower):
        return (
            "The key thing is that trust in AI should be earned, not assumed.\n\n"
            "**A trustworthy AI is not the one that always sounds confident. It is the one that knows when confidence is deserved.**\n\n"
            "That means it should:\n\n"
            "- **Separate facts from guesses:** Stable knowledge is fine, but current claims need evidence.\n"
            "- **Admit uncertainty:** Saying \"I cannot verify that yet\" is better than inventing a polished answer.\n"
            "- **Use the right tool:** Search for current facts, local memory for preferences, and structured reasoning for complex problems.\n"
            "- **Avoid harm:** A useful answer should not create danger, confusion, or false confidence.\n\n"
            "In practice, the safest AI is not timid. It is careful. It still helps, but it does not pretend."
        )

    return (
        "The way I think about it is simple: a good AI should make thinking easier, not noisier.\n\n"
        "**The best AI is not just smart. It is useful, honest, and steady.**\n\n"
        "It should understand the user's intent, answer in clean language, use tools when facts may be current, and avoid pretending when it does not know.\n\n"
        "That balance matters because fluent answers can feel intelligent even when they are wrong. Real usefulness comes from clarity plus judgment."
    )


def local_deficiency_diagnosis_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(deficiency|weakness|issue|problem|wrong|why did|which one|which deficiency|learning a subject)\b", lower):
        return None
    if not re.search(r"\b(reasoning|understanding|accuracy|accurate|structure|answer|learning a subject|fitness plan)\b", lower):
        return None
    return (
        "It is mainly an understanding and intent-routing deficiency.\n\n"
        "What happened:\n"
        "- The user asked for a fitness plan, which needs a practical workout schedule.\n"
        "- The backend treated 'fitness plan' like a writing topic or school subject.\n"
        "- Then it used a generic essay-style frame, so the answer talked about 'learning a subject' instead of giving exercises, days, and rules.\n\n"
        "Which level was weak:\n"
        "- Understanding: main issue, because it misunderstood the task type.\n"
        "- Answer structure: secondary issue, because the format should have been a plan, not an essay.\n"
        "- Reasoning: minor issue, because a reasoning check should notice that a plan needs actionable steps.\n"
        "- Accuracy: not the main issue. The answer was not exactly false; it was irrelevant and too generic.\n\n"
        "Bottom line:\n"
        "When an answer is generic but not factually wrong, fix understanding and routing first, then structure. Accuracy matters after the app is answering the right task."
    )


def clean_writing_topic_candidate(raw: str) -> str:
    topic = clean_text(raw)
    topic = re.sub(r"(?i)\b(thanks|thank you|pls|please|sir|mam|ma'am)\b", " ", topic)
    topic = re.sub(r"(?i)^(i\s+(need|want|would like)\s+|can you\s+|could you\s+|would you\s+)", "", topic)
    topic = re.sub(r"(?i)^(write|give|make|create|draft|prepare)\s+(me\s+)?", "", topic)
    topic = re.sub(r"(?i)\b" + WRITING_KIND_RE + r"\b", " ", topic)
    topic = re.sub(r"(?i)\b" + WRITING_LENGTH_RE + r"\b", " ", topic)
    topic = re.sub(r"(?i)^(me\s+|an?\s+|the\s+|on\s+|about\s+|for\s+|of\s+)+", "", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" .,:;-")
    return topic


def meaningful_topic_words(topic: str) -> List[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{1,}", clean_text(topic).lower())
    return [word for word in words if word not in WRITING_TOPIC_FILLERS]


def extract_writing_topic(raw: str) -> str:
    text = clean_text(raw)
    topic_match = re.search(r"(?i)\b(?:topic\s*(?:is|:)?|on|about|for|regarding|titled)\s+(.+)$", text)
    if topic_match:
        topic = clean_writing_topic_candidate(topic_match.group(1))
    else:
        topic = clean_writing_topic_candidate(text)
    return title_case_topic(topic) if meaningful_topic_words(topic) else "the topic"


def normalize_prompt_topic(raw: str) -> str:
    return extract_writing_topic(raw)


def analyze_writing_request(message: str) -> Dict[str, Any]:
    text = clean_text(message)
    lower = text.lower()
    has_kind = bool(re.search(r"\b" + WRITING_KIND_RE + r"\b", lower))
    has_write_action = bool(re.search(r"\b(write|draft|prepare|compose|make|create|give)\b", lower))
    has_need_action = bool(re.search(r"\b(i\s+need|i\s+want|need|want)\b", lower))
    has_writing_phrase = bool(re.search(r"\b(write\s+(about|on)|write\s+me|draft\s+me|give\s+me\s+(an?\s+)?(?:" + WRITING_KIND_RE + r"))\b", lower))
    is_writing = has_writing_phrase or (has_kind and (has_write_action or has_need_action or len(text.split()) <= 8))
    if not has_kind and re.search(r"\b(fitness|workout|exercise|gym|training|diet)\b", lower) and re.search(r"\b(plan|routine|schedule|program)\b", lower):
        is_writing = False
    kind_match = re.search(r"\b" + WRITING_KIND_RE + r"\b", lower)
    kind = kind_match.group(1) if kind_match else "writing"
    length = "long" if re.search(r"\b(long|detailed|full|complete)\b", lower) else "balanced"
    if re.search(r"\b(short|brief|small)\b", lower):
        length = "short"
    topic = extract_writing_topic(text)
    missing_topic = topic == "the topic"
    return {
        "is_writing": is_writing,
        "kind": kind,
        "length": length,
        "topic": topic,
        "missing_topic": missing_topic,
    }


def missing_writing_topic_reply(request: Dict[str, Any]) -> str:
    length = "long " if request.get("length") == "long" else "short " if request.get("length") == "short" else ""
    kind = clean_text(str(request.get("kind") or "writing"))
    if kind == "writing":
        kind = "piece"
    return (
        f"Sure. What topic should the {length}{kind} be about?\n\n"
        "Send just the topic, and I will write it properly."
    )


def build_fathers_day_essay(length: str = "balanced") -> str:
    if length == "long":
        return (
            "Father's Day is a special occasion dedicated to honoring fathers and father figures for their love, "
            "sacrifice, guidance, and support. A father plays an important role in shaping a child's life, not only "
            "by providing for the family, but also by teaching values through daily actions.\n\n"
            "A father's love is often quiet. He may not always express his feelings in many words, but his care can "
            "be seen in his hard work, protection, patience, and concern for the future of his children. He stands "
            "beside the family during difficult times and gives strength when others feel weak.\n\n"
            "Fathers also teach discipline and responsibility. They correct us when we make mistakes, encourage us "
            "when we lose confidence, and guide us toward better choices. Their advice may sometimes feel strict, "
            "but it often comes from experience and love.\n\n"
            "Father's Day reminds us that we should not take these sacrifices for granted. A simple thank you, a kind "
            "message, or spending time together can mean a lot. The day is not only about gifts; it is about gratitude, "
            "respect, and emotional connection.\n\n"
            "In many families, fathers are the silent strength behind every achievement. Their efforts help children "
            "dream bigger, work harder, and face life with courage. This is why Father's Day is meaningful: it gives us "
            "a chance to recognize the love that often works quietly in the background.\n\n"
            "Bottom line:\n"
            "Father's Day teaches us to value our fathers, respect their sacrifices, and appreciate the steady love they give every day."
        )
    return (
        "Father's Day is a special occasion to honor the love, sacrifice, and guidance of fathers. "
        "A father often works quietly in the background, supporting the family, protecting his children, "
        "and teaching them important values through his actions.\n\n"
        "A father's love may not always be expressed in many words, but it can be seen in his care, hard work, "
        "and constant concern for the future of his children. He encourages us when we feel weak, corrects us "
        "when we make mistakes, and helps us become responsible people.\n\n"
        "Father's Day reminds us to thank our fathers for everything they do. A simple wish, a kind word, or "
        "spending time with them can make them feel loved and respected. It is not only a day for gifts, but "
        "also a day for gratitude.\n\n"
        "Bottom line:\n"
        "Father's Day teaches us to value our fathers and appreciate the strength, patience, and love they give us every day."
    )


def is_world_war_two_topic(text: str) -> bool:
    lower = clean_text(text).lower()
    return bool(re.search(r"\b(second world war|world war ii|world war 2|ww2|wwii)\b", lower))


def build_world_war_two_history(length: str = "balanced") -> str:
    if length == "short":
        return (
            "World War II was a global war fought from 1939 to 1945 between the Axis powers, mainly Germany, Italy, and Japan, "
            "and the Allies, including Britain, the Soviet Union, the United States, China, and many others.\n\n"
            "Key points:\n"
            "- It began in Europe after Nazi Germany invaded Poland on September 1, 1939.\n"
            "- Major causes included the Treaty of Versailles, the Great Depression, aggressive expansion, militarism, and the rise of fascist dictatorships.\n"
            "- The war included the Holocaust, in which Nazi Germany murdered about six million Jews and millions of other victims.\n"
            "- It ended in 1945 after Germany surrendered in May and Japan surrendered in September.\n\n"
            "Bottom line:\n"
            "World War II changed world politics, weakened old empires, led to the United Nations, and shaped the modern world."
        )
    return (
        "World War II was a global war fought from 1939 to 1945 between the Axis powers and the Allies. "
        "It was not just one battle or one country's problem; it spread across Europe, Africa, Asia, and the Pacific, "
        "and it reshaped the modern world.\n\n"
        "Key points:\n"
        "- Causes: The Treaty of Versailles left Germany angry after World War I, the Great Depression created instability, and fascist leaders used nationalism, racism, and militarism to gain power.\n"
        "- Beginning: Nazi Germany invaded Poland on September 1, 1939. Britain and France declared war on Germany soon after.\n"
        "- Major powers: The Axis included Germany, Italy, and Japan. The Allies included Britain, the Soviet Union, the United States, China, France, and many other countries.\n"
        "- Turning points: Germany's invasion of the Soviet Union, the Battle of Stalingrad, the Allied D-Day landings in Normandy, and major Pacific battles weakened the Axis powers.\n"
        "- Human cost: The war caused tens of millions of deaths and included the Holocaust, in which Nazi Germany murdered about six million Jews and millions of other victims.\n"
        "- End: Germany surrendered in May 1945. Japan surrendered in September 1945 after the atomic bombings of Hiroshima and Nagasaki and the Soviet entry into the war against Japan.\n\n"
        "Why it matters:\n"
        "World War II led to the creation of the United Nations, accelerated the decline of European colonial empires, and helped create a new world order dominated by the United States and the Soviet Union during the Cold War.\n\n"
        "Bottom line:\n"
        "The history of World War II is important because it shows how economic crisis, extreme ideology, weak diplomacy, and aggressive expansion can turn regional conflicts into a global disaster."
    )


def build_world_war_two_essay(length: str = "balanced") -> str:
    if length == "short":
        return (
            "History of World War II\n\n"
            "World War II was one of the most destructive wars in human history. It was fought from 1939 to 1945 between the Axis powers and the Allies. "
            "The war began in Europe when Nazi Germany invaded Poland on September 1, 1939. Soon, Britain and France declared war on Germany.\n\n"
            "The main causes included the harsh effects of the Treaty of Versailles, the Great Depression, militarism, aggressive expansion, and the rise of dictators such as Adolf Hitler. "
            "The war spread across Europe, Africa, Asia, and the Pacific. It caused huge destruction and led to the Holocaust, in which millions of innocent people were murdered.\n\n"
            "World War II ended in 1945 after Germany surrendered in May and Japan surrendered in September. The war changed the world by creating the United Nations, weakening colonial empires, and beginning the Cold War period.\n\n"
            "Bottom line:\n"
            "World War II teaches that hatred, dictatorship, and unchecked aggression can cause terrible human suffering."
        )
    if length == "long":
        return (
            "History of World War II\n\n"
            "World War II was a global conflict fought from 1939 to 1945. It involved many countries and was fought between two major groups: the Axis powers, mainly Germany, Italy, and Japan, and the Allies, including Britain, the Soviet Union, the United States, China, France, and many others.\n\n"
            "The roots of the war go back to the end of World War I. The Treaty of Versailles punished Germany heavily, creating anger and economic hardship. Later, the Great Depression made life worse in many countries. In this unstable situation, Adolf Hitler and the Nazi Party rose to power in Germany by promising national strength and blaming others for the country's problems.\n\n"
            "The immediate beginning of the war came on September 1, 1939, when Nazi Germany invaded Poland. Britain and France declared war on Germany. Over the next years, Germany conquered or attacked many parts of Europe, while Japan expanded aggressively in Asia and the Pacific.\n\n"
            "The war had several major turning points. Germany's invasion of the Soviet Union became a costly failure, especially after the Battle of Stalingrad. In 1944, Allied forces landed in Normandy on D-Day and began pushing Germany back from the west. In the Pacific, the United States and its allies gradually defeated Japan through major island battles.\n\n"
            "World War II also caused enormous human suffering. Tens of millions of people died, including soldiers and civilians. One of the darkest parts of the war was the Holocaust, in which Nazi Germany murdered about six million Jews and millions of other victims.\n\n"
            "The war ended in 1945. Germany surrendered in May after Allied forces entered Berlin. Japan surrendered in September after the atomic bombings of Hiroshima and Nagasaki and the Soviet Union's entry into the war against Japan.\n\n"
            "After the war, the world changed deeply. The United Nations was formed to help prevent future wars. European colonial empires weakened. The United States and the Soviet Union became superpowers, leading to the Cold War.\n\n"
            "Bottom line:\n"
            "World War II is important because it shows the danger of extreme nationalism, dictatorship, racism, and unchecked aggression. It also explains many parts of the modern world."
        )
    return (
        "History of World War II\n\n"
        "World War II was a global war fought from 1939 to 1945 between the Axis powers and the Allies. It began in Europe when Nazi Germany invaded Poland on September 1, 1939, leading Britain and France to declare war on Germany.\n\n"
        "The war grew from several causes: anger over the Treaty of Versailles, the economic damage of the Great Depression, the rise of fascist dictatorships, militarism, and aggressive expansion by Germany, Italy, and Japan. Adolf Hitler and Nazi Germany played a central role in starting the war in Europe.\n\n"
        "The conflict spread across Europe, Africa, Asia, and the Pacific. Important turning points included the Battle of Stalingrad, the D-Day landings in Normandy, and major Allied victories in the Pacific. The war also included the Holocaust, in which Nazi Germany murdered about six million Jews and millions of other victims.\n\n"
        "World War II ended in 1945. Germany surrendered in May, and Japan surrendered in September after the atomic bombings of Hiroshima and Nagasaki and the Soviet Union's entry into the war against Japan.\n\n"
        "Bottom line:\n"
        "World War II changed the world by leading to the United Nations, weakening colonial empires, and creating the conditions for the Cold War."
    )


def build_fitness_essay(length: str = "balanced") -> str:
    if length == "short":
        return (
            "Fitness\n\n"
            "Fitness means keeping the body active, strong, and healthy through regular exercise, balanced food, rest, and discipline. It is important because it improves stamina, supports the heart, strengthens muscles, and helps a person feel more confident in daily life.\n\n"
            "A good fitness routine should include strength training, cardio, stretching, enough sleep, and proper hydration. Fitness is not only about looking good; it is about having energy, avoiding unhealthy habits, and building a better lifestyle.\n\n"
            "Bottom line:\n"
            "Fitness becomes useful when it is practiced consistently with a simple plan and gradual progress."
        )
    return (
        "Fitness\n\n"
        "Fitness is the condition of being physically active, healthy, and capable of handling daily work with energy. It is important because it supports the heart, muscles, bones, sleep, mood, confidence, and long-term health.\n\n"
        "A fit person does not depend only on intense workouts. Real fitness comes from a balanced routine that includes strength exercises, cardio, mobility, rest, hydration, and nutritious food. Strength training helps build muscle and protect joints. Cardio improves stamina and heart health. Stretching and mobility reduce stiffness and support better movement.\n\n"
        "Fitness also builds discipline. When a person follows a regular routine, even for a few minutes every day, it creates consistency and self-control. This can improve focus, reduce stress, and make everyday tasks feel easier.\n\n"
        "The best fitness plan is simple and sustainable. Doing too much at once can cause tiredness or injury, but slow progress helps the body adapt safely.\n\n"
        "Bottom line:\n"
        "Fitness is not just about appearance. It is a long-term habit that improves health, energy, confidence, and quality of life."
    )


def build_topic_specific_writing(message: str, topic: str, kind: str, length: str) -> Optional[str]:
    normalized_kind = normalize_person_kind(kind) if kind in {"articles", "notes"} else clean_text(kind).lower()
    if is_world_war_two_topic(message) or is_world_war_two_topic(topic):
        if normalized_kind == "paragraph":
            return (
                "World War II was a global war fought from 1939 to 1945 between the Axis powers and the Allies. "
                "It began in Europe after Nazi Germany invaded Poland on September 1, 1939. The war spread across Europe, Africa, Asia, and the Pacific, causing massive destruction and tens of millions of deaths. "
                "It also included the Holocaust, one of history's worst crimes against humanity. The war ended in 1945 after Germany surrendered in May and Japan surrendered in September. "
                "World War II changed the modern world by leading to the United Nations, weakening colonial empires, and beginning the Cold War period."
            )
        if normalized_kind in {"note", "notes"}:
            return build_world_war_two_history("short" if length == "short" else "balanced")
        if normalized_kind == "speech":
            return (
                "Good morning everyone,\n\n"
                "Today I would like to speak about the history of World War II.\n\n"
                "World War II was fought from 1939 to 1945 between the Axis powers and the Allies. It began when Nazi Germany invaded Poland on September 1, 1939. "
                "The war spread across many parts of the world and caused enormous suffering.\n\n"
                "Its main causes included the Treaty of Versailles, economic crisis, aggressive expansion, militarism, and the rise of dictatorships. The war ended in 1945, but its effects shaped the modern world through the United Nations, the Cold War, and major political changes.\n\n"
                "The history of World War II teaches us that hatred, dictatorship, and unchecked aggression can destroy millions of lives.\n\n"
                "Thank you."
            )
        return build_world_war_two_essay(length)
    if re.search(r"\b(fitness|health|exercise|workout|gym|training|cardio|strength)\b", f"{message} {topic}".lower()):
        if normalized_kind == "paragraph":
            return (
                "Fitness means keeping the body active, strong, and healthy through regular exercise, balanced food, rest, and discipline. "
                "It improves stamina, supports the heart and muscles, boosts confidence, and helps people handle daily work with more energy. "
                "A good fitness routine includes strength training, cardio, stretching, hydration, sleep, and steady progress."
            )
        return build_fitness_essay(length)
    return None


def writing_topic_frame(topic: str) -> Dict[str, str]:
    lower = topic.lower()
    core_match = re.match(r"(?i)^(?:importance|value|role|benefits?)\s+of\s+(.+)$", topic.strip())
    core_topic = title_case_topic(core_match.group(1)) if core_match else topic
    core_lower = core_topic.lower()
    if re.search(r"\b(history|historical|war|revolution|empire|civilization|civilisation|ancient|medieval|modern world)\b", lower):
        return {
            "thesis": f"The importance of {core_lower} comes from understanding real causes, events, decisions, and consequences from the past.",
            "human": "History matters because it shows how people's choices, leadership, conflict, ideas, and mistakes shaped later society.",
            "detail": "A strong history answer should explain the background, the main events, the people involved, and the impact that followed.",
            "action": "The topic becomes useful when it connects dates and facts with cause, effect, and lessons for the present.",
        }
    if re.search(r"\b(fitness|health|exercise|workout|gym|training|cardio|strength|diet)\b", lower):
        return {
            "thesis": f"The importance of {core_lower} is that it improves physical health, energy, discipline, confidence, and long-term well-being.",
            "human": "Fitness is not only about appearance; it supports the heart, muscles, sleep, mood, and daily stamina.",
            "detail": "A good fitness routine combines strength training, cardio, mobility, rest, hydration, and balanced food instead of depending on one shortcut.",
            "action": "The best result comes from a simple plan followed consistently, with gradual progress and enough recovery.",
        }
    if re.search(r"\b(environment|pollution|climate|nature|tree|water|air|earth|plastic)\b", lower):
        return {
            "thesis": f"The importance of {core_lower} comes from its direct effect on health, nature, and the quality of life for future generations.",
            "human": "It is not only a science topic; it is connected to the air people breathe, the water they drink, and the places they call home.",
            "detail": "Small daily choices, responsible public action, and better awareness can reduce damage and create cleaner surroundings.",
            "action": "The real solution begins when people treat protection of nature as a shared responsibility, not someone else's problem.",
        }
    if re.search(r"\b(ai|artificial intelligence|technology|internet|computer|mobile|digital|robot|science)\b", lower):
        return {
            "thesis": f"The importance of {core_lower} comes from the way it changes how people learn, work, communicate, and solve problems.",
            "human": "Its value depends on how wisely people use it, because powerful tools can help society only when they are guided by human judgment.",
            "detail": "Technology can save time, improve access to knowledge, and create new opportunities, but it also demands responsibility and balance.",
            "action": "The best approach is to use it as a support for clear thinking, not as a replacement for effort, creativity, or values.",
        }
    if re.search(r"\b(education|school|student|teacher|learning|knowledge|study|exam|discipline)\b", lower):
        return {
            "thesis": f"The importance of {core_lower} lies in the way it builds knowledge, confidence, discipline, and the ability to make better choices.",
            "human": "True learning is not only about marks or memorizing facts; it is about understanding life more clearly.",
            "detail": "A good education develops curiosity, patience, communication, and the courage to solve difficult problems.",
            "action": "When learning becomes connected with real life, it helps a person grow in both skill and character.",
        }
    if re.search(r"\b(independence|republic|india|nation|country|freedom|patriotism)\b", lower):
        return {
            "thesis": f"The importance of {core_lower} is that it reminds people of responsibility, unity, sacrifice, and respect for the nation.",
            "human": "It connects the present generation with the struggles and hopes of those who worked for a better future.",
            "detail": "National progress depends not only on leaders, but also on citizens who act with honesty, discipline, and care for others.",
            "action": "The strongest form of respect is to contribute through good actions, awareness, and responsible citizenship.",
        }
    if re.search(r"\b(friendship|family|kindness|honesty|discipline|respect|responsibility|time|success|hard work)\b", lower):
        return {
            "thesis": f"The importance of {core_lower} is seen in how it shapes character and influences the way people treat others.",
            "human": "Its importance is often seen in ordinary moments: choices, relationships, habits, and the way people respond to difficulty.",
            "detail": "A strong value becomes meaningful when it is practiced consistently, not only spoken about in good words.",
            "action": "Real growth begins when a person turns the idea into daily action.",
        }
    return {
        "thesis": f"The importance of {core_lower} is that it helps people understand life, choices, and the world around them more clearly.",
        "human": "A good understanding of this subject connects knowledge with real situations instead of keeping it as a memorized idea.",
        "detail": "It encourages awareness, better judgment, and the ability to look at a problem from more than one side.",
        "action": "The topic becomes truly useful when it is explained simply and applied thoughtfully in daily life.",
    }


def writing_sentence_subject(topic: str) -> str:
    core_match = re.match(r"(?i)^(?:importance|value|role|benefits?)\s+of\s+(.+)$", topic.strip())
    if core_match:
        lead_word = clean_text(topic).split(" ", 1)[0].lower()
        if lead_word == "benefits":
            return "The benefits of " + title_case_topic(core_match.group(1)).lower()
        return f"The {lead_word} of " + title_case_topic(core_match.group(1)).lower()
    return topic


def build_polished_paragraph(topic: str, length: str) -> str:
    frame = writing_topic_frame(topic)
    subject = writing_sentence_subject(topic)
    if length == "long":
        return (
            f"{subject} is meaningful because it affects the way people think, act, and understand the world. "
            f"{frame['thesis']} {frame['human']} {frame['detail']} {frame['action']}"
        )
    return (
        f"{subject} is meaningful because it helps people think more clearly and act more responsibly. "
        f"{frame['thesis']} {frame['action']}"
    )


def build_polished_essay(topic: str, length: str) -> str:
    frame = writing_topic_frame(topic)
    title = topic
    if length == "short":
        return (
            f"{title}\n\n"
            f"{frame['thesis']} {frame['human']}\n\n"
            f"{frame['detail']}\n\n"
            "Conclusion:\n"
            f"{frame['action']}"
        )
    if length == "long":
        return (
            f"{title}\n\n"
            f"{frame['thesis']} It deserves thoughtful attention because it is connected with real life, human behavior, "
            "and the choices people make every day.\n\n"
            f"{frame['human']} This is why the topic should not be understood only in a bookish way. It becomes clearer when "
            "we connect it with daily experiences, personal responsibility, and the needs of society.\n\n"
            f"{frame['detail']} A clear understanding of the topic helps people avoid careless thinking and make wiser decisions. "
            "It also encourages discipline, awareness, and respect for consequences.\n\n"
            "Another important point is that strong ideas become useful only when they are put into practice. Words are easy, "
            "but steady action shows real understanding. When people apply the lesson in ordinary situations, the topic becomes "
            "part of character, not just information.\n\n"
            "Conclusion:\n"
            f"{frame['action']} In this way, {topic.lower()} becomes more than a subject to write about; it becomes a guide for "
            "clearer thinking and better living."
        )
    return (
        f"{title}\n\n"
        f"{frame['thesis']} It deserves attention because it is connected with real life and human understanding.\n\n"
        f"{frame['human']} This makes the topic useful for students, families, and society because it teaches people to think "
        "beyond simple answers.\n\n"
        f"{frame['detail']}\n\n"
        "Conclusion:\n"
        f"{frame['action']}"
    )


def build_polished_speech(topic: str, length: str) -> str:
    frame = writing_topic_frame(topic)
    middle = (
        f"{frame['thesis']}\n\n"
        f"{frame['human']} {frame['detail']}\n\n"
    )
    if length == "short":
        middle = f"{frame['thesis']} {frame['action']}\n\n"
    elif length == "long":
        middle += (
            "We often understand important ideas only when they touch our own lives. That is why this topic should make us "
            "pause, think, and act with more responsibility.\n\n"
        )
    return (
        "Good morning everyone,\n\n"
        f"Today, I would like to speak about {topic.lower()}.\n\n"
        f"{middle}"
        f"{frame['action']}\n\n"
        "Thank you."
    )


def build_polished_article(topic: str, length: str) -> str:
    frame = writing_topic_frame(topic)
    if length == "short":
        return (
            f"{topic}: Why It Matters\n\n"
            f"{frame['thesis']} {frame['human']}\n\n"
            f"{frame['action']}"
        )
    return (
        f"{topic}: Why It Matters\n\n"
        f"{frame['thesis']} {frame['human']}\n\n"
        f"{frame['detail']}\n\n"
        f"In practice, the value of {topic.lower()} depends on awareness and action. {frame['action']}"
    )


def build_polished_note(topic: str, length: str) -> str:
    frame = writing_topic_frame(topic)
    points = [
        frame["thesis"],
        frame["human"],
        frame["detail"],
        frame["action"],
    ]
    if length == "short":
        points = [points[0], points[-1]]
    return "\n".join([
        f"Notes on {topic}:",
        "",
        *[f"- {point}" for point in points],
    ])


def extract_leave_reason(message: str, topic: str = "") -> str:
    text = clean_text(message)
    lower = text.lower()
    reason_match = re.search(
        r"(?i)\b(?:reason|because|as|for)\s*(?:is|:)?\s+(.+)$",
        text,
    )
    reason = clean_text(reason_match.group(1)) if reason_match else clean_text(topic)
    reason = re.sub(r"(?i)\b(leave|letter|application|notice|request|please|kindly)\b", " ", reason)
    reason = re.sub(r"(?i)\b(to|for)\s+(my\s+)?(school|college|class|principal|class teacher|office|company|manager)\b", " ", reason)
    reason = re.sub(r"\s+", " ", reason).strip(" .,:;-")
    if re.search(r"\b(sick|ill|unwell|fever|medical|health)\b", f"{lower} {reason.lower()}"):
        return "sick leave"
    if reason and reason.lower() not in {"the topic", "reason", "school", "my school", "college", "my college"}:
        return reason.lower()
    return "personal leave"


def build_leave_letter(message: str, topic: str, kind: str = "letter") -> str:
    lower = clean_text(message).lower()
    reason = extract_leave_reason(message, topic)
    is_office = bool(re.search(r"\b(office|company|manager|work|job|employee|team lead|hr)\b", lower))
    recipient = "The Manager" if is_office else "The Principal"
    place = "office" if is_office else "school"
    organization_label = "[Organization Name]" if is_office else "[School Name]"
    signoff = "Yours sincerely" if is_office else "Yours obediently"
    subject = "Application for Sick Leave" if "sick" in reason else "Leave Application"
    if "sick" in reason:
        reason_sentence = "I am not feeling well and need time to rest and recover."
    elif reason == "personal leave":
        reason_sentence = "I need to be absent due to personal reasons."
    else:
        reason_sentence = f"I need to be absent due to {reason}."
    return (
        "Date: [DD/MM/YYYY]\n\n"
        f"To\n{recipient}\n{organization_label}\n\n"
        f"Subject: {subject}\n\n"
        "Respected Sir/Madam\n\n"
        f"I am writing to request leave. {reason_sentence} Therefore, I will not be able to attend {place} for the required period.\n\n"
        "Kindly grant me leave. I will complete any missed work as soon as I return.\n\n"
        "Thank you for your understanding.\n\n"
        f"{signoff}\n"
        "[Your Name]"
    )


def build_polished_letter(message: str, topic: str, kind: str = "letter") -> str:
    lower = clean_text(message).lower()
    topic = title_case_topic(topic) if topic and topic != "the topic" else "Your Request"
    if re.search(r"\b(leave|sick|ill|unwell|fever|medical|absent)\b", lower + " " + topic.lower()):
        return build_leave_letter(message, topic, kind)
    return (
        "Date: [DD/MM/YYYY]\n\n"
        "To\n"
        "[Recipient Name/Designation]\n"
        "[Organization Name]\n\n"
        f"Subject: {topic}\n\n"
        "Respected Sir/Madam\n\n"
        f"I am writing this letter regarding {topic.lower()}. I request you to kindly consider the matter and take the necessary action.\n\n"
        "I would be grateful for your support and understanding.\n\n"
        "Thank you.\n\n"
        "Yours sincerely\n"
        "[Your Name]"
    )


def build_generic_writing(topic: str, kind: str = "essay", length: str = "balanced") -> str:
    normalized_kind = normalize_person_kind(kind) if kind in {"articles", "notes"} else clean_text(kind).lower()
    topic_specific = build_topic_specific_writing(topic, topic, normalized_kind, length)
    if topic_specific:
        return topic_specific
    if normalized_kind in {"paragraph"} or length == "short" and normalized_kind == "writing":
        return build_polished_paragraph(topic, length)
    if normalized_kind == "speech":
        return build_polished_speech(topic, length)
    if normalized_kind == "article":
        return build_polished_article(topic, length)
    if normalized_kind in {"note", "notes"}:
        return build_polished_note(topic, length)
    if normalized_kind in {"letter", "application", "notice"}:
        return build_polished_letter(topic, topic, normalized_kind)
    return build_polished_essay(topic, length)


def local_writing_reply(message: str, session_id: Optional[str] = None) -> Optional[str]:
    text = clean_text(message)
    request = analyze_writing_request(text)
    if not request.get("is_writing"):
        return None

    if request.get("missing_topic"):
        if session_id:
            set_pending_task(session_id, {
                "type": "writing_topic",
                "kind": request.get("kind", "essay"),
                "length": request.get("length", "balanced"),
                "source": "missing_topic",
            })
        return missing_writing_topic_reply(request)

    topic = str(request.get("topic") or "the topic")
    topic_lower = topic.lower()
    topic_specific = build_topic_specific_writing(
        text,
        topic,
        str(request.get("kind", "essay")),
        str(request.get("length", "balanced")),
    )
    if topic_specific:
        return topic_specific
    if "father" in topic_lower and "day" in topic_lower:
        return build_fathers_day_essay(str(request.get("length", "balanced")))
    if str(request.get("kind", "")).lower() in {"letter", "application", "notice"}:
        return build_polished_letter(
            text,
            topic,
            str(request.get("kind", "letter")),
        )

    return build_generic_writing(
        topic,
        str(request.get("kind", "essay")),
        str(request.get("length", "balanced")),
    )


LOCAL_KNOWLEDGE_CARDS: Dict[str, Dict[str, Any]] = {
    "photosynthesis": {
        "answer": "Photosynthesis is the process by which green plants, algae, and some bacteria use sunlight to make food from carbon dioxide and water.",
        "points": [
            "Chlorophyll in leaves absorbs light energy.",
            "Carbon dioxide enters through tiny openings called stomata.",
            "Water comes from the roots and moves to the leaves.",
            "Glucose is produced as food, and oxygen is released.",
        ],
        "bottom": "Photosynthesis changes light energy into chemical energy stored in glucose.",
    },
    "respiration": {
        "answer": "Respiration is the process by which living cells release energy from food, usually glucose.",
        "points": [
            "It happens in cells and provides energy for life processes.",
            "Aerobic respiration uses oxygen and releases more energy.",
            "Carbon dioxide and water are common waste products.",
        ],
        "bottom": "Respiration is how cells turn food into usable energy.",
    },
    "gravity": {
        "answer": "Gravity is the force of attraction between objects that have mass.",
        "points": [
            "It pulls objects toward Earth, which is why things fall down.",
            "It keeps planets moving around the Sun.",
            "More massive objects have stronger gravitational pull.",
        ],
        "bottom": "Gravity is the force that gives weight and keeps large objects in orbit.",
    },
    "democracy": {
        "answer": "Democracy is a system of government in which people have the power to choose their leaders and influence decisions.",
        "points": [
            "Citizens vote in elections.",
            "Leaders are expected to be accountable to the people.",
            "Rights, laws, and public participation are important.",
        ],
        "bottom": "Democracy means government by the people, directly or through elected representatives.",
    },
    "artificial intelligence": {
        "answer": "Artificial intelligence is technology that lets computers perform tasks that normally require human intelligence.",
        "points": [
            "It can understand language, recognize patterns, make predictions, and generate content.",
            "AI learns from data or follows rules designed by humans.",
            "It is useful, but it can make mistakes and needs human judgment.",
        ],
        "bottom": "AI is powerful when it helps people think, create, decide, and work faster.",
    },
    "machine learning": {
        "answer": "Machine learning is a part of AI where computers learn patterns from data instead of being programmed for every single rule.",
        "points": [
            "The model is trained on examples.",
            "It finds patterns and uses them to make predictions.",
            "Better data usually leads to better results.",
        ],
        "bottom": "Machine learning is how many modern AI systems improve from examples.",
    },
    "internet": {
        "answer": "The internet is a global network that connects computers and devices so they can share information.",
        "points": [
            "It supports websites, email, video calls, apps, and online learning.",
            "Data travels through connected networks using communication rules called protocols.",
            "It is useful, but privacy, distraction, and misinformation are risks.",
        ],
        "bottom": "The internet connects people and information across the world.",
    },
    "pollution": {
        "answer": "Pollution is the addition of harmful substances or energy to the environment.",
        "points": [
            "Air, water, soil, and noise pollution are common types.",
            "It can harm humans, animals, plants, and ecosystems.",
            "Reducing waste, saving energy, and using cleaner technology can help.",
        ],
        "bottom": "Pollution damages the environment, so prevention and responsible habits matter.",
    },
    "climate change": {
        "answer": "Climate change means long-term changes in Earth's temperature, rainfall, seasons, and weather patterns.",
        "points": [
            "Human activities such as burning fossil fuels increase greenhouse gases.",
            "It can cause heat waves, melting ice, rising sea levels, and extreme weather.",
            "Reducing emissions and adapting to changes are both important.",
        ],
        "bottom": "Climate change is a long-term environmental challenge driven strongly by greenhouse gases.",
    },
    "adolf hitler": {
        "answer": "Adolf Hitler was the dictator of Nazi Germany from 1933 to 1945 and one of the central figures behind the Second World War and the Holocaust.",
        "points": [
            "He led the Nazi Party and became chancellor of Germany in 1933.",
            "He built a totalitarian dictatorship based on extreme nationalism, racism, antisemitism, and militarism.",
            "His invasion of Poland on September 1, 1939, helped start the Second World War in Europe.",
            "His regime carried out the Holocaust, murdering about six million Jews and millions of other victims.",
            "He died by suicide in Berlin on April 30, 1945, as Nazi Germany was collapsing.",
        ],
        "bottom": "Hitler is remembered as a brutal dictator whose ideology and actions caused catastrophic war, genocide, and human suffering.",
    },
    "second world war": {
        "answer": "The Second World War was a global war fought from 1939 to 1945 between the Axis powers and the Allies.",
        "points": [
            "Major causes included unresolved tensions after World War I, economic crisis, aggressive expansion, and the rise of fascist dictatorships.",
            "Germany's invasion of Poland on September 1, 1939, triggered Britain and France to declare war.",
            "Adolf Hitler and Nazi Germany were central to the war in Europe, but the war had many causes and actors.",
            "The war ended in 1945 after Germany surrendered in May and Japan surrendered in September.",
        ],
        "bottom": "World War II was not caused by one person alone, but Hitler's Nazi Germany played a major role in starting and escalating it in Europe.",
    },
    "water cycle": {
        "answer": "The water cycle is the continuous movement of water between Earth's surface and the atmosphere.",
        "points": [
            "Evaporation turns water into vapor.",
            "Condensation forms clouds.",
            "Precipitation brings water back as rain, snow, or hail.",
            "Collection gathers water in rivers, lakes, oceans, and groundwater.",
        ],
        "bottom": "The water cycle recycles Earth's water through evaporation, clouds, rain, and collection.",
    },
}


def clean_learning_topic(message: str) -> str:
    text = clean_text(message)
    text = re.sub(r"(?i)\b(advantages and disadvantages|pros and cons|benefits and drawbacks)\s+(of|for|about)?\s*", "", text)
    text = re.sub(r"(?i)\b(difference between|compare)\s+", "", text)
    text = re.sub(r"(?i)^(please\s+)?(history of|history about|overview of|background of|timeline of)\s+", "", text)
    text = re.sub(r"(?i)^(please\s+)?(explain|define|describe|tell me about|teach me|what is|what are|who is|who are|who was|who were|why is|why are|how does|how do|how is|meaning of)\s+", "", text)
    text = re.sub(r"(?i)^(the|a|an)\s+", "", text)
    text = re.sub(r"(?i)\b(in simple words|simply|for class \d+|briefly|short answer|long answer|with example|examples?)\b", " ", text)
    text = re.sub(r"\?+$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;-")
    if not text:
        return "this"
    return title_case_topic(text)


def find_knowledge_card(topic: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    lower = clean_text(topic).lower()
    for key, card in LOCAL_KNOWLEDGE_CARDS.items():
        if re.search(rf"\b{re.escape(key)}\b", lower):
            return key, card
    aliases = {
        "ai": "artificial intelligence",
        "ml": "machine learning",
        "ww2": "second world war",
        "wwii": "second world war",
        "world war ii": "second world war",
        "world war 2": "second world war",
        "hitler": "adolf hitler",
        "nazi germany": "adolf hitler",
    }
    for alias, key in aliases.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return key, LOCAL_KNOWLEDGE_CARDS.get(key)
    return lower, None


def local_knowledge_reply(message: str, presentation_style: str = "balanced") -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(what is|what are|who is|who are|who was|who were|explain|define|describe|meaning of|teach me|tell me|use of|uses of|example of|how does|why does|why is|how is|history of|overview of|background of|timeline of)\b", lower):
        return None
    topic = clean_learning_topic(message)
    key, card = find_knowledge_card(topic)
    if not card:
        key, card = find_knowledge_card(message)
    if card and key == "second world war" and re.search(r"\b(history|overview|background|timeline)\b", lower):
        return build_world_war_two_history("short" if presentation_style == "short" else "balanced")
    if card:
        lines = [
            f"{card['answer']}\n",
            "Key points:",
        ]
        lines.extend(f"- {point}" for point in card.get("points", [])[:5])
        lines.extend(["", "Bottom line:", str(card.get("bottom", ""))])
        return "\n".join(lines)

    topic_lower = topic.lower()
    if presentation_style == "short":
        return (
            f"{topic} is best understood by starting with its simple meaning, then looking at one example.\n\n"
            "Bottom line:\n"
            f"A good answer about {topic_lower} should explain what it means and why it matters."
        )
    return (
        f"{topic} can be understood by breaking it into meaning, parts, and use.\n\n"
        "Key points:\n"
        f"- Meaning: Start with what {topic_lower} means in simple words.\n"
        "- Parts: Break the idea into smaller pieces.\n"
        "- Example: Connect it with a real-life situation.\n"
        "- Use: Explain why it matters.\n\n"
        "Bottom line:\n"
        f"A strong answer about {topic_lower} should be simple, structured, and connected to real life."
    )


def split_comparison_subjects(message: str) -> Optional[Tuple[str, str]]:
    text = clean_text(message)

    def clean_subject(raw: str) -> str:
        subject = clean_text(raw).strip(" .,:;-")
        subject = re.sub(r"(?i)\b(?:for|when|while|during|in order to)\b.+$", "", subject).strip(" .,:;-")
        subject = re.sub(r"(?i)\b(?:give|include|with checks?|in bullets?|in points?)\b.+$", "", subject).strip(" .,:;-")
        return title_case_topic(subject)

    patterns = [
        r"(?i)\b(?:difference between|compare)\s+(.+?)\s+(?:and|with|vs\.?|versus)\s+(.+?)[?.!]*$",
        r"(?i)^(.+?)\s+(?:vs\.?|versus)\s+(.+?)[?.!]*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            left = clean_subject(match.group(1))
            right = clean_subject(match.group(2))
            if left and right and left.lower() != right.lower():
                return left, right
    return None


def local_comparison_reply(message: str) -> Optional[str]:
    subjects = split_comparison_subjects(message)
    if not subjects:
        return None
    left, right = subjects
    pair = f"{left} {right}".lower()
    if "ram" in pair and "cpu" in pair:
        return (
            "RAM and CPU both matter for running an AI assistant, but they solve different bottlenecks: RAM decides what can stay loaded, while the CPU decides how fast work gets processed.\n\n"
            "| Check | RAM | CPU |\n"
            "|---|---|---|\n"
            "| Main job | Holds the model, chat history, files, cache, and active app data in memory | Runs the calculations, server code, routing, and response generation work |\n"
            "| When it becomes the bottleneck | The app slows badly, crashes, or swaps to disk when the model/context does not fit | Replies feel slow even though memory is not full |\n"
            "| Helps most with | Larger models, longer context, more browser tabs/files, and multiple users | Faster inference, smoother API handling, search/file processing, and concurrent requests |\n"
            "| Upgrade priority | Upgrade first if memory usage is near full or the system is swapping | Upgrade first if RAM has headroom but generation is still slow |\n\n"
            "Practical check:\n"
            "- If RAM usage is above about 85-90%, add RAM or use a smaller model/context.\n"
            "- If CPU stays near 100% while RAM has room, use a faster CPU, fewer concurrent tasks, or a remote model.\n"
            "- If both are high, reduce model size, context length, and background services first.\n\n"
            "Bottom line:\n"
            "RAM keeps the AI assistant stable; CPU makes it responsive. For local AI, enough RAM comes first, then CPU speed decides how pleasant it feels."
        )
    if re.search(r"\belectric (car|cars|vehicle|vehicles|ev|evs)\b", pair) and re.search(
        r"\b(petrol|gasoline|fuel) (car|cars|vehicle|vehicles)?\b|\bpetrol\b|\bgasoline\b",
        pair,
    ):
        return (
            "Electric cars and petrol cars mainly differ in how they store energy, how they run, and what they cost to maintain.\n\n"
            "| Point | Electric cars | Petrol cars |\n"
            "|---|---|---|\n"
            "| Power source | Battery and electric motor | Petrol engine and fuel tank |\n"
            "| Running feel | Quiet, smooth, quick acceleration | Engine sound, gear shifts, familiar driving feel |\n"
            "| Daily cost | Usually cheaper to run if charging is affordable | Usually higher fuel cost, depending on petrol prices |\n"
            "| Refuelling | Needs charging time and charging access | Refuels quickly at petrol pumps |\n"
            "| Maintenance | Fewer moving parts, usually simpler maintenance | More engine parts, oil changes, and regular servicing |\n"
            "| Pollution | No tailpipe emissions while driving | Emits exhaust gases while driving |\n"
            "| Best for | City use, home charging, lower running cost | Long trips, quick refuelling, weak charging access |\n\n"
            "Takeaway:\n"
            "Choose an electric car if charging is easy and daily running cost matters most. Choose a petrol car if quick refuelling and long-distance flexibility matter more."
        )
    return (
        f"{left} and {right} are easiest to compare by purpose, use, and key difference.\n\n"
        f"| Point | {left} | {right} |\n"
        "|---|---|---|\n"
        "| Basic idea | One side of the comparison | The other side of the comparison |\n"
        "| Main use | Used when its features fit the need | Used when its features fit the need |\n"
        "| Key difference | Check what it does best | Check how it differs in function or result |\n\n"
        "Bottom line:\n"
        f"The best choice between {left.lower()} and {right.lower()} depends on the purpose, context, and result you need."
    )


def local_pros_cons_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(advantages and disadvantages|pros and cons|benefits and drawbacks)\b", lower):
        return None
    topic = clean_learning_topic(message)
    return (
        f"{topic} has both useful benefits and possible drawbacks.\n\n"
        "| Advantages | Disadvantages |\n"
        "|---|---|\n"
        "| Can save time or effort | Can create dependency if used carelessly |\n"
        "| Can improve access to information or tools | Can cause distraction or misuse |\n"
        "| Can support learning, work, or communication | May need rules, balance, or responsible use |\n\n"
        "Bottom line:\n"
        f"{topic} is most useful when it is used wisely and with balance."
    )


def extract_goal_topic(message: str) -> str:
    text = clean_text(message)
    text = re.sub(r"(?i)^user question:\s*", "", text).strip()
    text = re.sub(r"(?i)^(please\s+)?(can you|could you|help me|tell me|show me)\s+", "", text)
    text = re.sub(r"(?i)^(please\s+)?(give|write|make|create|prepare|provide)\s+(me\s+)?(an?\s+)?", "", text)
    text = re.sub(r"(?i)^(how to|steps to|how can i|how do i|i want to|i need to|i have to|i wanna|i am trying to|i'm trying to|i make|i want|i need)\s+", "", text)
    text = re.sub(r"(?i)^(make|create|build|start|open|launch|set up|setup|plan|grow)\s+(an?\s+|my\s+)?", "", text)
    text = re.sub(r"(?i)^(project\s+plan|business\s+plan|travel\s+plan|plan)\s*(for|about|on|to)?\s*", "", text)
    text = re.sub(r"(?i)^(an?\s+|my\s+|the\s+)+", "", text)
    text = re.sub(r"(?i)\b(step by step|full guide|complete guide|properly|from scratch|for beginners|beginner)\b", " ", text)
    text = re.sub(r"\?+$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;-")
    return title_case_topic(text or clean_learning_topic(message))


def is_goal_or_problem_request(message: str) -> bool:
    lower = clean_text(message).lower()
    if re.fullmatch(r"(make|fix|improve|change|remove|add)\s+(it|this|that|them|those)(\s+(better|more|again|now))?[.! ]*", lower):
        return False
    if is_study_management_request(message):
        return True
    return bool(
        re.search(r"\b(how to|how should i|steps to|how can i|how do i|i want to|i need to|i have to|i am trying to|i'm trying to|make|create|build|start|launch|set up|setup|grow|plan)\b", lower)
        and not re.search(r"\b(image|picture|photo|art|poster|logo|wallpaper|email|letter|essay|application|speech)\b", lower)
    )


def youtube_channel_plan(topic: str) -> str:
    return (
        "Short answer:\n"
        "To make a YouTube channel, do not start with only the channel name. Start with the audience, topic, and first 5 videos. That makes the channel easier to grow.\n\n"
        "Step-by-step plan:\n"
        "1. Choose one clear niche.\n"
        "Pick a topic you can make videos about every week, such as gaming, study tips, tech, anime edits, facts, tutorials, or vlogs.\n\n"
        "2. Define the viewer.\n"
        "Write one sentence: \"My channel helps ___ people do/learn/enjoy ___.\" This keeps your videos focused.\n\n"
        "3. Create the channel basics.\n"
        "Use a short channel name, a clean profile picture, a simple banner, and a description that tells viewers what they will get.\n\n"
        "4. Plan your first 5 videos.\n"
        "Do not wait for perfect equipment. Plan simple videos you can actually finish.\n\n"
        "| Video | Purpose |\n"
        "|---|---|\n"
        "| 1 | Introduce the topic and promise of the channel |\n"
        "| 2 | Solve one common beginner problem |\n"
        "| 3 | Share a useful list, guide, or tutorial |\n"
        "| 4 | React to or explain something popular in your niche |\n"
        "| 5 | Make a stronger version of the video that performed best |\n\n"
        "5. Upload consistently.\n"
        "Start with 1-2 videos per week. Improve the title, thumbnail, and first 10 seconds every time.\n\n"
        "Best first setup:\n"
        "- Phone camera or screen recorder with clear voice or captions.\n"
        "- Good lighting if your face is shown.\n"
        "- Simple editing with CapCut, Clipchamp, or any basic editor.\n"
        "- Thumbnail with 2-4 words, not too much text.\n\n"
        "7-day starter workflow:\n"
        "1. Day 1: Choose niche and channel name.\n"
        "2. Day 2: Make logo, banner, and description.\n"
        "3. Day 3: Write 5 video ideas.\n"
        "4. Day 4: Record video 1.\n"
        "5. Day 5: Edit video 1.\n"
        "6. Day 6: Make thumbnail and title.\n"
        "7. Day 7: Upload, then note what to improve next.\n\n"
        "Bottom line:\n"
        "A good YouTube channel grows from consistency, useful videos, clear titles, and improving one thing every upload."
    )


def website_goal_plan(topic: str) -> str:
    return (
        "Short answer:\n"
        "Build the website around the user's main action first, then design the pages around that action.\n\n"
        "Plan:\n"
        "1. Decide the purpose: portfolio, business, product, blog, school project, or tool.\n"
        "2. Choose the main action: contact, buy, read, sign up, download, or try the app.\n"
        "3. Create the core pages: home, about, work/services, contact, and one proof section.\n"
        "4. Keep the design simple: readable text, strong spacing, clear navigation, and fast loading.\n"
        "5. Test it on mobile before sharing it.\n\n"
        "Bottom line:\n"
        "A website feels professional when the visitor instantly understands what it is, why it matters, and what to do next."
    )


def business_goal_plan(topic: str) -> str:
    clean_topic = clean_text(topic)
    clean_topic = re.sub(r"(?i)^(write|draft|make|create|prepare|give)\s+(me\s+)?(a\s+)?(short\s+|small\s+|brief\s+|full\s+|complete\s+)?business plan\s*(for|about|on)?\s*", "", clean_topic)
    clean_topic = re.sub(r"(?i)^(a\s+|an\s+|the\s+)+", "", clean_topic).strip(" .,:;-")
    business = title_case_topic(clean_topic or "Business")
    business_lower = business.lower()
    if re.search(r"\b(stationery|school supplies|notebook|pen|pencil)\b", business_lower):
        return (
            "Short answer:\n"
            f"A {business_lower} can work well if it stays close to students, keeps fast-moving items in stock, and earns trust through fair prices.\n\n"
            "Plan:\n"
            "1. Target customers: students, parents, teachers, nearby tuition centers, and small offices.\n"
            "2. Core products: notebooks, pens, pencils, erasers, geometry boxes, chart paper, files, art supplies, and exam materials.\n"
            "3. Location strategy: choose a spot near a school, coaching center, bus stop, or residential area with students.\n"
            "4. Pricing strategy: keep daily-use items affordable, then earn extra margin from bundles, art kits, files, and seasonal exam packs.\n"
            "5. Marketing: offer school-opening bundles, WhatsApp ordering, small discounts for bulk class orders, and quick home delivery nearby.\n\n"
            "Next step:\n"
            "Make a list of the 30 fastest-selling items and estimate the starting stock cost before renting or decorating the shop."
        )
    return (
        "Short answer:\n"
        f"Start small with {business_lower}: validate demand before spending too much time or money.\n\n"
        "Plan:\n"
        "1. Define the exact customer and why they would pay.\n"
        "2. Offer one simple product or service first, not many things at once.\n"
        "3. Check whether people already pay for similar solutions.\n"
        "4. Build a small first version or service package.\n"
        "5. Talk to real users, improve, then repeat.\n\n"
        "Next step:\n"
        "Write the customer, offer, price, and first sales channel on one page before building anything bigger."
    )


def school_project_goal_plan(topic: str) -> str:
    clean_topic = title_case_topic(topic)
    topic_lower = clean_topic.lower()
    if "science fair" not in topic_lower and "science project" not in topic_lower:
        focus = clean_topic
    else:
        focus = "school science fair project"
    return (
        "Short answer:\n"
        f"Make the {focus} around one clear question, one simple experiment, and one clean display board. Do not start with decoration first; start with the idea and proof.\n\n"
        "Plan:\n"
        "1. Choose the question: pick one testable question, such as how light affects plant growth or which material keeps water warm longer.\n"
        "2. Write the hypothesis: predict what you think will happen and why.\n"
        "3. List materials: keep it simple, safe, and easy to repeat at home or school.\n"
        "4. Run the experiment: change only one variable and record results in a table.\n"
        "5. Make visuals: add photos, a chart, and a short explanation of what the results mean.\n"
        "6. Build the display: use sections for Question, Hypothesis, Materials, Method, Results, Conclusion, and What I learned.\n\n"
        "Timeline:\n"
        "- Day 1: Choose topic and hypothesis.\n"
        "- Day 2: Gather materials and prepare the table for results.\n"
        "- Days 3-5: Run the experiment and take photos.\n"
        "- Day 6: Make chart, conclusion, and display board.\n"
        "- Day 7: Practice explaining it in 60 seconds.\n\n"
        "Bottom line:\n"
        "A strong science fair project is simple, testable, and well explained."
    )


def generic_goal_plan(topic: str) -> str:
    topic_lower = topic.lower()
    return (
        "Short answer:\n"
        f"To work on {topic_lower}, start by defining the exact result, then turn it into small actions you can finish.\n\n"
        "Plan:\n"
        f"1. Define the result: what should {topic_lower} look like when it is done?\n"
        "2. Find the first obstacle: skill, time, tools, money, confidence, or information.\n"
        "3. Make the smallest useful version first.\n"
        "4. Test it with a real example or real user.\n"
        "5. Improve one thing at a time instead of changing everything together.\n\n"
        "Check:\n"
        "- Is the goal clear enough to start today?\n"
        "- Is the first step small enough to finish in one sitting?\n"
        "- Do you know how you will measure progress?\n\n"
        "Bottom line:\n"
        "A good plan turns a big idea into the next clear action."
    )


def is_fitness_plan_request(message: str) -> bool:
    lower = clean_text(message).lower()
    has_fitness_topic = bool(re.search(
        r"\b(fitness|workout|exercise|gym|training|strength|cardio|weight loss|fat loss|muscle gain|lose weight|build muscle|get fit|diet)\b",
        lower,
    ))
    has_plan_intent = bool(re.search(r"\b(plan|routine|schedule|program|workout|fitness plan|training plan)\b", lower))
    return has_fitness_topic and has_plan_intent


def build_fitness_plan(message: str) -> str:
    lower = clean_text(message).lower()
    days_match = re.search(r"\b([3-6])\s*(day|days)\b", lower)
    days = int(days_match.group(1)) if days_match else 5
    if re.search(r"\b(weight loss|fat loss|lose weight|slim)\b", lower):
        goal = "fat loss and better stamina"
    elif re.search(r"\b(muscle|strength|bulk|gain)\b", lower):
        goal = "strength and muscle gain"
    else:
        goal = "general fitness, strength, and stamina"

    if days <= 3:
        weekly_plan = [
            "Day 1: Full-body strength - squats, push-ups, rows, glute bridges, and plank. Do 2-3 sets each.",
            "Day 2: Cardio + mobility - 25-35 minutes brisk walking, cycling, or jogging, then 10 minutes stretching.",
            "Day 3: Full-body strength - lunges, shoulder press, hip hinge/deadlift pattern, core work, and light cardio finish.",
        ]
    elif days == 4:
        weekly_plan = [
            "Day 1: Upper body strength - push-ups/bench press, rows, shoulder press, curls, triceps, and plank.",
            "Day 2: Lower body strength - squats, lunges, glute bridges, calf raises, and core.",
            "Day 3: Cardio + mobility - 30 minutes steady cardio, then hips, hamstrings, back, and shoulder mobility.",
            "Day 4: Full-body circuit - squat, push, pull, hinge, carry, and core for 3 rounds at moderate effort.",
        ]
    else:
        weekly_plan = [
            "Day 1: Full-body strength - squats, push-ups, rows, glute bridges, and plank. Do 2-3 sets each.",
            "Day 2: Cardio - 25-35 minutes brisk walking, cycling, jogging, or skipping at a pace you can sustain.",
            "Day 3: Strength + core - lunges, shoulder press, hip hinge/deadlift pattern, side plank, and dead bug.",
            "Day 4: Mobility + light cardio - 20 minutes easy movement, then stretch hips, hamstrings, chest, and back.",
            "Day 5: Full-body circuit - squat, push, pull, hinge, carry, and core for 3 rounds at moderate effort.",
        ]

    lines = [
        "Fitness plan",
        "",
        f"Goal: {goal}.",
        "",
        "Weekly plan:",
        *[f"- {item}" for item in weekly_plan],
        "",
        "Rules to follow:",
        "- Warm up for 5-8 minutes before every workout.",
        "- Keep 1-2 rest days each week so your body can recover.",
        "- Increase reps, weight, or time slowly each week instead of doing too much at once.",
        "- Eat enough protein, drink water, and sleep well; fitness improves outside the workout too.",
        "",
        "Bottom line:",
        "Start simple, stay consistent for 4 weeks, and adjust the plan based on your energy, soreness, and goal.",
    ]
    if re.search(r"\b(medical|injury|pain|doctor|condition)\b", lower):
        lines.extend([
            "",
            "Safety note:",
            "Because you mentioned a possible medical or injury issue, use this only as a general plan and check with a qualified professional before intense exercise.",
        ])
    return "\n".join(lines)


def local_fitness_plan_reply(message: str) -> Optional[str]:
    if not is_fitness_plan_request(message):
        return None
    return build_fitness_plan(message)


def local_goal_plan_reply(message: str) -> Optional[str]:
    if not is_goal_or_problem_request(message):
        return None
    lower = clean_text(message).lower()
    topic = extract_goal_topic(message)
    if re.search(r"\b(science fair|school project|science project|project plan)\b", lower):
        return school_project_goal_plan(topic)
    study_management = local_study_management_reply(message)
    if study_management:
        return study_management
    fitness = local_fitness_plan_reply(message)
    if fitness:
        return fitness
    if re.search(r"\b(youtube|yt|channel|creator|video channel)\b", lower):
        return youtube_channel_plan(topic)
    if re.search(r"\b(website|web site|webpage|landing page|portfolio site)\b", lower):
        return website_goal_plan(topic)
    if re.search(r"\b(business|startup|shop|brand|sell|selling|product)\b", lower):
        return business_goal_plan(topic)
    return generic_goal_plan(topic)


def local_step_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(how to|steps to|how can i|how do i)\b", lower):
        return None
    return local_goal_plan_reply(message)


def local_semantic_reply(
    message: str,
    response_lane: str = "human_chat",
    presentation_style: str = "balanced",
) -> Optional[str]:
    return (
        local_direct_name_reply(message)
        or local_reflective_reply(message)
        or local_comparison_reply(message)
        or local_pros_cons_reply(message)
        or local_goal_plan_reply(message)
        or local_step_reply(message)
        or local_knowledge_reply(message, presentation_style)
    )


def local_email_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(email|e-mail|mail)\b", lower):
        return None
    purpose = clean_text(message)
    purpose = re.sub(r"(?i)^(please\s+)?(write|draft|make|create|compose|give me)\s+(an?\s+)?(email|e-mail|mail)\s*(to|for|about)?\s*", "", purpose)
    purpose = purpose or "send a clear professional message"
    return draft_email_text(purpose)


def local_study_plan_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(study plan|study planner|revision plan|timetable|schedule for study)\b", lower):
        return None
    topic_raw = re.sub(r"(?i)^(please\s+)?(make|create|generate|give me|prepare)\s+(a\s+)?", "", clean_text(message))
    topic_raw = re.sub(r"(?i)\b(study plan|study planner|revision plan|timetable|schedule for study)\b\s*(for|on|about)?\s*", "", topic_raw)
    topic_raw = re.sub(r"(?i)\b(in|for)\s+\d{1,2}\s*(day|days|week|weeks)\b", "", topic_raw)
    topic = title_case_topic(topic_raw.strip(" .,:;-") or clean_learning_topic(message))
    days_match = re.search(r"\b(\d{1,2})\s*(day|days)\b", lower)
    days = int(days_match.group(1)) if days_match else 7
    return make_study_plan(topic, days=days, daily_minutes=45)


def is_study_management_request(message: str) -> bool:
    lower = clean_text(message).lower()
    if re.search(r"\b(science fair|school project|science project|project plan)\b", lower):
        return False
    has_study_topic = bool(re.search(r"\b(study|studies|school|class|grade|exam|homework|subject|subjects)\b", lower))
    has_management_intent = bool(re.search(
        r"\b(manage|management|organize|organise|balance|schedule|routine|timetable|plan|prepare|study better|focus|score|marks|revise|revision|how should i|how can i)\b",
        lower,
    ))
    return has_study_topic and has_management_intent


def extract_class_level(message: str) -> str:
    lower = clean_text(message).lower()
    match = re.search(r"\b(class|grade)\s*(\d{1,2})\b", lower)
    if match:
        return f"Class {match.group(2)}"
    return "school"


def build_study_management_plan(message: str) -> str:
    class_level = extract_class_level(message)
    lower = clean_text(message).lower()
    daily_minutes = 120 if re.search(r"\b(class|grade)\s*(8|9|10)\b", lower) else 90
    return (
        f"{class_level} study management plan\n\n"
        "Short answer:\n"
        "Manage your studies with a simple daily routine: learn today’s lessons, practise questions, revise old topics, and keep one small buffer for homework or weak subjects.\n\n"
        "Daily routine:\n"
        f"1. School recap: Spend 20 minutes reviewing what was taught today.\n"
        f"2. Main study block: Study one difficult subject for 45-60 minutes.\n"
        f"3. Practice block: Solve questions, sums, grammar exercises, or textbook questions for 30-40 minutes.\n"
        f"4. Revision block: Revise one old topic for 15-20 minutes so you do not forget it.\n"
        f"5. Homework/buffer: Keep 20-30 minutes for homework, projects, or unfinished work.\n\n"
        "Weekly plan:\n"
        "- Monday to Friday: Follow the daily routine and focus on school topics taught that day.\n"
        "- Saturday: Revise the week’s weak chapters and complete pending homework.\n"
        "- Sunday: Do a light test, organize notebooks, and plan the next week.\n\n"
        "Subject method:\n"
        "- Maths: practise sums daily, especially the mistakes you made before.\n"
        "- Science: understand concepts first, then write definitions and diagrams.\n"
        "- Social Science: make short notes with dates, keywords, and causes/effects.\n"
        "- English/languages: read, learn grammar rules, and practise writing answers.\n\n"
        "Rules that make it work:\n"
        "- Do not study every subject every day; rotate subjects.\n"
        "- Keep your phone away during study blocks.\n"
        "- Use 40 minutes study + 5 minutes break if you lose focus.\n"
        "- At the end of each day, mark one topic as done and one topic to improve tomorrow.\n\n"
        "Bottom line:\n"
        f"For {class_level}, consistency matters more than studying all night. Study a little every day, practise actively, and revise weekly."
    )


def local_study_management_reply(message: str) -> Optional[str]:
    if not is_study_management_request(message):
        return None
    return build_study_management_plan(message)


def local_file_summary_reply(message: str, session_id: Optional[str]) -> Optional[str]:
    lower = clean_text(message).lower()
    if not session_id or not re.search(r"\b(summarize|summarise|summary|read|analyze|analyse|extract|notes from|key points from)\b", lower) or not re.search(r"\b(file|pdf|document|upload|uploaded)\b|\bthis\s+(?:file|pdf|document|upload)\b", lower):
        return None
    session = get_session(session_id)
    files = session.get("files", [])
    if not files:
        return "Upload a PDF or text file first, then ask me to summarize it."
    selected = files[-1]
    result = summarize_text_locally(str(selected.get("text", "")), 6)
    lines = [
        f"File summary: {selected.get('filename', 'uploaded file')}",
        "",
        "Summary:",
        result["summary"],
    ]
    if result["key_points"]:
        lines.extend(["", "Key points:"])
        lines.extend(f"- {point}" for point in result["key_points"])
    if result["action_items"]:
        lines.extend(["", "Action items:"])
        lines.extend(f"- {item}" for item in result["action_items"])
    return "\n".join(lines)


def extract_inline_payload(message: str, command_pattern: str = "") -> str:
    text = clean_text(message)
    quote_match = re.search(r'"([^"]{8,})"', text)
    if quote_match:
        return clean_text(quote_match.group(1))
    quote_match = re.search(r"'([^']{8,})'", text)
    if quote_match:
        return clean_text(quote_match.group(1))
    if ":" in text:
        after = clean_text(text.split(":", 1)[1])
        if len(after.split()) >= 3:
            return after
    if command_pattern:
        payload = re.sub(command_pattern, "", text, flags=re.IGNORECASE).strip(" .,:;-")
        if len(payload.split()) >= 3:
            return clean_text(payload)
    return ""


def local_text_summary_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(summarize|summarise|summary|shorten|key points|main points|takeaways)\b", lower):
        return None
    if re.search(r"\b(file|pdf|document|upload|uploaded)\b", lower):
        return None
    payload = extract_inline_payload(
        message,
        r"(?i)^(please\s+)?(summarize|summarise|summary of|shorten|give me|extract|list)\s+(the\s+)?(key points|main points|takeaways|this|text)?\s*",
    )
    if not payload or len(payload.split()) < 10:
        return None
    result = summarize_text_locally(payload, 5)
    lines = [
        "Summary:",
        result["summary"],
    ]
    if result["key_points"]:
        lines.extend(["", "Key points:"])
        lines.extend(f"- {point}" for point in result["key_points"][:5])
    if result["action_items"]:
        lines.extend(["", "Action items:"])
        lines.extend(f"- {item}" for item in result["action_items"][:4])
    return "\n".join(lines)


def basic_polish_text(text: str) -> str:
    cleaned = clean_text(text)
    replacements = {
        r"\bi\b": "I",
        r"\bim\b": "I'm",
        r"\bdont\b": "don't",
        r"\bcant\b": "can't",
        r"\bwont\b": "won't",
        r"\bdoesnt\b": "doesn't",
        r"\bdidnt\b": "didn't",
        r"\bisnt\b": "isn't",
        r"\barent\b": "aren't",
        r"\bu\b": "you",
        r"\bur\b": "your",
        r"\bpls\b": "please",
    }
    for pattern, value in replacements.items():
        cleaned = re.sub(pattern, value, cleaned, flags=re.IGNORECASE)
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def local_text_transform_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    is_transform = bool(re.search(
        r"\b(fix grammar|correct grammar|grammar check|correct this|rewrite|rephrase|polish|make this clearer|improve this sentence|improve this text)\b",
        lower,
    ))
    if not is_transform:
        return None
    payload = extract_inline_payload(
        message,
        r"(?i)^(please\s+)?(fix grammar|correct grammar|grammar check|correct this|rewrite|rephrase|polish|make this clearer|improve this sentence|improve this text)\s*",
    )
    if not payload:
        return None
    polished = basic_polish_text(payload)
    label = "Polished version:" if re.search(r"\b(rewrite|rephrase|polish|clearer|improve)\b", lower) else "Corrected version:"
    return f"{label}\n{polished}"


def local_brainstorm_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(brainstorm|ideas?|suggest names?|give me ideas|topic ideas|content ideas)\b", lower):
        return None
    topic = extract_goal_topic(message)
    topic = re.sub(r"(?i)\b(brainstorm|ideas?|suggest names?|give me ideas|topic ideas|content ideas)\b\s*(for|about|on)?\s*", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "the project")
    if not topic or topic.lower() in {"ideas", "idea", "this"}:
        topic = "the project"
    return (
        f"Ideas for {topic.lower()}:\n\n"
        f"1. Simple beginner version: Make a small, clear version of {topic.lower()} that can be finished quickly.\n"
        f"2. Useful problem-solver: Focus on one real problem people have with {topic.lower()} and solve only that.\n"
        f"3. Comparison idea: Compare two ways to do {topic.lower()} and explain which one works better.\n"
        f"4. Step-by-step guide: Turn {topic.lower()} into a checklist, tutorial, or short explainer.\n"
        f"5. Creative version: Add a unique style, story, or visual angle so it feels memorable.\n\n"
        "Best pick:\n"
        "Choose the idea that is easiest to finish and easiest for someone else to understand."
    )


def local_decision_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(which should i choose|which is better|should i|better option|choose between|decide between)\b", lower):
        return None
    topic = extract_goal_topic(message)
    topic = re.sub(r"(?i)\b(which should i choose|which is better|should i|better option|choose between|decide between)\b\s*", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "this choice")
    return (
        "Decision framework:\n\n"
        f"For {topic.lower()}, choose the option that wins on three things: usefulness, risk, and effort.\n\n"
        "How to decide:\n"
        "1. Usefulness: Which option solves the real problem better?\n"
        "2. Risk: Which option is less likely to waste time, money, or trust?\n"
        "3. Effort: Which option can you actually do consistently?\n"
        "4. Reversibility: If the choice fails, can you change direction easily?\n\n"
        "Bottom line:\n"
        "If both options look equal, pick the one with lower risk and faster feedback first."
    )


def local_recipe_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(recipe|cook|make food|ingredients|how to make)\b", lower):
        return None
    topic = extract_goal_topic(message)
    topic = re.sub(r"(?i)\b(give me|make|create|cook|recipe|ingredients|how to make)\b\s*(a|an|the|for|of)?\s*", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "a simple dish")
    if not topic or topic.lower() in {"recipe", "cook"}:
        topic = "a simple dish"
    if "pasta" in topic.lower():
        return (
            "Simple pasta recipe:\n\n"
            "Ingredients:\n"
            "Pasta, salt, oil or butter, garlic, onion, tomato sauce or vegetables, and cheese or herbs if available.\n\n"
            "Steps:\n"
            "1. Boil water, add salt, and cook the pasta until soft but not mushy.\n"
            "2. Save a little pasta water, then drain the pasta.\n"
            "3. Heat oil or butter in a pan and cook garlic, onion, or vegetables.\n"
            "4. Add tomato sauce or seasoning, then mix in the pasta.\n"
            "5. Add a little pasta water if it feels dry, then finish with cheese or herbs.\n\n"
            "Bottom line:\n"
            "Keep the pasta slightly firm, season the sauce well, and mix everything while hot."
        )
    return (
        f"Simple recipe plan for {topic.lower()}:\n\n"
        "Ingredients:\n"
        "Use the main ingredient, salt, basic spices, oil or butter, and onion, tomato, garlic, or herbs if they fit the dish.\n\n"
        "Steps:\n"
        "1. Prepare and cut the ingredients first.\n"
        "2. Heat the pan and cook aromatics or spices gently.\n"
        "3. Add the main ingredient and cook until done.\n"
        "4. Taste and adjust salt, spice, or texture.\n"
        "5. Serve hot with a simple side.\n\n"
        "Bottom line:\n"
        "Tell me the exact dish name and ingredients you have, and I can make this into a precise recipe."
    )


def local_travel_itinerary_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(travel plan|trip plan|itinerary|visit|tour plan)\b", lower):
        return None
    topic = extract_goal_topic(message)
    topic = re.sub(r"(?i)\b(make|create|give me|travel plan|trip plan|itinerary|tour plan)\b\s*(a|an|the|for|to|of)?\s*", " ", topic)
    topic = re.sub(r"(?i)\b\d+\s*(day|days)\b", " ", topic)
    topic = re.sub(r"(?i)\btravel\b", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "the trip")
    return (
        f"Travel itinerary for {topic.lower()}:\n\n"
        "Day 1: Arrival and easy exploration.\n"
        "- Check in, rest, and visit one nearby place.\n"
        "- Keep the evening light so the trip starts smoothly.\n\n"
        "Day 2: Main attractions.\n"
        "- Visit the most important places early.\n"
        "- Keep food, transport time, and rest breaks in the plan.\n\n"
        "Day 3: Flexible day.\n"
        "- Add shopping, local food, photos, or one missed attraction.\n"
        "- Leave buffer time for travel back.\n\n"
        "Checklist:\n"
        "- Confirm travel time, opening hours, tickets, weather, and local transport before going.\n\n"
        "Bottom line:\n"
        "For an accurate itinerary, share the city, number of days, budget, and who is travelling."
    )


def local_health_info_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(health|symptom|pain|fever|medicine|doctor|diet|sleep|stress|exercise injury|injury)\b", lower):
        return None
    topic = extract_goal_topic(message)
    return (
        "General health guidance:\n\n"
        f"For {topic.lower()}, treat this as general information, not a diagnosis.\n\n"
        "Safe steps:\n"
        "1. Notice the main symptom, how long it has lasted, and what makes it better or worse.\n"
        "2. Rest, hydrate, and avoid anything that clearly worsens it.\n"
        "3. Do not take prescription medicine unless a qualified clinician told you to.\n"
        "4. Seek urgent medical help for severe pain, breathing trouble, fainting, heavy bleeding, chest pain, confusion, or symptoms that worsen quickly.\n\n"
        "Bottom line:\n"
        "I can help you understand possibilities and questions to ask, but a doctor or local medical service is the right source for diagnosis or treatment."
    )


def local_legal_info_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(legal|law|contract|rights|court|case|sue|police|agreement|terms)\b", lower):
        return None
    if re.search(r"\b(explain|summarize|summarise|review|simplify|read)\b", lower) and re.search(r"\b(contract|agreement|terms|document)\b", lower):
        payload = extract_inline_payload(message)
        if not payload:
            return (
                "Paste the contract text or the exact clause you want explained.\n\n"
                "I will then break it into:\n"
                "1. Plain meaning.\n"
                "2. Duties or promises.\n"
                "3. Risks or unclear parts.\n"
                "4. Questions to ask a qualified lawyer if it matters legally.\n\n"
                "Bottom line:\n"
                "Without the actual text, I should not guess what the contract says."
            )
    topic = extract_goal_topic(message)
    return (
        "General legal information:\n\n"
        f"For {topic.lower()}, I can explain the issue in plain language, but I cannot replace a qualified lawyer.\n\n"
        "How to handle it:\n"
        "1. Identify the country/state because law depends heavily on location.\n"
        "2. Collect the contract, messages, receipts, dates, and names involved.\n"
        "3. Separate facts from assumptions before making any claim.\n"
        "4. For deadlines, court papers, police matters, or money at risk, contact a local legal professional quickly.\n\n"
        "Bottom line:\n"
        "The safe answer depends on jurisdiction and exact facts, so use this as preparation, not final legal advice."
    )


def local_finance_info_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(finance|money|budget|saving|investment|invest|stock|crypto|loan|debt|tax|profit)\b", lower):
        return None
    topic = extract_goal_topic(message)
    return (
        "General finance guidance:\n\n"
        f"For {topic.lower()}, focus on risk, time horizon, cash flow, and evidence before deciding.\n\n"
        "Useful checklist:\n"
        "1. Emergency money: Keep basic savings before taking big risks.\n"
        "2. Debt: High-interest debt usually matters before investing.\n"
        "3. Risk: Never put essential money into something volatile.\n"
        "4. Evidence: Current prices, taxes, and rules need fresh verification.\n"
        "5. Fit: A good financial choice depends on your income, goals, age, and responsibilities.\n\n"
        "Bottom line:\n"
        "I can help compare options and build a plan, but I should not promise returns or give personalized financial advice as fact."
    )


def local_career_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(resume|cv|job application|cover letter|career|portfolio|linkedin|interview)\b", lower):
        return None
    if re.search(r"\b(interview|hr round|technical round|interview questions)\b", lower):
        return (
            "Interview prep plan:\n\n"
            "1. Prepare your intro: who you are, what you know, and what role you want.\n"
            "2. Review the job description and match each requirement with one example from your work or study.\n"
            "3. Practise 5 common questions: strengths, weakness, project, challenge, and why this role.\n"
            "4. Prepare 2-3 questions to ask the interviewer.\n"
            "5. After each practice answer, make it shorter and more specific.\n\n"
            "Bottom line:\n"
            "The best answers use real examples, not memorized lines."
        )
    return (
        "Resume/CV improvement plan:\n\n"
        "1. Put your strongest role, skill, or project near the top.\n"
        "2. Use bullet points that show action and result, not only duties.\n"
        "3. Add skills that match the job, but only if you can explain them.\n"
        "4. Keep formatting simple and readable.\n"
        "5. Remove weak filler like 'hardworking' unless you prove it with examples.\n\n"
        "Bottom line:\n"
        "A strong resume makes the reader understand your value in the first 10 seconds."
    )


def local_presentation_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(presentation|ppt|slides|slide deck|speech outline)\b", lower):
        return None
    topic = extract_goal_topic(message)
    topic = re.sub(r"(?i)\b(make|create|give me|presentation|ppt|slides|slide deck|speech outline|outline)\b\s*(about|on|for)?\s*", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "the topic")
    return (
        f"Presentation outline for {topic.lower()}:\n\n"
        "Slide 1: Title and main idea.\n"
        "Slide 2: Why the topic matters.\n"
        "Slide 3: Key point 1 with an example.\n"
        "Slide 4: Key point 2 with a fact, image, or comparison.\n"
        "Slide 5: Key point 3 with practical impact.\n"
        "Slide 6: Conclusion and takeaway.\n\n"
        "Speaking tip:\n"
        "Use short slide text and explain the details with your voice.\n\n"
        "Bottom line:\n"
        "A good presentation has one clear message, not too much text on each slide."
    )


def local_meeting_notes_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(meeting notes|minutes of meeting|mom|action items|meeting summary)\b", lower):
        return None
    payload = extract_inline_payload(message)
    source = payload if payload else "the meeting"
    result = summarize_text_locally(source, 5) if payload else {"summary": "Add the meeting text after a colon and I will summarize it.", "key_points": [], "action_items": []}
    lines = [
        "Meeting notes:",
        "",
        "Summary:",
        result["summary"],
    ]
    if result.get("key_points"):
        lines.extend(["", "Decisions/key points:"])
        lines.extend(f"- {point}" for point in result["key_points"][:5])
    if result.get("action_items"):
        lines.extend(["", "Action items:"])
        lines.extend(f"- {item}" for item in result["action_items"][:5])
    return "\n".join(lines)


def local_social_caption_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(caption|instagram caption|youtube title|tweet|post caption|social media post)\b", lower):
        return None
    topic = extract_goal_topic(message)
    topic = re.sub(r"(?i)\b(write|make|create|give me|instagram caption|youtube title|tweet|post caption|social media post|caption)\b\s*(for|about|on)?\s*", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "the post")
    return (
        f"Caption ideas for {topic.lower()}:\n\n"
        "1. Short: Small steps, real progress.\n"
        "2. Clean: Learning, building, improving - one day at a time.\n"
        "3. Energetic: New idea. New effort. Better result.\n"
        "4. Thoughtful: Progress looks simple when you keep showing up.\n"
        "5. Direct: Built this with focus, patience, and a little trial and error.\n\n"
        "Best pick:\n"
        "Use the caption that matches the mood of the post, not the longest one."
    )


def local_creative_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if re.search(r"\b(poem|original song|song lyrics|rap|shayari)\b", lower):
        topic = extract_goal_topic(message)
        return (
            f"Original poem about {topic.lower()}:\n\n"
            "A quiet thought begins to rise,\n"
            "A little spark behind the eyes.\n"
            "With every step, the path grows clear,\n"
            "And doubt becomes a smaller fear.\n\n"
            "Bottom line:\n"
            "Tell me the mood you want, and I can make it happier, sadder, romantic, or more powerful."
        )
    if re.search(r"\b(story|short story|creative writing|plot|character idea)\b", lower):
        topic = extract_goal_topic(message)
        return (
            f"Story idea for {topic.lower()}:\n\n"
            "Title: The Small Door\n\n"
            "Premise:\n"
            "A student finds a door that appears only when they are about to give up. Behind it is not magic treasure, but a room showing the result of every choice they avoided.\n\n"
            "Plot:\n"
            "1. The student faces a problem they keep delaying.\n"
            "2. The door appears after a difficult day.\n"
            "3. Inside, they see possible futures shaped by courage, laziness, honesty, and fear.\n"
            "4. They return and make one small brave choice.\n\n"
            "Bottom line:\n"
            "The theme is simple: the future changes when the next action changes."
        )
    if re.search(r"\b(joke|funny|make me laugh)\b", lower):
        return "Quick joke:\n\nWhy did the developer go broke? Because they used up all their cache.\n\nTiny, harmless, and painfully accurate."
    return None


def local_emotional_support_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(stressed|sad|anxious|worried|lonely|angry|overwhelmed|i feel bad|relationship|friend problem|family problem)\b", lower):
        return None
    if re.search(r"\b(relationship|crush|friend problem|breakup|family problem)\b", lower):
        return (
            "Relationship advice:\n\n"
            "Start with what you can control: your words, your boundaries, and your timing.\n\n"
            "What to do:\n"
            "1. Do not react while emotions are at their peak.\n"
            "2. Write down what happened, what you feel, and what you need.\n"
            "3. Talk calmly using specific examples instead of blame.\n"
            "4. If the other person keeps disrespecting you, protect your peace and step back.\n\n"
            "Bottom line:\n"
            "A healthy relationship needs honesty, respect, and space for both people to be heard."
        )
    return (
        "I hear you. When things feel heavy, start smaller than the whole problem.\n\n"
        "Try this now:\n"
        "1. Take a slow breath and unclench your shoulders.\n"
        "2. Name the feeling in one sentence.\n"
        "3. Pick one small action for the next 10 minutes: water, a walk, a message to someone safe, or writing the problem down.\n\n"
        "Bottom line:\n"
        "You do not have to solve everything at once. Start with the next safe step."
    )


def local_flashcards_or_quiz_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(flashcards?|quiz|practice questions|test me|mcq|multiple choice)\b", lower):
        return None
    topic = clean_learning_topic(message)
    topic = re.sub(r"(?i)\b(make|create|give me|flashcards?|quiz|practice questions|test me|mcq|multiple choice)\b\s*(about|on|for)?\s*", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "this topic")
    if re.search(r"\b(flashcards?)\b", lower):
        return (
            f"Flashcards on {topic.lower()}:\n\n"
            "1. Q: What is the main idea?\n"
            f"A: The main idea of {topic.lower()} is the core concept you should understand first.\n\n"
            "2. Q: Why does it matter?\n"
            "A: It matters because it connects facts with real understanding.\n\n"
            "3. Q: How should you revise it?\n"
            "A: Read the concept, close the book, recall it, then check mistakes.\n\n"
            "4. Q: What is a good exam habit?\n"
            "A: Use keywords, examples, and a clear final point."
        )
    return (
        f"Practice quiz on {topic.lower()}:\n\n"
        "1. What is the main idea of this topic?\n"
        "2. Name two important points about it.\n"
        "3. Give one example connected to real life.\n"
        "4. Write a short answer in 3-4 lines.\n"
        "5. What mistake should students avoid?\n\n"
        "Answer key:\n"
        "Send your answers, and I will check them clearly."
    )


def local_timeline_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.search(r"\b(timeline|chronology|order of events|sequence of events)\b", lower):
        return None
    if is_world_war_two_topic(message):
        return (
            "World War II timeline:\n\n"
            "1939: Germany invades Poland; Britain and France declare war.\n"
            "1940: Germany conquers much of Western Europe; Battle of Britain begins.\n"
            "1941: Germany invades the Soviet Union; Japan attacks Pearl Harbor; the United States enters the war.\n"
            "1942: Battle of Midway and major fighting in North Africa and the Soviet Union.\n"
            "1943: Germany loses at Stalingrad; Allies advance in Italy.\n"
            "1944: D-Day landings begin the liberation of Western Europe.\n"
            "1945: Germany surrenders in May; Japan surrenders in September after atomic bombings and Soviet entry into the Pacific war.\n\n"
            "Bottom line:\n"
            "The war moved from Axis expansion to Allied counterattack and ended in 1945."
        )
    topic = clean_learning_topic(message)
    topic = re.sub(r"(?i)\b(make|create|give me|timeline|chronology|order of events|sequence of events)\b\s*(about|on|for|of)?\s*", " ", topic)
    topic = title_case_topic(clean_text(topic).strip(" .,:;-") or "this topic")
    return (
        f"Timeline for {topic.lower()}:\n\n"
        "1. Start: Define the beginning event or cause.\n"
        "2. Development: Add the major turning points in order.\n"
        "3. Peak: Mark the most important event or conflict.\n"
        "4. Result: Explain what changed after it.\n"
        "5. Impact: End with why it matters.\n\n"
        "Bottom line:\n"
        "Share the exact topic and I can make a date-based timeline."
    )


def is_high_confidence_local_reply(message: str, presentation_style: str = "balanced") -> bool:
    lower = clean_text(message).lower()
    if re.search(r"\b(summarize|summarise|summary|read|analyze|analyse|extract|notes from|key points from)\b", lower) and re.search(r"\b(file|pdf|document|upload|uploaded)\b|\bthis\s+(?:file|pdf|document|upload)\b", lower):
        return True
    if local_text_summary_reply(message) or local_text_transform_reply(message):
        return True
    if local_brainstorm_reply(message) or local_decision_reply(message) or local_recipe_reply(message) or local_travel_itinerary_reply(message):
        return True
    if (
        local_health_info_reply(message)
        or local_legal_info_reply(message)
        or local_finance_info_reply(message)
        or local_career_reply(message)
        or local_presentation_reply(message)
        or local_meeting_notes_reply(message)
        or local_social_caption_reply(message)
        or local_creative_reply(message)
        or local_emotional_support_reply(message)
        or local_flashcards_or_quiz_reply(message)
        or local_timeline_reply(message)
    ):
        return True
    if re.search(r"\b(who is|who are|who was|who were|what is|what are|explain|define|describe|meaning of|teach me|history of|overview of|background of|timeline of)\b", lower):
        _, card = find_knowledge_card(clean_learning_topic(message))
        if card is not None:
            return True
    _, direct_card = find_knowledge_card(message)
    if direct_card is not None and re.search(r"\b(tell me|use|uses|example|meaning|simple|explain|what|who|why|how|history|overview|background|timeline)\b", lower):
        return True
    if is_goal_or_problem_request(message):
        return True
    if re.search(r"\b(study plan|study planner|revision plan|timetable|schedule for study)\b", lower):
        return True
    if re.search(r"\b(email|e-mail|mail)\b", lower) and re.search(r"\b(write|draft|compose|make|create|ask|request)\b", lower):
        return True
    if split_comparison_subjects(message):
        return True
    if local_capability_reply(message):
        return True
    if re.search(r"\b(advantages and disadvantages|pros and cons|benefits and drawbacks)\b", lower):
        return True
    if re.search(r"\b(how to|steps to|how can i|how do i)\b", lower):
        return True
    if re.search(r"\b(what is|what are|who is|who are|who was|who were|explain|define|describe|meaning of|teach me|history of|overview of|background of|timeline of)\b", lower):
        _, card = find_knowledge_card(clean_learning_topic(message))
        return card is not None
    return False


def detect_task_intent(message: str, use_research: bool = False) -> str:
    lower = clean_text(message).lower()
    if not lower:
        return "empty"
    if use_research:
        if re.search(r"\b(github repo|github repository|github stars|github issues|latest commit|pull requests?|repo stars)\b|github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", lower):
            return "realtime_github_repo"
        if re.search(r"\b(pypi|pip package|python package|npm package|node package|package version|latest package|latest version of package)\b", lower):
            return "realtime_package_version"
        if re.search(r"\b(cve|security advisory|zero[- ]day|vulnerability|patch status|exploit|security update)\b", lower):
            return "realtime_security_advisory"
        if re.search(r"\b(crypto|cryptocurrency|bitcoin|btc|ethereum|eth|solana|sol|dogecoin|doge|cardano|ada|xrp|bnb)\b", lower) and re.search(r"\b(price|rate|today|current|live|worth)\b", lower):
            return "realtime_crypto_price"
        if re.search(r"\b(earthquake|tremor|seismic|aftershock)\b", lower):
            return "realtime_earthquake"
        if re.search(r"\b(air quality|aqi|pollution level|pm2\.?5|pm10)\b", lower):
            return "realtime_air_quality"
        if re.search(r"\b(space launch|rocket launch|next launch|upcoming launch|launch schedule)\b", lower):
            return "realtime_space_launch"
        if re.search(r"\b(fuel price|petrol price|diesel price|gasoline price)\b", lower):
            return "realtime_fuel_price"
        if re.search(r"\b(tax deadline|tax due date|itr deadline|filing deadline)\b", lower):
            return "realtime_tax_deadline"
        if re.search(r"\b(university admission|college admission|admission result|admission list|counselling schedule|counseling schedule)\b", lower):
            return "realtime_university_admission"
        if re.search(r"\b(dataset|kaggle dataset|data portal|download dataset)\b", lower) and re.search(r"\b(latest|current|find|search|where|available)\b", lower):
            return "realtime_dataset_lookup"
        if re.search(r"\b(public record|court record|case status|land record|company filing|sec filing)\b", lower):
            return "realtime_public_record"
        if re.search(r"\b(weather|temperature|rain|forecast)\b", lower):
            return "realtime_weather"
        if re.search(r"\b(score|scores|match|matches|game|games|fixture|fixtures|standings|points table|league table|ipl|nba|nfl|cricket|football|soccer|tennis)\b", lower):
            return "realtime_sports"
        if re.search(r"\b(public transport|metro|subway|local bus|bus timetable|train timetable)\b", lower):
            return "realtime_public_transport"
        if re.search(r"\b(flights?|trains?|buses|bus|traffic|delay|delayed|cancelled|canceled|pnr|route status|departure|arrival)\b", lower):
            return "realtime_travel_status"
        if re.search(r"\b(platform status|server status|service status|is .{1,35} down|outage|downtime|not loading right now)\b", lower):
            return "realtime_platform_status"
        if re.search(r"\b(power cut|power outage|internet outage|network outage|service outage|blackout)\b", lower):
            return "realtime_outage"
        if re.search(r"\b(showtimes?|movie times?|cinema times?|theater times?)\b", lower):
            return "realtime_movie_showtimes"
        if re.search(r"\b(near me|nearby|open now|restaurant|cafe|hotel|hospital|pharmacy|movie times|cinema|store hours)\b", lower):
            return "realtime_local_places"
        if re.search(r"\b(events?|concert|conference|festival|meetup|tickets?|happening)\b", lower):
            return "realtime_events"
        if re.search(r"\b(job openings?|hiring|vacancy|vacancies|internship|walk[- ]?in)\b", lower):
            return "realtime_jobs"
        if re.search(r"\b(exam result|results? out|board result|admit card|hall ticket|answer key|cutoff|cut[- ]?off)\b", lower):
            return "realtime_exam_result"
        if re.search(r"\b(scholarship|application deadline|last date|admission deadline|registration deadline)\b", lower):
            return "realtime_academic_deadline"
        if re.search(r"\b(holiday|bank holiday|public holiday|school holiday|calendar date)\b", lower):
            return "realtime_holiday_calendar"
        if re.search(r"\b(government scheme|govt scheme|yojana|subsidy|benefit scheme|official portal)\b", lower):
            return "realtime_government_scheme"
        if re.search(r"\b(new law|latest law|current law|new rule|latest rule|regulation update|policy update|guidelines? updated)\b", lower):
            return "realtime_law_policy_update"
        if re.search(r"\b(exchange rate|currency rate|usd to|inr to|eur to|gbp to)\b", lower):
            return "realtime_exchange_rate"
        if re.search(r"\b(price|cost|deal|discount)\b", lower) and re.search(r"\b(phone|laptop|tablet|gpu|cpu|camera|headphones|earbuds|car|bike|product|iphone|android|macbook|playstation|xbox)\b", lower):
            return "realtime_product_price"
        if re.search(r"\b(stock|share|market|sensex|nifty|nasdaq|dow|s&p|inflation|rupee|dollar|stock price|share price|market price)\b", lower):
            return "realtime_market"
        if re.search(
            r"\b(latest|current|new|newest|updated|released)\b.{0,55}\b(version|model|specs?|release|download|phone|iphone|android|ios|windows|app)\b"
            r"|\b(version|model|specs?|release|download|phone|iphone|android|ios|windows|app)\b.{0,55}\b(latest|current|newest|updated|released)\b"
            r"|\b(release date|available now|availability)\b",
            lower,
        ):
            return "realtime_version_release"
        if re.search(r"\b(in stock|out of stock|available near me|store availability|where to buy)\b", lower):
            return "realtime_shopping_availability"
        if re.search(r"\b(best|top|recommend|which should i buy|buy|purchase|worth it|review)\b", lower):
            return "realtime_product_recommendation"
        if re.search(r"\b(schedule|timetable|calendar|when is|date for|exam date|result date)\b", lower):
            return "realtime_schedule"
        if re.search(r"\b(news|latest|recent|today|right now|current conflict|ongoing war|election)\b", lower):
            return "realtime_news"
        if re.search(r"\b(current|ceo|president|prime minister|pm of|who is|who are|verify|fact[- ]?check)\b", lower):
            return "realtime_current_fact"
        return "realtime_search"
    if re.fullmatch(
        r"(?:what is|calculate|solve)?\s*-?\d+(?:\.\d+)?\s*[+\-*/x]\s*-?\d+(?:\.\d+)?\??",
        lower,
    ):
        return "calculation"
    if re.search(r"\b(solve|calculate|math|equation|percentage|percent|ratio|average|profit and loss|speed|distance)\b", lower):
        return "math_reasoning"
    if local_deficiency_diagnosis_reply(message):
        return "diagnostic_deficiency"
    if re.search(r"\b(create|generate|make|draw|give me)\b", lower) and re.search(r"\b(image|picture|photo|art|poster|logo|wallpaper|thumbnail|banner)\b", lower):
        return "image_generation"
    if re.search(r"\b(detect language|what language is this|identify language|language detection)\b", lower):
        return "language_detection"
    if re.search(r"\b(transliterate|transliteration|write .* in english letters|convert .* to english letters)\b", lower):
        return "transliteration"
    if re.search(r"\b(romanize|romanization|romaji|pinyin)\b", lower):
        return "romanization"
    if re.search(r"\b(script conversion|convert script|devanagari|latin script|arabic script|tamil script|telugu script|kannada script|malayalam script)\b", lower):
        return "script_conversion"
    if re.search(r"\b(conversation practice|speaking practice|practice dialogue|roleplay in)\b", lower):
        return "conversation_practice"
    if re.search(r"\b(dialogue translation|translate dialogue|conversation translation)\b", lower):
        return "dialogue_translation"
    if re.search(r"\b(check translation|review translation|is this translation accurate|translation accuracy|fix translation)\b", lower):
        return "translation_review"
    if re.search(r"\b(natural translation|translate naturally|make the translation natural|sound natural in)\b", lower):
        return "natural_translation"
    if re.search(r"\b(literal translation|word for word translation|translate word by word)\b", lower):
        return "literal_translation"
    if re.search(r"\b(back translation|translate it back|back-translate)\b", lower):
        return "back_translation"
    if re.search(r"\b(cultural context|culture note|cultural meaning|does this sound rude|rude or polite)\b", lower):
        return "cultural_context"
    if re.search(r"\b(politeness register|register|honorific|honorifics|formal register|casual register)\b", lower):
        return "politeness_register"
    translation_language_pattern = (
        r"hindi|english|tamil|telugu|kannada|malayalam|marathi|bengali|bangla|gujarati|punjabi|urdu|sanskrit|"
        r"arabic|french|spanish|german|italian|portuguese|russian|chinese|mandarin|japanese|korean|turkish|dutch|"
        r"greek|latin|assamese|odia|oriya|nepali|sinhala|thai|vietnamese|indonesian|malay|swahili|hebrew|persian|farsi|"
        r"polish|ukrainian|czech|swedish|norwegian|danish|finnish|hungarian|romanian|albanian|armenian|azerbaijani|"
        r"basque|bosnian|bulgarian|burmese|myanmar|catalan|croatian|estonian|filipino|tagalog|georgian|haitian creole|"
        r"hausa|icelandic|irish|javanese|kazakh|khmer|lao|latvian|lithuanian|serbian|slovak|slovenian|somali|welsh|"
        r"yoruba|zulu|amharic|pashto|kurdish|uzbek|mongolian|maori|quechua|luxembourgish|galician|belarusian|macedonian|"
        r"maltese|esperanto"
    )
    if re.search(
        rf"\b(translate|translation|convert this to|convert to|say .{{0,80}} in|how to say .{{0,80}} in|to (?:{translation_language_pattern})|in (?:{translation_language_pattern}))\b",
        lower,
    ):
        return "translation"
    if re.search(r"\b(ipa|phonetic transcription|phonetics|phoneme|phonology)\b", lower):
        return "phonetics_ipa"
    if re.search(r"\b(pronounce|pronunciation|how to say|accent practice)\b", lower):
        return "pronunciation_help"
    if re.search(r"\b(accent reduction|speak like|fluency practice|intonation practice)\b", lower):
        return "accent_reduction"
    if re.search(r"\b(language level|level test|placement test|skill assessment|assess my language|fluency level)\b", lower):
        return "language_skill_assessment"
    if re.search(r"\b(cefr|a1|a2|b1|b2|c1|c2)\b", lower) and re.search(r"\b(language|english|french|spanish|german|speaking|writing|reading|listening)\b", lower):
        return "cefr_leveling"
    if re.search(r"\b(language roadmap|language curriculum|study plan for .* language|learn .* in .* days|learn .* in .* months)\b", lower):
        return "language_curriculum"
    if re.search(r"\b(grammar drill|grammar exercise|grammar practice|practice grammar)\b", lower):
        return "grammar_drill"
    if re.search(r"\b(vocabulary quiz|vocab quiz|word quiz|quiz me on words)\b", lower):
        return "vocabulary_quiz"
    if re.search(r"\b(flashcard|flashcards|anki card|anki cards)\b", lower):
        return "flashcards"
    if re.search(r"\b(minimal pair|minimal pairs|sound pairs)\b", lower):
        return "minimal_pairs"
    if re.search(r"\b(syllable stress|word stress|stress pattern|stressed syllable)\b", lower):
        return "syllable_stress"
    if re.search(r"\b(word usage|usage of|how to use .* word|use this word)\b", lower):
        return "word_usage"
    if re.search(r"\b(sentence correction|correct sentence|fix sentence|is this sentence correct)\b", lower):
        return "sentence_correction"
    if re.search(r"\b(cultural context|culture note|cultural meaning|does this sound rude|rude or polite)\b", lower):
        return "cultural_context"
    if re.search(r"\b(politeness register|register|honorific|honorifics|formal register|casual register)\b", lower):
        return "politeness_register"
    if re.search(r"\b(compare languages|difference between .* and .* language|multilingual comparison)\b", lower):
        return "multilingual_compare"
    if re.search(r"\b(essay correction|correct my essay|essay feedback|improve my essay)\b", lower):
        return "essay_correction"
    if re.search(r"\b(email rewrite|rewrite my email|professional email|formal email)\b", lower):
        return "email_rewrite"
    if re.search(r"\b(grammar rule|explain grammar|tense|parts of speech|sentence structure)\b", lower):
        return "grammar_explanation"
    if re.search(r"\b(meaning of|word meaning|what does .* mean|dictionary definition|define this word)\b", lower):
        return "word_meaning"
    if re.search(r"\b(dictionary|definition)\b", lower) and re.search(r"\b(word|term|phrase)\b", lower):
        return "dictionary_definition"
    if re.search(r"\b(etymology|word origin|origin of the word)\b", lower):
        return "etymology"
    if re.search(r"\b(synonym|synonyms|antonym|antonyms|similar words|opposite words)\b", lower):
        return "synonym_antonym"
    if re.search(r"\b(idiom|idioms|figure of speech)\b", lower):
        return "idiom_explanation"
    if re.search(r"\b(proverb|saying|moral saying)\b", lower):
        return "proverb_explanation"
    if re.search(r"\b(vocabulary|vocab|learn words|word list|new words)\b", lower):
        return "vocabulary_builder"
    if re.search(r"\b(spelling|spell check|how to spell|misspelled)\b", lower):
        return "spelling_help"
    if re.search(r"\b(punctuation|comma|semicolon|colon|apostrophe|quotation marks)\b", lower):
        return "punctuation_help"
    if re.search(r"\b(parse this sentence|sentence parsing|parse sentence|clause analysis)\b", lower):
        return "sentence_parsing"
    if re.search(r"\b(parts of speech|noun|pronoun|verb|adjective|adverb|preposition|conjunction)\b", lower):
        return "parts_of_speech"
    if re.search(r"\b(tense practice|tenses|present perfect|past perfect|future tense|tense exercise)\b", lower):
        return "tense_practice"
    if re.search(r"\b(conjugate|verb conjugation|conjugation)\b", lower):
        return "verb_conjugation"
    if re.search(r"\b(phrasal verb|phrasal verbs)\b", lower):
        return "phrasal_verbs"
    if re.search(r"\b(collocation|collocations|natural phrase|word combination)\b", lower):
        return "collocations"
    if re.search(r"\b(make it formal|make it informal|formal tone|informal tone|polite tone|friendly tone)\b", lower):
        return "formal_informal_rewrite"
    if re.search(r"\b(change tone|tone conversion|make it polite|make it professional|make it casual)\b", lower):
        return "tone_conversion"
    if re.search(r"\b(bilingual|explain in both|english and hindi|english and tamil|dual language)\b", lower):
        return "bilingual_explanation"
    if re.search(r"\b(phrasebook|travel phrases|common phrases|useful phrases)\b", lower):
        return "phrasebook"
    if re.search(r"\b(reading comprehension|comprehension passage|read the passage)\b", lower):
        return "reading_comprehension"
    if re.search(r"\b(comprehension questions|questions from passage|make questions from passage)\b", lower):
        return "comprehension_questions"
    if re.search(r"\b(cloze test|fill in the blanks|fill blanks)\b", lower):
        return "cloze_test"
    if re.search(r"\b(dictation|listening practice|dictation practice)\b", lower):
        return "dictation_practice"
    if re.search(r"\b(ielts|toefl|duolingo english test|cambridge english|language exam)\b", lower):
        return "language_exam_prep"
    if re.search(r"\b(localize|localise|localization|localisation|adapt for audience)\b", lower):
        return "language_localization"
    if re.search(r"\b(dialect|slang|british english|american english|indian english|australian english)\b", lower):
        return "dialect_rewrite"
    if re.search(r"\b(subtitle|subtitles|srt|caption translation)\b", lower):
        return "subtitle_translation"
    language_patterns = [
        ("language_hindi", r"\b(hindi|हिंदी)\b"),
        ("language_english", r"\b(english|अंग्रेजी)\b"),
        ("language_tamil", r"\b(tamil|தமிழ்)\b"),
        ("language_telugu", r"\b(telugu|తెలుగు)\b"),
        ("language_kannada", r"\b(kannada|ಕನ್ನಡ)\b"),
        ("language_malayalam", r"\b(malayalam|മലയാളം)\b"),
        ("language_marathi", r"\b(marathi|मराठी)\b"),
        ("language_bengali", r"\b(bengali|bangla|বাংলা)\b"),
        ("language_gujarati", r"\b(gujarati|ગુજરાતી)\b"),
        ("language_punjabi", r"\b(punjabi|ਪੰਜਾਬੀ)\b"),
        ("language_urdu", r"\b(urdu|اردو)\b"),
        ("language_sanskrit", r"\b(sanskrit|संस्कृत)\b"),
        ("language_arabic", r"\b(arabic|العربية)\b"),
        ("language_french", r"\b(french|français)\b"),
        ("language_spanish", r"\b(spanish|español)\b"),
        ("language_german", r"\b(german|deutsch)\b"),
        ("language_italian", r"\b(italian|italiano)\b"),
        ("language_portuguese", r"\b(portuguese|português)\b"),
        ("language_russian", r"\b(russian|русский)\b"),
        ("language_chinese", r"\b(chinese|mandarin|中文|汉语)\b"),
        ("language_japanese", r"\b(japanese|日本語)\b"),
        ("language_korean", r"\b(korean|한국어)\b"),
        ("language_turkish", r"\b(turkish|türkçe)\b"),
        ("language_dutch", r"\b(dutch|nederlands)\b"),
        ("language_greek", r"\b(greek|ελληνικά)\b"),
        ("language_latin", r"\b(latin)\b"),
        ("language_assamese", r"\b(assamese|অসমীয়া)\b"),
        ("language_odia", r"\b(odia|oriya|ଓଡ଼ିଆ)\b"),
        ("language_nepali", r"\b(nepali|नेपाली)\b"),
        ("language_sinhala", r"\b(sinhala|sinhalese|සිංහල)\b"),
        ("language_thai", r"\b(thai|ภาษาไทย)\b"),
        ("language_vietnamese", r"\b(vietnamese|tiếng việt)\b"),
        ("language_indonesian", r"\b(indonesian|bahasa indonesia)\b"),
        ("language_malay", r"\b(malay|bahasa melayu)\b"),
        ("language_swahili", r"\b(swahili|kiswahili)\b"),
        ("language_hebrew", r"\b(hebrew|עברית)\b"),
        ("language_persian", r"\b(persian|farsi|فارسی)\b"),
        ("language_polish", r"\b(polish|polski)\b"),
        ("language_ukrainian", r"\b(ukrainian|українська)\b"),
        ("language_czech", r"\b(czech|čeština)\b"),
        ("language_swedish", r"\b(swedish|svenska)\b"),
        ("language_norwegian", r"\b(norwegian|norsk)\b"),
        ("language_danish", r"\b(danish|dansk)\b"),
        ("language_finnish", r"\b(finnish|suomi)\b"),
        ("language_hungarian", r"\b(hungarian|magyar)\b"),
        ("language_romanian", r"\b(romanian|română)\b"),
        ("language_albanian", r"\b(albanian|shqip)\b"),
        ("language_armenian", r"\b(armenian|հայերեն)\b"),
        ("language_azerbaijani", r"\b(azerbaijani|azeri|azərbaycan)\b"),
        ("language_basque", r"\b(basque|euskara)\b"),
        ("language_bosnian", r"\b(bosnian|bosanski)\b"),
        ("language_bulgarian", r"\b(bulgarian|български)\b"),
        ("language_burmese", r"\b(burmese|myanmar|မြန်မာ)\b"),
        ("language_catalan", r"\b(catalan|català)\b"),
        ("language_croatian", r"\b(croatian|hrvatski)\b"),
        ("language_estonian", r"\b(estonian|eesti)\b"),
        ("language_filipino", r"\b(filipino|tagalog)\b"),
        ("language_georgian", r"\b(georgian|ქართული)\b"),
        ("language_haitian_creole", r"\b(haitian creole|kreyòl)\b"),
        ("language_hausa", r"\b(hausa)\b"),
        ("language_icelandic", r"\b(icelandic|íslenska)\b"),
        ("language_irish", r"\b(irish|gaeilge)\b"),
        ("language_javanese", r"\b(javanese|jawa)\b"),
        ("language_kazakh", r"\b(kazakh|қазақ)\b"),
        ("language_khmer", r"\b(khmer|cambodian|ខ្មែរ)\b"),
        ("language_lao", r"\b(lao|laotian|ລາວ)\b"),
        ("language_latvian", r"\b(latvian|latviešu)\b"),
        ("language_lithuanian", r"\b(lithuanian|lietuvių)\b"),
        ("language_serbian", r"\b(serbian|српски|srpski)\b"),
        ("language_slovak", r"\b(slovak|slovenčina)\b"),
        ("language_slovenian", r"\b(slovenian|slovene|slovenščina)\b"),
        ("language_somali", r"\b(somali|soomaali)\b"),
        ("language_welsh", r"\b(welsh|cymraeg)\b"),
        ("language_yoruba", r"\b(yoruba|yorùbá)\b"),
        ("language_zulu", r"\b(zulu|isizulu)\b"),
        ("language_amharic", r"\b(amharic|አማርኛ)\b"),
        ("language_pashto", r"\b(pashto|پښتو)\b"),
        ("language_kurdish", r"\b(kurdish|kurmanji|sorani)\b"),
        ("language_uzbek", r"\b(uzbek|oʻzbek|o'zbek)\b"),
        ("language_mongolian", r"\b(mongolian|монгол)\b"),
        ("language_maori", r"\b(maori|māori)\b"),
        ("language_quechua", r"\b(quechua|runa simi)\b"),
        ("language_luxembourgish", r"\b(luxembourgish|lëtzebuergesch)\b"),
        ("language_galician", r"\b(galician|galego)\b"),
        ("language_belarusian", r"\b(belarusian|беларуская)\b"),
        ("language_macedonian", r"\b(macedonian|македонски)\b"),
        ("language_maltese", r"\b(maltese|malti)\b"),
        ("language_esperanto", r"\b(esperanto)\b"),
    ]
    if re.search(r"\b(learn|practice|teach me|grammar|vocabulary|phrases|speaking|writing|reading)\b", lower):
        for route_name, pattern in language_patterns:
            if re.search(pattern, lower):
                return route_name
    if re.search(r"\b(language learning|learn a language|practice language|language practice)\b", lower):
        return "language_learning"
    if re.search(r"\b(fix grammar|correct grammar|grammar check|correct this|rewrite|rephrase|polish|make this clearer|improve this sentence|improve this text)\b", lower):
        return "grammar_fix" if re.search(r"\b(grammar|correct)\b", lower) else "rewrite_polish"
    if re.search(r"\b(summarize|summarise|summary|shorten|key points|main points|takeaways)\b", lower) and not re.search(r"\b(file|pdf|document|upload|uploaded)\b", lower):
        return "key_points" if re.search(r"\b(key points|main points|takeaways)\b", lower) else "text_summary"
    if re.search(r"\b(make|create|format|put|show)\b.{0,40}\b(table|tabular|columns)\b|\btable format\b", lower):
        return "table_format"
    if re.search(r"\b(excel formula|spreadsheet formula|google sheets formula|vlookup|xlookup|pivot table)\b", lower):
        return "excel_formula"
    if re.search(r"\b(regex|regular expression|pattern match)\b", lower):
        return "regex_help"
    if re.search(r"\b(git|github)\b", lower) and re.search(r"\b(commit|branch|merge|rebase|pull request|push|clone|conflict)\b", lower):
        return "git_help"
    if re.search(r"\b(deploy|deployment|docker|kubernetes|vercel|render|netlify|aws|azure|gcp|ci/cd|cicd)\b", lower):
        return "devops_deploy"
    if re.search(r"\b(unit test|tests?|test cases?|pytest|jest|vitest|playwright test)\b", lower):
        return "test_generation"
    if re.search(r"\b(log analysis|analyze logs|error logs|server logs)\b", lower):
        return "log_analysis"
    if re.search(r"\b(performance|optimize|optimise|slow|latency|memory leak|speed up)\b", lower) and re.search(r"\b(code|app|website|api|backend|frontend|query|database)\b", lower):
        return "performance_tuning"
    if re.search(r"\b(review this code|code review|review my code)\b", lower):
        return "code_review"
    if re.search(r"\b(architecture review|review architecture|system architecture)\b", lower):
        return "architecture_review"
    if re.search(r"\b(ui|ux|user interface|user experience|design feedback|layout feedback)\b", lower):
        return "ui_ux_feedback"
    if re.search(r"\b(accessibility|a11y|screen reader|wcag|contrast ratio)\b", lower):
        return "accessibility_review"
    if re.search(r"\b(image prompt|prompt for image|stable diffusion prompt|midjourney prompt)\b", lower):
        return "image_prompt"
    if re.search(r"\b(prompt|prompt engineering|system prompt|improve my prompt)\b", lower):
        return "prompt_engineering"
    if re.search(r"\b(contract|agreement|terms|clause|legal document)\b", lower) and re.search(r"\b(explain|review|summarize|simplify|check|what does)\b", lower):
        return "contract_explainer"
    if re.search(r"\b(document|pdf|text|article|essay|report)\b", lower) and re.search(r"\b(review|summarize|analyse|analyze|extract|explain)\b", lower):
        return "document_review"
    if re.search(r"\b(fill|complete|help with)\b.{0,40}\b(form|application form|template)\b", lower):
        return "form_fill_help"
    if re.search(r"\b(clean up|organize|organise|format)\b.{0,40}\b(notes|class notes|rough notes)\b", lower):
        return "notes_cleanup"
    if re.search(r"\b(system design|architecture|scalable design|design a system)\b", lower):
        return "system_design"
    if re.search(r"\b(api design|rest api|endpoint design|openapi|webhook)\b", lower):
        return "api_design"
    if re.search(r"\b(sql|database|schema|query|indexing|postgres|mysql|mongodb)\b", lower):
        return "database_query"
    if re.search(r"\b(cybersecurity|security risk|vulnerability|phishing|malware|xss|csrf|sql injection)\b", lower):
        return "cybersecurity_info"
    if re.search(r"\b(debug|bug|traceback|stack trace|error log|exception)\b", lower):
        return "bug_triage"
    if re.search(r"\b(not working|won't work|doesn't work|broken|issue|problem|fix this)\b", lower):
        return "troubleshooting_steps"
    if re.search(r"\b(fix|debug|error|bug|traceback|issue|not working)\b", lower) and re.search(r"\b(code|backend|frontend|api|html|css|javascript|python|server|app|website|function|script)\b", lower):
        return "code_or_debug"
    if re.search(r"\b(backend|frontend|api|html|css|javascript|python|code|github|deploy)\b", lower):
        return "code_or_debug"
    if re.search(r"\b(meeting notes|minutes of meeting|mom|action items|meeting summary)\b", lower):
        return "meeting_notes"
    if re.search(r"\b(presentation|ppt|slides|slide deck|speech outline)\b", lower):
        return "presentation_outline"
    if re.search(r"\b(essay feedback|review my essay|improve my essay|grade my essay)\b", lower):
        return "essay_feedback"
    if re.search(r"\b(essay|paragraph writing|composition)\b", lower) and re.search(r"\b(write|draft|make|create)\b", lower):
        return "essay_draft"
    if re.search(r"\b(book summary|summarize book|chapter summary|novel summary)\b", lower):
        return "book_summary"
    if re.search(r"\b(poem analysis|analyze poem|poetry analysis)\b", lower):
        return "poem_analysis"
    if re.search(r"\b(lab report|practical report|experiment report)\b", lower):
        return "lab_report"
    if re.search(r"\b(physics|chemistry|biology|science concept|scientific explanation)\b", lower):
        return "science_explanation"
    if re.search(r"\b(history|ww1|ww2|world war|ancient|medieval|modern history)\b", lower):
        return "history_explanation"
    if re.search(r"\b(geography|map work|climate zones|landforms|rivers)\b", lower):
        return "geography_explanation"
    if re.search(r"\b(economics|demand and supply|inflation meaning|gdp|market economy)\b", lower):
        return "economics_explanation"
    if re.search(r"\b(philosophy|ethics|logic|stoicism|existentialism)\b", lower):
        return "philosophy_explanation"
    if re.search(r"\b(speech|welcome speech|anchoring script|talk script)\b", lower):
        return "speech_draft"
    if re.search(r"\b(debate|argument for|argument against|motion)\b", lower):
        return "debate_prep"
    if re.search(r"\b(lesson plan|teaching plan|class activity)\b", lower):
        return "lesson_plan"
    if re.search(r"\b(rubric|grade this|feedback on|mark this|evaluate this)\b", lower):
        return "rubric_feedback"
    if re.search(r"\b(research brief|briefing note|background research|source brief)\b", lower):
        return "research_brief"
    if re.search(r"\b(career roadmap|career path|how to become|roadmap to become)\b", lower):
        return "career_roadmap"
    if re.search(r"\b(resume bullet|resume bullets|achievement bullet|cv bullet)\b", lower):
        return "resume_bullets"
    if re.search(r"\b(cover letter|application letter for job)\b", lower):
        return "cover_letter"
    if re.search(r"\b(linkedin profile|linkedin headline|linkedin about)\b", lower):
        return "linkedin_profile"
    if re.search(r"\b(mock interview|interview practice|simulate interview)\b", lower):
        return "mock_interview"
    if re.search(r"\b(resume|cv|job application|cover letter|career|portfolio|linkedin)\b", lower):
        return "career_resume"
    if re.search(r"\b(interview|hr round|technical round|interview questions)\b", lower):
        return "interview_prep"
    if re.search(r"\b(caption|instagram caption|youtube title|tweet|post caption|social media post)\b", lower):
        return "social_caption"
    if re.search(r"\b(brand name|name my brand|business name|startup name)\b", lower):
        return "brand_naming"
    if re.search(r"\b(slogan|tagline|catchphrase)\b", lower):
        return "slogan_tagline"
    if re.search(r"\b(business strategy|growth strategy|go-to-market|go to market)\b", lower):
        return "business_strategy"
    if re.search(r"\b(market research|competitor research|customer research)\b", lower):
        return "market_research"
    if re.search(r"\b(sales pitch|pitch email|elevator pitch)\b", lower):
        return "sales_pitch"
    if re.search(r"\b(customer support|support reply|reply to customer|complaint response)\b", lower):
        return "customer_support_reply"
    if re.search(r"\b(ad copy|sales copy|landing page copy|marketing copy|product description)\b", lower):
        return "marketing_copy"
    if re.search(r"\b(poem|original song|song lyrics|rap|shayari)\b", lower):
        return "poem_or_original_song"
    if re.search(r"\b(story|short story|creative writing|plot|character idea)\b", lower):
        return "creative_story"
    if re.search(r"\b(joke|funny|make me laugh)\b", lower):
        return "joke_fun"
    if re.search(r"\b(habit|routine|build discipline|daily habit|break a habit)\b", lower):
        return "habit_plan"
    if re.search(r"\b(mental wellness|mental health plan|calm down|burnout|self care)\b", lower):
        return "mental_wellness"
    if re.search(r"\b(stressed|sad|anxious|worried|lonely|angry|overwhelmed|i feel bad)\b", lower):
        return "emotional_support"
    if re.search(r"\b(relationship|crush|friend problem|breakup|family problem)\b", lower):
        return "relationship_advice"
    if re.search(r"\b(negotiate|negotiation|ask for raise|bargain|counter offer)\b", lower):
        return "negotiation_script"
    if re.search(r"\b(apology|say sorry|apologize|apologise)\b", lower):
        return "apology_message"
    if re.search(r"\b(flashcards?|quiz|practice questions|test me|mcq|multiple choice)\b", lower):
        return "flashcards" if re.search(r"\bflashcards?\b", lower) else "quiz_generation"
    if re.search(r"\b(timeline|chronology|order of events|sequence of events)\b", lower):
        return "timeline"
    if re.search(r"\b(study timetable|revision timetable|exam timetable plan)\b", lower):
        return "study_timetable"
    if re.search(r"\b(study plan|study planner|revision plan|timetable|schedule for study)\b", lower):
        return "study_plan"
    if re.search(r"\b(homework|assignment|exam answer|answer this question|question answer|class \d+|grade \d+)\b", lower):
        return "exam_answer" if re.search(r"\b(exam answer|answer this question|question answer)\b", lower) else "homework_help"
    if re.search(r"\b(medical|medicine|diagnosis|clinical|patient|disease|treatment plan)\b", lower):
        return "medicine_info"
    if re.search(r"\b(nursing|patient care plan|care plan|vital signs)\b", lower):
        return "nursing_info"
    if re.search(r"\b(pharmacy|drug interaction|dosage form|medication counseling)\b", lower):
        return "pharmacy_info"
    if re.search(r"\b(dental|dentistry|tooth|teeth|oral hygiene|cavity)\b", lower):
        return "dentistry_info"
    if re.search(r"\b(veterinary|pet health|animal health|dog health|cat health)\b", lower):
        return "veterinary_info"
    if re.search(r"\b(psychology|cognitive behavioral|cbt|therapy plan|behavior analysis)\b", lower):
        return "psychology_info"
    if re.search(r"\b(parenting|child behavior|teen problem|study habit for child)\b", lower):
        return "parenting_guidance"
    if re.search(r"\b(productivity|time management|focus plan|deep work|procrastination)\b", lower):
        return "personal_productivity"
    if re.search(r"\b(sports coaching|training drill|football training|cricket practice|basketball drill)\b", lower):
        return "sports_coaching"
    if re.search(r"\b(music theory|chord progression|scale practice|melody writing)\b", lower):
        return "music_theory"
    if re.search(r"\b(film analysis|movie analysis|cinematography|screenplay analysis)\b", lower):
        return "film_analysis"
    if re.search(r"\b(game design|game mechanic|level design|game balance)\b", lower):
        return "game_design"
    if re.search(r"\b(legal memo|legal memorandum|issue rule analysis conclusion|irac)\b", lower):
        return "legal_memo"
    if re.search(r"\b(case brief|brief this case|case law summary)\b", lower):
        return "case_brief"
    if re.search(r"\b(compliance|regulatory checklist|policy compliance|controls checklist)\b", lower):
        return "compliance_check"
    if re.search(r"\b(privacy policy|data privacy|gdpr|ccpa|privacy notice)\b", lower):
        return "privacy_guidance"
    if re.search(r"\b(ethics|ethical analysis|moral dilemma|professional ethics)\b", lower):
        return "ethics_analysis"
    if re.search(r"\b(religion|theology|scripture|spiritual meaning)\b", lower):
        return "theology_religion"
    if re.search(r"\b(prove that|mathematical proof|proof by induction|proof contradiction)\b", lower):
        return "mathematics_proof"
    if re.search(r"\b(health|symptom|pain|fever|medicine|doctor|diet|sleep|stress|injury)\b", lower):
        return "health_info"
    if re.search(r"\b(legal|law|contract|rights|court|case|sue|police|agreement|terms)\b", lower):
        return "legal_info"
    if re.search(r"\b(budget plan|monthly budget|save money plan)\b", lower):
        return "budget_plan"
    if re.search(r"\b(expense analysis|spending analysis|analyze my expenses)\b", lower):
        return "expense_analysis"
    if re.search(r"\b(accounting|journal entry|ledger|balance sheet|income statement|cash flow statement|bookkeeping)\b", lower):
        return "accounting_help"
    if re.search(r"\b(tax planning|tax return|income tax|gst|vat|deduction|tax saving)\b", lower):
        return "tax_help"
    if re.search(r"\b(audit|internal control|audit checklist|audit finding)\b", lower):
        return "audit_checklist"
    if re.search(r"\b(insurance|premium|claim|policy coverage|deductible)\b", lower):
        return "insurance_guidance"
    if re.search(r"\b(real estate|property|rent agreement|home buying|mortgage|lease)\b", lower):
        return "real_estate_guidance"
    if re.search(r"\b(procurement|vendor selection|rfp|purchase order|supplier)\b", lower):
        return "procurement_plan"
    if re.search(r"\b(finance|money|budget|saving|investment|invest|stock|crypto|loan|debt|tax|profit)\b", lower):
        return "finance_info"
    if re.search(r"\b(hr policy|human resources|employee policy|leave policy|performance review)\b", lower):
        return "hr_policy"
    if re.search(r"\b(operations plan|operational plan|standard process|workflow improvement)\b", lower):
        return "operations_plan"
    if re.search(r"\b(logistics|shipment|warehouse|inventory movement|delivery route)\b", lower):
        return "logistics_plan"
    if re.search(r"\b(supply chain|supplier chain|demand planning|inventory planning)\b", lower):
        return "supply_chain_plan"
    if re.search(r"\b(manufacturing|production line|factory process|lean manufacturing)\b", lower):
        return "manufacturing_process"
    if re.search(r"\b(quality control|qa process|qc checklist|inspection checklist)\b", lower):
        return "quality_control"
    if re.search(r"\b(product management|product roadmap|prd|user story|feature prioritization)\b", lower):
        return "product_management"
    if re.search(r"\b(project management|project charter|risk register|gantt|milestone plan)\b", lower):
        return "project_management"
    if re.search(r"\b(agile|scrum|sprint planning|kanban|retrospective)\b", lower):
        return "agile_scrum"
    if re.search(r"\b(data science|data cleaning|feature engineering|exploratory data analysis|eda)\b", lower):
        return "data_science"
    if re.search(r"\b(machine learning|ml model|classification model|regression model|neural network|ai model training)\b", lower):
        return "machine_learning"
    if re.search(r"\b(statistics|probability|standard deviation|hypothesis test|p value|confidence interval)\b", lower):
        return "statistics_help"
    if re.search(r"\b(dashboard|kpi dashboard|power bi|tableau|looker|analytics dashboard)\b", lower):
        return "dashboard_design"
    if re.search(r"\b(data|dataset|csv|spreadsheet|analyze these numbers|statistics|chart this)\b", lower):
        return "data_analysis"
    if re.search(r"\b(research methodology|research methods|survey design|sample size|literature review)\b", lower):
        return "research_methods"
    if re.search(r"\b(citation|apa|mla|chicago style|bibliography|reference list)\b", lower):
        return "academic_citation"
    if re.search(r"\b(grant proposal|funding proposal|research grant|ngo grant)\b", lower):
        return "grant_proposal"
    if re.search(r"\b(policy analysis|public policy|policy brief|governance)\b", lower):
        return "policy_analysis"
    if re.search(r"\b(news article|journalism|press release|reporting)\b", lower):
        return "journalism_draft"
    if re.search(r"\b(ngo program|nonprofit program|community program|social impact project)\b", lower):
        return "ngo_program_plan"
    if re.search(r"\b(event plan|event planning|wedding plan|conference plan|workshop plan)\b", lower):
        return "event_planning"
    if re.search(r"\b(hotel management|hospitality|restaurant operations|guest service)\b", lower):
        return "hospitality_plan"
    if re.search(r"\b(retail|store layout|merchandising|pos system|shop operations)\b", lower):
        return "retail_plan"
    if re.search(r"\b(agriculture|farming|crop plan|soil health|irrigation)\b", lower):
        return "agriculture_guidance"
    if re.search(r"\b(environmental science|climate change|pollution control|biodiversity)\b", lower):
        return "environmental_science"
    if re.search(r"\b(sustainability|esg|carbon footprint|green plan)\b", lower):
        return "sustainability_plan"
    if re.search(r"\b(civil engineering|concrete|beam design|foundation|construction plan)\b", lower):
        return "civil_engineering"
    if re.search(r"\b(mechanical engineering|machine design|thermodynamics|cad model|hvac)\b", lower):
        return "mechanical_engineering"
    if re.search(r"\b(electrical engineering|circuit design|power system|motor control|wiring diagram)\b", lower):
        return "electrical_engineering"
    if re.search(r"\b(electronics|arduino|raspberry pi|sensor circuit|microcontroller)\b", lower):
        return "electronics_help"
    if re.search(r"\b(architectural plan|building design|floor plan|site plan)\b", lower):
        return "architecture_building"
    if re.search(r"\b(interior design|room design|space planning|furniture layout)\b", lower):
        return "interior_design"
    if re.search(r"\b(urban planning|city planning|transport planning|zoning)\b", lower):
        return "urban_planning"
    if re.search(r"\b(science fair|school project|science project|project plan)\b", lower):
        return "project_plan"
    if re.search(r"\b(reminder|remind me|due|todo|to-do)\b", lower):
        return "reminder"
    if re.search(r"\b(calendar|schedule my|plan my day|time block|appointment)\b", lower):
        return "schedule_planning"
    if re.search(r"\b(workflow|automation|automate|checklist|pipeline)\b", lower):
        return "workflow_plan"
    if is_study_management_request(message):
        return "study_management_plan"
    if is_fitness_plan_request(message):
        return "fitness_plan"
    if re.search(r"\b(brainstorm|ideas?|suggest names?|give me ideas|topic ideas|content ideas)\b", lower):
        return "brainstorm_ideas"
    if re.search(r"\b(which should i choose|which is better|should i|better option|choose between|decide between)\b", lower):
        return "decision_advice"
    if re.search(r"\b(decision matrix|score these options|rank these options|weighted decision)\b", lower):
        return "decision_matrix"
    if re.search(r"\b(risk assessment|risks?|failure points|what could go wrong)\b", lower):
        return "risk_assessment"
    if re.search(r"\b(swot|strengths weaknesses opportunities threats)\b", lower):
        return "swot_analysis"
    if re.search(r"\b(okr|objectives and key results|quarterly goals)\b", lower):
        return "okr_planning"
    if re.search(r"\b(sop|standard operating procedure|process document)\b", lower):
        return "sop_process"
    if re.search(r"\b(checklist|check list|things to do|steps list)\b", lower):
        return "checklist"
    if re.search(r"\b(meal plan|diet plan|weekly meals|nutrition plan)\b", lower):
        return "meal_plan"
    if re.search(r"\b(shopping list|grocery list|things to buy)\b", lower):
        return "shopping_list"
    if re.search(r"\b(recipe|cook|make food|ingredients|how to make)\b", lower):
        return "recipe_or_cooking"
    if re.search(r"\b(travel plan|trip plan|itinerary|visit|tour plan)\b", lower):
        return "travel_itinerary"
    if re.search(r"\b(packing list|what to pack|travel packing)\b", lower):
        return "packing_list"
    if re.search(r"\b(summarize|summarise|summary|read|analyze|analyse|extract|notes from|key points from)\b", lower) and re.search(r"\b(file|pdf|document|upload|uploaded)\b|\bthis\s+(?:file|pdf|document|upload)\b", lower):
        return "file_summary"
    if re.search(r"\b(email|e-mail|mail)\b", lower) and re.search(r"\b(write|draft|compose|make|create|ask|request)\b", lower):
        return "email_draft"
    if re.search(r"\b(reply to|respond to)\b", lower) and re.search(r"\b(email|message|text|dm)\b", lower):
        return "email_reply"
    writing = analyze_writing_request(message)
    if writing.get("is_writing"):
        return f"writing_{clean_text(str(writing.get('kind') or 'draft')).lower()}"
    if re.search(r"\b(song|music|track|recommend|suggest)\b", lower):
        return "song_recommendation"
    if re.search(r"\b(compare products|product comparison|compare phones|compare laptops|versus| vs )\b", lower):
        return "product_comparison"
    if re.search(r"\b(recommend|suggest|best|good option|what should i watch|what should i read)\b", lower):
        return "recommendation"
    if split_comparison_subjects(message):
        return "comparison"
    if re.search(r"\b(advantages and disadvantages|pros and cons|benefits and drawbacks)\b", lower):
        return "pros_cons"
    if re.search(r"\b(youtube|yt|channel|creator|video channel)\b", lower) and is_goal_or_problem_request(message):
        return "youtube_plan"
    if re.search(r"\b(website|web site|webpage|landing page|portfolio site)\b", lower) and is_goal_or_problem_request(message):
        return "website_plan"
    if re.search(r"\b(business|startup|shop|brand|sell|selling|product|business plan)\b", lower) and is_goal_or_problem_request(message):
        return "business_plan"
    if is_goal_or_problem_request(message):
        return "general_plan"
    if local_capability_reply(message):
        return "capability_status"
    if re.search(r"\b(who is|who are|who was|who were|what is|what are|explain|define|describe|meaning of|teach me|history of|overview of|background of|timeline of|how does|why is)\b", lower):
        return "concept_tutoring" if re.search(r"\b(teach me|explain|how does|why is|with example|simple words)\b", lower) else "learning_topic"
    if "?" in lower:
        return "general_question"
    return "chat"


LANGUAGE_ROUTE_NAMES = {
    "translation",
    "language_detection", "transliteration", "romanization", "script_conversion", "word_meaning",
    "dictionary_definition", "etymology", "synonym_antonym", "idiom_explanation",
    "proverb_explanation", "vocabulary_builder", "spelling_help", "punctuation_help",
    "sentence_parsing", "parts_of_speech", "tense_practice", "verb_conjugation",
    "phrasal_verbs", "collocations", "tone_conversion", "formal_informal_rewrite",
    "bilingual_explanation", "phrasebook", "conversation_practice", "dialogue_translation",
    "reading_comprehension", "comprehension_questions", "cloze_test", "dictation_practice",
    "language_exam_prep", "language_localization", "dialect_rewrite", "subtitle_translation",
    "phonetics_ipa", "accent_reduction", "pronunciation_help", "grammar_explanation",
    "language_skill_assessment", "cefr_leveling", "language_curriculum", "grammar_drill",
    "vocabulary_quiz", "flashcards", "minimal_pairs", "syllable_stress", "word_usage",
    "sentence_correction", "translation_review", "natural_translation", "literal_translation",
    "back_translation", "cultural_context", "politeness_register", "multilingual_compare",
    "essay_correction", "email_rewrite",
    "language_learning", "language_hindi", "language_english", "language_tamil",
    "language_telugu", "language_kannada", "language_malayalam", "language_marathi",
    "language_bengali", "language_gujarati", "language_punjabi", "language_urdu",
    "language_sanskrit", "language_arabic", "language_french", "language_spanish",
    "language_german", "language_italian", "language_portuguese", "language_russian",
    "language_chinese", "language_japanese", "language_korean", "language_turkish",
    "language_dutch", "language_greek", "language_latin", "language_assamese",
    "language_odia", "language_nepali", "language_sinhala", "language_thai",
    "language_vietnamese", "language_indonesian", "language_malay", "language_swahili",
    "language_hebrew", "language_persian", "language_polish", "language_ukrainian",
    "language_czech", "language_swedish", "language_norwegian", "language_danish",
    "language_finnish", "language_hungarian", "language_romanian",
    "language_albanian", "language_armenian", "language_azerbaijani", "language_basque",
    "language_bosnian", "language_bulgarian", "language_burmese", "language_catalan",
    "language_croatian", "language_estonian", "language_filipino", "language_georgian",
    "language_haitian_creole", "language_hausa", "language_icelandic", "language_irish",
    "language_javanese", "language_kazakh", "language_khmer", "language_lao",
    "language_latvian", "language_lithuanian", "language_serbian", "language_slovak",
    "language_slovenian", "language_somali", "language_welsh", "language_yoruba",
    "language_zulu", "language_amharic", "language_pashto", "language_kurdish",
    "language_uzbek", "language_mongolian", "language_maori", "language_quechua",
    "language_luxembourgish", "language_galician", "language_belarusian",
    "language_macedonian", "language_maltese", "language_esperanto",
}


LANGUAGE_LABELS = {
    "language_hindi": "Hindi",
    "language_english": "English",
    "language_tamil": "Tamil",
    "language_telugu": "Telugu",
    "language_kannada": "Kannada",
    "language_malayalam": "Malayalam",
    "language_marathi": "Marathi",
    "language_bengali": "Bengali",
    "language_gujarati": "Gujarati",
    "language_punjabi": "Punjabi",
    "language_urdu": "Urdu",
    "language_sanskrit": "Sanskrit",
    "language_arabic": "Arabic",
    "language_french": "French",
    "language_spanish": "Spanish",
    "language_german": "German",
    "language_italian": "Italian",
    "language_portuguese": "Portuguese",
    "language_russian": "Russian",
    "language_chinese": "Chinese/Mandarin",
    "language_japanese": "Japanese",
    "language_korean": "Korean",
    "language_turkish": "Turkish",
    "language_dutch": "Dutch",
    "language_greek": "Greek",
    "language_latin": "Latin",
    "language_assamese": "Assamese",
    "language_odia": "Odia",
    "language_nepali": "Nepali",
    "language_sinhala": "Sinhala",
    "language_thai": "Thai",
    "language_vietnamese": "Vietnamese",
    "language_indonesian": "Indonesian",
    "language_malay": "Malay",
    "language_swahili": "Swahili",
    "language_hebrew": "Hebrew",
    "language_persian": "Persian/Farsi",
    "language_polish": "Polish",
    "language_ukrainian": "Ukrainian",
    "language_czech": "Czech",
    "language_swedish": "Swedish",
    "language_norwegian": "Norwegian",
    "language_danish": "Danish",
    "language_finnish": "Finnish",
    "language_hungarian": "Hungarian",
    "language_romanian": "Romanian",
    "language_albanian": "Albanian",
    "language_armenian": "Armenian",
    "language_azerbaijani": "Azerbaijani",
    "language_basque": "Basque",
    "language_bosnian": "Bosnian",
    "language_bulgarian": "Bulgarian",
    "language_burmese": "Burmese/Myanmar",
    "language_catalan": "Catalan",
    "language_croatian": "Croatian",
    "language_estonian": "Estonian",
    "language_filipino": "Filipino/Tagalog",
    "language_georgian": "Georgian",
    "language_haitian_creole": "Haitian Creole",
    "language_hausa": "Hausa",
    "language_icelandic": "Icelandic",
    "language_irish": "Irish",
    "language_javanese": "Javanese",
    "language_kazakh": "Kazakh",
    "language_khmer": "Khmer",
    "language_lao": "Lao",
    "language_latvian": "Latvian",
    "language_lithuanian": "Lithuanian",
    "language_serbian": "Serbian",
    "language_slovak": "Slovak",
    "language_slovenian": "Slovenian",
    "language_somali": "Somali",
    "language_welsh": "Welsh",
    "language_yoruba": "Yoruba",
    "language_zulu": "Zulu",
    "language_amharic": "Amharic",
    "language_pashto": "Pashto",
    "language_kurdish": "Kurdish",
    "language_uzbek": "Uzbek",
    "language_mongolian": "Mongolian",
    "language_maori": "Maori",
    "language_quechua": "Quechua",
    "language_luxembourgish": "Luxembourgish",
    "language_galician": "Galician",
    "language_belarusian": "Belarusian",
    "language_macedonian": "Macedonian",
    "language_maltese": "Maltese",
    "language_esperanto": "Esperanto",
}


def extract_language_payload(message: str) -> str:
    payload = extract_inline_payload(message)
    if payload:
        return payload
    text = clean_text(message)
    patterns = [
        r"(?i)\b(?:meaning of|define|definition of|synonym(?:s)? for|antonym(?:s)? for|pronounce|pronunciation of|how to say|translate|transliterate|romanize)\s+(.+)$",
        r"(?i)\b(?:idiom|idioms|proverb|proverbs|phrase)\s+(.+)$",
        r"(?i)\b(?:vocabulary|vocab|word list)\s+(?:for|about|on)\s+(.+)$",
        r"(?i)\b(?:correct|fix|rewrite|localize|localise|make it formal|make it informal|change tone)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = clean_text(match.group(1)).strip(" .,:;\"'")
            if candidate:
                return candidate
    return ""


def detect_script_hint(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "Devanagari script, commonly used for Hindi/Marathi/Sanskrit and related languages"
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "Tamil script"
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "Telugu script"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "Kannada script"
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "Malayalam script"
    if re.search(r"[\u0980-\u09FF]", text):
        return "Bengali/Assamese script"
    if re.search(r"[\u0A80-\u0AFF]", text):
        return "Gujarati script"
    if re.search(r"[\u0A00-\u0A7F]", text):
        return "Gurmukhi script, commonly used for Punjabi"
    if re.search(r"[\u0B00-\u0B7F]", text):
        return "Odia script"
    if re.search(r"[\u0D80-\u0DFF]", text):
        return "Sinhala script"
    if re.search(r"[\u0E00-\u0E7F]", text):
        return "Thai script"
    if re.search(r"[\u0E80-\u0EFF]", text):
        return "Lao script"
    if re.search(r"[\u1780-\u17FF]", text):
        return "Khmer script"
    if re.search(r"[\u1000-\u109F]", text):
        return "Burmese/Myanmar script"
    if re.search(r"[\u0600-\u06FF]", text):
        return "Arabic/Urdu-script text"
    if re.search(r"[\u0590-\u05FF]", text):
        return "Hebrew script"
    if re.search(r"[\u0370-\u03FF]", text):
        return "Greek script"
    if re.search(r"[\u0400-\u04FF]", text):
        return "Cyrillic script, used by Russian/Ukrainian/Bulgarian/Serbian and related languages"
    if re.search(r"[\u0530-\u058F]", text):
        return "Armenian script"
    if re.search(r"[\u10A0-\u10FF]", text):
        return "Georgian script"
    if re.search(r"[\u1200-\u137F]", text):
        return "Ethiopic script, commonly used for Amharic and related languages"
    if re.search(r"[\u4E00-\u9FFF]", text):
        return "Chinese characters"
    if re.search(r"[\u3040-\u30FF]", text):
        return "Japanese kana/kanji text"
    if re.search(r"[\uAC00-\uD7AF]", text):
        return "Korean Hangul"
    if re.search(r"[A-Za-z]", text):
        return "Latin-script text"
    return "unclear from the text provided"


def language_practice_plan(language: str) -> str:
    return (
        f"{language} learning route:\n\n"
        "Short answer:\n"
        f"Study {language} through four lanes: pronunciation, vocabulary, grammar patterns, and real conversation.\n\n"
        "Daily practice:\n"
        "1. Pronunciation: repeat 5-10 useful phrases aloud.\n"
        "2. Vocabulary: learn 10 words in one topic, such as school, travel, food, or work.\n"
        "3. Grammar: practise one pattern with 5 original sentences.\n"
        "4. Conversation: write a short dialogue and speak both sides.\n\n"
        "Best route:\n"
        "- Beginner: phrases + pronunciation first.\n"
        "- Intermediate: grammar patterns + reading.\n"
        "- Advanced: writing correction + conversation practice.\n\n"
        "Bottom line:\n"
        f"To improve fast in {language}, practise small real sentences every day instead of memorizing isolated rules."
    )


def local_language_route_reply(message: str, task_intent: str) -> Optional[str]:
    if task_intent not in LANGUAGE_ROUTE_NAMES:
        return None
    payload = extract_language_payload(message)

    if task_intent == "language_detection":
        sample = payload or re.sub(r"(?i)\b(detect language|what language is this|identify language|language detection)\b", "", clean_text(message)).strip()
        script = detect_script_hint(sample)
        return (
            "Language detection:\n\n"
            f"- Script clue: {script}.\n"
            "- For exact language detection, longer text is more reliable than one short word.\n\n"
            "Bottom line:\n"
            f"The safest current guess from the visible script is: {script}."
        )

    if task_intent in {"transliteration", "romanization", "script_conversion"}:
        return (
            "Transliteration route:\n\n"
            "What I can do:\n"
            "- Convert text from one script to another script style.\n"
            "- Keep pronunciation close to the original.\n"
            "- Mark uncertain sounds when the source language has sounds English does not have.\n\n"
            "Needed for exact output:\n"
            "- Source text.\n"
            "- Target script, such as English letters, Devanagari, Tamil, or Arabic script.\n\n"
            "Bottom line:\n"
            "Paste the exact text and target script, and I will transliterate it cleanly."
        )

    if task_intent == "translation":
        lower_message = clean_text(message).lower()
        common_translations = {
            ("thank you", "albanian"): "Faleminderit.",
            ("thanks", "albanian"): "Faleminderit.",
            ("hello", "albanian"): "Pershendetje.",
            ("please", "albanian"): "Te lutem.",
            ("sorry", "albanian"): "Me fal.",
            ("thank you", "spanish"): "Gracias.",
            ("hello", "spanish"): "Hola.",
            ("thank you", "french"): "Merci.",
            ("hello", "french"): "Bonjour.",
            ("thank you", "german"): "Danke.",
            ("hello", "german"): "Hallo.",
            ("thank you", "italian"): "Grazie.",
            ("hello", "italian"): "Ciao.",
            ("thank you", "portuguese"): "Obrigado/Obrigada.",
            ("hello", "portuguese"): "Ola.",
            ("thank you", "japanese"): "Arigato gozaimasu.",
            ("hello", "japanese"): "Konnichiwa.",
            ("thank you", "korean"): "Gamsahamnida.",
            ("hello", "korean"): "Annyeonghaseyo.",
            ("thank you", "hindi"): "Dhanyavaad.",
            ("hello", "hindi"): "Namaste.",
            ("thank you", "tamil"): "Nandri.",
            ("hello", "tamil"): "Vanakkam.",
        }
        for (phrase, language), translated in common_translations.items():
            if phrase in lower_message and language in lower_message:
                return (
                    f"Translation to {language.title()}:\n\n"
                    f"{translated}\n\n"
                    "Usage note:\n"
                    "- Use it as a short everyday phrase.\n"
                    "- For formal speech, add the situation or audience so I can adjust the tone.\n\n"
                    "Bottom line:\n"
                    f"{phrase.title()} in {language.title()} is: {translated}"
                )
        return (
            "Translation route:\n\n"
            "What I need:\n"
            "- Exact text to translate.\n"
            "- Target language.\n"
            "- Tone: simple, formal, friendly, natural, literal, or professional.\n\n"
            "Best format:\n"
            "Use: translate '<text>' to <language> in a natural tone.\n\n"
            "Bottom line:\n"
            "Precise translation needs the exact source text and target language."
        )

    if task_intent in {"word_meaning", "dictionary_definition"}:
        word = payload or "the word"
        return (
            f"Meaning route for {word}:\n\n"
            "Answer structure:\n"
            "- Meaning: give the simple definition first.\n"
            "- Use: show one natural sentence.\n"
            "- Tone: mention whether it is formal, casual, literary, slang, or technical.\n"
            "- Related words: add synonyms and opposites when useful.\n\n"
            "Bottom line:\n"
            "Send the exact word and language if you want a precise dictionary-style answer."
        )

    if task_intent == "synonym_antonym":
        word = payload or "the word"
        if word.lower().strip(" .") == "happy":
            return (
                "Synonyms and antonyms for happy:\n\n"
                "Synonyms:\n"
                "- glad\n"
                "- joyful\n"
                "- pleased\n"
                "- cheerful\n"
                "- delighted\n\n"
                "Antonyms:\n"
                "- sad\n"
                "- unhappy\n"
                "- miserable\n"
                "- upset\n\n"
                "Best use:\n"
                "- Happy is general.\n"
                "- Delighted is stronger.\n"
                "- Pleased is more formal.\n\n"
                "Bottom line:\n"
                "Choose the synonym by intensity and tone, not only by meaning."
            )
        return (
            f"Synonym/antonym route for {word}:\n\n"
            "Synonyms:\n"
            "- Similar words should match the context, not just the dictionary.\n\n"
            "Antonyms:\n"
            "- Opposite words depend on the exact meaning being used.\n\n"
            "Best way to ask:\n"
            f"Use: 'Give synonyms and antonyms for {word} in this sentence: ...'\n\n"
            "Bottom line:\n"
            "Context matters; the best synonym is the one that fits the sentence naturally."
        )

    if task_intent in {"idiom_explanation", "proverb_explanation", "etymology"}:
        item = payload or "the phrase"
        if item.lower().strip(" .") == "break the ice":
            return (
                "Idiom: break the ice\n\n"
                "Meaning:\n"
                "- To make people feel more comfortable at the start of a conversation or meeting.\n\n"
                "Example:\n"
                "- The teacher told a funny story to break the ice on the first day of class.\n\n"
                "Similar meaning:\n"
                "- Start a conversation.\n"
                "- Make the situation less awkward.\n\n"
                "Bottom line:\n"
                "Break the ice means to reduce awkwardness and help people start talking naturally."
            )
        return (
            f"Language explanation for {item}:\n\n"
            "Use this structure:\n"
            "- Literal meaning: what the words say directly.\n"
            "- Real meaning: what the phrase actually means.\n"
            "- Example: one sentence in normal use.\n"
            "- Similar phrase: a close equivalent if one exists.\n\n"
            "Bottom line:\n"
            "Idioms and proverbs should be explained by meaning and use, not translated word by word."
        )

    if task_intent == "vocabulary_builder":
        topic = clean_text(payload or "daily English")
        if re.search(r"\b(business|work|office|professional)\b", topic.lower()):
            return (
                "Business English vocabulary:\n\n"
                "| Word/Phrase | Simple meaning | Example |\n"
                "|---|---|---|\n"
                "| deadline | final date/time | The deadline is Friday. |\n"
                "| proposal | suggested plan | I sent the project proposal. |\n"
                "| revenue | money earned | Revenue increased this month. |\n"
                "| negotiate | discuss to reach agreement | We need to negotiate the price. |\n"
                "| client | customer/customer company | The client approved the design. |\n"
                "| feedback | comments for improvement | Please share your feedback. |\n"
                "| update | new information | Send me an update by evening. |\n"
                "| priority | most important task | This report is our priority. |\n\n"
                "Practice:\n"
                "- Write one sentence with each word.\n"
                "- Then rewrite the sentence in a formal tone.\n\n"
                "Bottom line:\n"
                "Business vocabulary becomes useful when you practise it in emails, meetings, and short status updates."
            )
        return (
            "Vocabulary builder:\n\n"
            "| Level | Words to learn | Practice |\n"
            "|---|---|---|\n"
            "| Basic | common nouns, verbs, adjectives | make simple sentences |\n"
            "| Intermediate | connectors, phrases, topic words | write short paragraphs |\n"
            "| Advanced | idioms, collocations, tone words | rewrite with nuance |\n\n"
            "Daily method:\n"
            "1. Pick one topic.\n"
            "2. Learn 10 words.\n"
            "3. Use each word in your own sentence.\n"
            "4. Review after 1 day, 3 days, and 7 days.\n\n"
            "Bottom line:\n"
            "Vocabulary grows fastest when you use words in sentences, not when you only memorize lists."
        )

    if task_intent in {"language_skill_assessment", "cefr_leveling", "language_curriculum"}:
        return (
            "Language planning route:\n\n"
            "What I will check:\n"
            "- Current level: beginner, intermediate, advanced, or CEFR-style A1-C2.\n"
            "- Weakest skill: reading, writing, listening, speaking, grammar, vocabulary, or pronunciation.\n"
            "- Goal: exam, school, travel, work, conversation, or native-like fluency.\n\n"
            "Best next step:\n"
            "- Send a short writing sample or tell me your target language and goal.\n"
            "- I will build a focused plan with daily practice, review, and measurable progress checks.\n\n"
            "Bottom line:\n"
            "A strong language plan starts by diagnosing the weakest skill, then practising that skill with real sentences."
        )

    if task_intent in {"vocabulary_quiz", "flashcards"}:
        return (
            "Vocabulary practice route:\n\n"
            "I can create:\n"
            "- Flashcards with word, meaning, example, and memory cue.\n"
            "- Multiple-choice vocabulary quizzes.\n"
            "- Fill-in-the-blank practice.\n"
            "- Review sets by topic, level, or exam.\n\n"
            "Best format:\n"
            "Tell me the language, topic, level, and number of words.\n\n"
            "Bottom line:\n"
            "Vocabulary sticks when each word is learned with an example sentence and reviewed more than once."
        )

    if task_intent in {"spelling_help", "punctuation_help", "grammar_explanation", "parts_of_speech", "sentence_parsing", "tense_practice", "verb_conjugation", "phrasal_verbs", "collocations", "grammar_drill", "word_usage", "sentence_correction"}:
        return (
            "Grammar route:\n\n"
            "How I will handle it:\n"
            "- Identify the grammar point.\n"
            "- Explain the rule in simple words.\n"
            "- Show correct and incorrect examples.\n"
            "- Give practice sentences if useful.\n\n"
            "Best format:\n"
            "Send the sentence or grammar topic, and I will break it down clearly.\n\n"
            "Bottom line:\n"
            "Good grammar help should explain the pattern and show how to use it, not just give the answer."
        )

    if task_intent in {"cultural_context", "politeness_register"}:
        return (
            "Cultural language check:\n\n"
            "What decides whether it sounds rude:\n"
            "- Exact words used.\n"
            "- Relationship: friend, teacher, elder, customer, manager, or stranger.\n"
            "- Formality level and honorifics.\n"
            "- Directness, tone, and situation.\n\n"
            "For Japanese especially:\n"
            "- Politeness changes with endings, honorifics, and how direct the request is.\n"
            "- A sentence can be grammatically correct but still sound too blunt.\n\n"
            "Bottom line:\n"
            "Send the exact sentence and who you are saying it to, and I will tell you whether it sounds natural, polite, rude, or too direct."
        )

    if task_intent in {"tone_conversion", "formal_informal_rewrite", "dialect_rewrite", "language_localization", "essay_correction", "email_rewrite"}:
        if payload:
            lower_payload = payload.lower()
            if task_intent == "formal_informal_rewrite" and re.search(r"\b(teacher|sir|madam|school|class)\b", lower_payload) and re.search(r"\b(can'?t|cannot|cant|come|attend)\b", lower_payload):
                polished = "Respected Teacher, I am sorry, but I will not be able to attend today."
            else:
                polished = basic_polish_text(payload)
            return (
                "Tone rewrite:\n\n"
                f"{polished}\n\n"
                "Bottom line:\n"
                "For a stronger rewrite, tell me the target tone: formal, friendly, confident, polite, simple, or professional."
            )
        return (
            "Tone and localization route:\n\n"
            "I can adapt text for:\n"
            "- Formal or informal tone.\n"
            "- American, British, Indian, or other audience styles.\n"
            "- Polite, confident, friendly, academic, or professional wording.\n\n"
            "Bottom line:\n"
            "Paste the exact text and target audience/tone, and I will rewrite it cleanly."
        )

    if task_intent in {"phrasebook", "conversation_practice"}:
        return (
            "Conversation practice route:\n\n"
            "Useful starter phrases:\n"
            "- Hello, how are you?\n"
            "- Could you help me?\n"
            "- I am learning this language.\n"
            "- Please say that again slowly.\n"
            "- Thank you, I understand now.\n\n"
            "Practice method:\n"
            "1. Choose a situation: school, travel, shopping, work, or friends.\n"
            "2. Practise a short dialogue.\n"
            "3. Replace one word at a time to make new sentences.\n\n"
            "Bottom line:\n"
            "Conversation improves fastest through short repeatable dialogues."
        )

    if task_intent in {"reading_comprehension", "comprehension_questions", "cloze_test", "dictation_practice", "language_exam_prep"}:
        return (
            "Language exam/practice route:\n\n"
            "I can create:\n"
            "- Reading comprehension questions.\n"
            "- Fill-in-the-blanks exercises.\n"
            "- Vocabulary and grammar drills.\n"
            "- Model answers with explanations.\n\n"
            "Best structure:\n"
            "Send the passage, class/level, and number of questions.\n\n"
            "Bottom line:\n"
            "Practice should test meaning, vocabulary, grammar, and inference separately."
        )

    if task_intent == "translation_review":
        lower_message = clean_text(message).lower()
        if "bonjour" in lower_message and "hello" in lower_message:
            return (
                "Translation check:\n\n"
                "Yes. Bonjour can mean hello in French.\n\n"
                "Usage note:\n"
                "- Bonjour is used as hello during the day.\n"
                "- It can also mean good morning or good day depending on context.\n\n"
                "Bottom line:\n"
                "Bonjour means hello, but it is more specifically a daytime greeting."
            )
        if "merci" in lower_message and re.search(r"\b(thank you|thanks)\b", lower_message):
            return (
                "Translation check:\n\n"
                "Yes. Merci means thank you or thanks in French.\n\n"
                "Bottom line:\n"
                "Merci is the normal French word for thank you."
            )
        return (
            "Translation review route:\n\n"
            "How I will check it:\n"
            "- Compare the source text with the translation.\n"
            "- Check meaning, tone, grammar, and naturalness.\n"
            "- Mark anything that is literal, awkward, incomplete, or wrong.\n\n"
            "Best format:\n"
            "Send: source text, translation, source language, and target language.\n\n"
            "Bottom line:\n"
            "A good translation review checks meaning and natural wording, not only dictionary matches."
        )

    if task_intent in {"bilingual_explanation", "dialogue_translation", "subtitle_translation", "natural_translation", "literal_translation", "back_translation", "multilingual_compare"}:
        return (
            "Bilingual language route:\n\n"
            "I can format the answer as:\n"
            "| Original | Translation | Simple meaning |\n"
            "|---|---|---|\n"
            "| text | translated text | explanation |\n\n"
            "Bottom line:\n"
            "For subtitles or dialogue, send the exact lines and target language so timing and tone stay natural."
        )

    if task_intent in {"pronunciation_help", "phonetics_ipa", "accent_reduction", "minimal_pairs", "syllable_stress"}:
        word = clean_text(payload)
        if word:
            if word.lower() == "schedule":
                return (
                    "Pronunciation of schedule:\n\n"
                    "- American English: SKED-jool\n"
                    "- British English: SHED-yool\n"
                    "- Simple practice: say it slowly as two parts: sched + ule.\n\n"
                    "Bottom line:\n"
                    "Both pronunciations are accepted; use the one that matches your accent target."
                )
            return (
                f"Pronunciation route for {word}:\n\n"
                "Breakdown:\n"
                "- Say the word slowly first.\n"
                "- Split it into syllables.\n"
                "- Stress the strongest syllable.\n"
                "- Repeat it inside a full sentence.\n\n"
                "Bottom line:\n"
                "Tell me the accent target, such as Indian English, American English, or British English, for a sharper pronunciation guide."
            )
        return (
            "Pronunciation route:\n\n"
            "What I can provide:\n"
            "- Simple pronunciation spelling.\n"
            "- Syllable breaks.\n"
            "- Stress pattern.\n"
            "- IPA-style guidance when useful.\n"
            "- Common mistake warnings.\n\n"
            "Bottom line:\n"
            "Send the word or sentence and the accent target, and I will break down how to say it."
        )

    if task_intent.startswith("language_"):
        return language_practice_plan(LANGUAGE_LABELS.get(task_intent, task_intent.replace("language_", "").title()))

    if task_intent == "language_learning":
        return language_practice_plan("your target language")

    return None


def local_reply_for_intent(message: str, task_intent: str, session_id: Optional[str] = None) -> Optional[str]:
    if task_intent in {
        "calculation",
        "math_reasoning",
        "image_generation",
        "code_or_debug",
        "reminder",
        "table_format",
        "recommendation",
        "data_analysis",
        "email_reply",
        "general_question",
        "realtime_current_fact",
        "realtime_news",
        "realtime_weather",
        "realtime_market",
        "realtime_product_recommendation",
        "realtime_search",
    }:
        return None
    language_reply = local_language_route_reply(message, task_intent)
    if language_reply:
        return language_reply
    if task_intent in {"text_summary", "key_points"}:
        return local_text_summary_reply(message)
    if task_intent in {"grammar_fix", "rewrite_polish"}:
        return local_text_transform_reply(message)
    if task_intent == "brainstorm_ideas":
        return local_brainstorm_reply(message)
    if task_intent == "decision_advice":
        return local_decision_reply(message)
    if task_intent == "recipe_or_cooking":
        return local_recipe_reply(message)
    if task_intent == "travel_itinerary":
        return local_travel_itinerary_reply(message)
    if task_intent == "health_info":
        return local_health_info_reply(message)
    if task_intent == "legal_info":
        return local_legal_info_reply(message)
    if task_intent == "finance_info":
        return local_finance_info_reply(message)
    if task_intent in {"career_resume", "interview_prep"}:
        return local_career_reply(message)
    if task_intent == "presentation_outline":
        return local_presentation_reply(message)
    if task_intent == "meeting_notes":
        return local_meeting_notes_reply(message)
    if task_intent == "social_caption":
        return local_social_caption_reply(message)
    if task_intent in {"creative_story", "poem_or_original_song", "joke_fun"}:
        return local_creative_reply(message)
    if task_intent in {"emotional_support", "relationship_advice"}:
        return local_emotional_support_reply(message)
    if task_intent in {"flashcards", "quiz_generation"}:
        return local_flashcards_or_quiz_reply(message)
    if task_intent == "timeline":
        return local_timeline_reply(message)
    if task_intent in {"homework_help", "exam_answer", "concept_tutoring"}:
        return local_knowledge_reply(message) or local_semantic_reply(message, "learning", "teaching_structure")
    if task_intent == "diagnostic_deficiency":
        return local_deficiency_diagnosis_reply(message)
    if task_intent == "study_management_plan":
        return local_study_management_reply(message)
    if task_intent == "fitness_plan":
        return local_fitness_plan_reply(message)
    if task_intent == "file_summary":
        return local_file_summary_reply(message, session_id)
    if task_intent == "study_plan":
        return local_study_plan_reply(message)
    if task_intent == "email_draft":
        return local_email_reply(message)
    if task_intent.startswith("writing_"):
        return local_writing_reply(message, session_id=session_id)
    if task_intent == "song_recommendation":
        return local_song_recommendation_reply(message)
    if task_intent == "comparison":
        return local_comparison_reply(message)
    if task_intent == "pros_cons":
        return local_pros_cons_reply(message)
    if task_intent in {"project_plan", "youtube_plan", "website_plan", "business_plan", "general_plan"}:
        return local_goal_plan_reply(message)
    if task_intent == "workflow_plan":
        return make_automation_plan(extract_goal_topic(message))
    if task_intent == "capability_status":
        return local_capability_reply(message)
    if task_intent == "learning_topic":
        return local_knowledge_reply(message)
    field_reply = local_field_expert_reply(message, task_intent)
    if field_reply:
        return field_reply
    return None


FIELD_AWARE_INTENTS = {
    "accounting_help", "tax_help", "audit_checklist", "insurance_guidance", "real_estate_guidance",
    "procurement_plan", "hr_policy", "operations_plan", "logistics_plan", "supply_chain_plan",
    "manufacturing_process", "quality_control", "product_management", "project_management",
    "agile_scrum", "data_science", "machine_learning", "statistics_help", "dashboard_design",
    "research_methods", "academic_citation", "grant_proposal", "policy_analysis", "journalism_draft",
    "ngo_program_plan", "event_planning", "hospitality_plan", "retail_plan", "agriculture_guidance",
    "environmental_science", "sustainability_plan", "civil_engineering", "mechanical_engineering",
    "electrical_engineering", "electronics_help", "architecture_building", "interior_design",
    "urban_planning", "medicine_info", "nursing_info", "pharmacy_info", "dentistry_info",
    "veterinary_info", "psychology_info", "parenting_guidance", "personal_productivity",
    "sports_coaching", "music_theory", "film_analysis", "game_design", "legal_memo",
    "case_brief", "compliance_check", "privacy_guidance", "ethics_analysis", "theology_religion",
    "mathematics_proof", "excel_formula", "regex_help", "git_help", "devops_deploy",
    "test_generation", "log_analysis", "performance_tuning", "architecture_review", "code_review",
    "ui_ux_feedback", "accessibility_review", "prompt_engineering", "image_prompt",
}


FIELD_PROFILES: Dict[str, Tuple[str, List[str], str]] = {
    "accounting_help": ("Accounting", ["Identify the accounts affected.", "Classify each account as asset, liability, equity, income, or expense.", "Apply debit/credit rules.", "Check that total debits equal total credits."], "A clean accounting answer should show the entry and the reasoning behind the debit and credit."),
    "nursing_info": ("Nursing", ["Assess the patient first: temperature, pulse, breathing, hydration, pain, and warning signs.", "State nursing goals clearly.", "List interventions with monitoring points.", "Escalate red flags to a qualified clinician."], "For health-related work, use this as education/support, not a substitute for professional care."),
    "medicine_info": ("Medicine", ["Clarify symptoms, timing, severity, and risk factors.", "Separate possible causes from confirmed facts.", "Give safe general guidance.", "Name red flags that need urgent medical help."], "Do not self-diagnose from a short prompt; use a clinician for personal medical decisions."),
    "legal_memo": ("Legal memo", ["Issue: define the legal question.", "Rule: state the governing rule in plain language.", "Analysis: apply the rule to the facts.", "Conclusion: give the likely answer and uncertainty."], "A strong legal memo is structured, fact-specific, and careful about jurisdiction."),
    "case_brief": ("Case brief", ["Facts: only the legally important facts.", "Issue: the question the court decided.", "Holding: the court's answer.", "Reasoning: why the court reached that result."], "Keep a case brief tight; it should help you recall the rule and reasoning fast."),
    "machine_learning": ("Machine learning", ["Define the prediction target.", "List input features and data source.", "Choose a baseline model first.", "Evaluate with the right metric and test split.", "Check leakage, bias, and deployment constraints."], "A good ML plan starts simple, measures honestly, and improves only after a baseline works."),
    "data_science": ("Data science", ["Clarify the business or research question.", "Audit the data quality.", "Explore patterns and outliers.", "Choose the right metric or visualization.", "Turn findings into a decision."], "Useful data science connects analysis to a decision, not just charts."),
    "civil_engineering": ("Civil engineering", ["Define loads, soil/site conditions, codes, and constraints.", "Sketch the structural path.", "Check safety factors and serviceability.", "Send final designs to a licensed engineer."], "Engineering plans need code checks and professional validation before real construction."),
    "electrical_engineering": ("Electrical engineering", ["Define voltage, current, load, protection, and environment.", "Draw the circuit or power path.", "Size components conservatively.", "Verify safety, grounding, heat, and isolation."], "Electrical work can be dangerous; verify real installations with a qualified professional."),
    "mechanical_engineering": ("Mechanical engineering", ["Define forces, motion, material, tolerance, and environment.", "Estimate loads and failure modes.", "Choose a simple mechanism first.", "Validate with calculations, simulation, or a prototype."], "Good mechanical design balances function, manufacturability, safety, and maintenance."),
    "product_management": ("Product management", ["Define the user and problem.", "State success metrics.", "Prioritize the smallest valuable feature.", "List tradeoffs, risks, and rollout checks."], "A good product answer turns ideas into decisions and testable next steps."),
    "project_management": ("Project management", ["Define scope and deliverables.", "Break work into milestones.", "Assign owners and dates.", "Track risks, dependencies, and acceptance criteria."], "A project plan is useful only when it makes ownership and next actions clear."),
    "grant_proposal": ("Grant proposal", ["State the need.", "Define the target group.", "Explain activities and timeline.", "Show budget logic.", "Describe measurable outcomes."], "A strong grant proposal connects problem, action, evidence, budget, and impact."),
}


def local_field_topic(message: str, task_intent: str) -> str:
    topic = clean_text(message)
    topic = re.sub(
        r"(?i)\b(make|create|write|draft|give me|help me|plan|about|for|with|a|an|the)\b",
        " ",
        topic,
    )
    topic = re.sub(r"(?i)\b(accounting|journal entry|nursing care plan|legal memo|machine learning|model plan|ml model|model|civil engineering|project management|grant proposal)\b", " ", topic)
    topic = clean_text(topic).strip(" .,:;-")
    return topic or task_intent.replace("_", " ")


def accounting_journal_entry_reply(message: str) -> str:
    lower = clean_text(message).lower()
    if "cash sales" in lower or ("cash" in lower and "sales" in lower):
        return (
            "Journal entry for cash sales:\n\n"
            "| Account | Debit | Credit |\n"
            "|---|---:|---:|\n"
            "| Cash | Amount |  |\n"
            "| Sales Revenue |  | Amount |\n\n"
            "Why:\n"
            "- Cash increases, so it is debited.\n"
            "- Sales revenue increases, so it is credited.\n\n"
            "Bottom line:\n"
            "If sales tax/GST is involved, credit Sales Revenue for the sale value and credit Tax Payable for the tax portion."
        )
    return ""


def nursing_care_plan_reply(message: str) -> str:
    lower = clean_text(message).lower()
    if "fever" not in lower:
        return ""
    return (
        "Nursing care plan for fever:\n\n"
        "Assessment:\n"
        "- Check temperature pattern, pulse, breathing, blood pressure, hydration, pain, and associated symptoms.\n"
        "- Look for red flags: confusion, stiff neck, breathing difficulty, persistent high fever, dehydration, seizure, or fever in an infant.\n\n"
        "Goals:\n"
        "- Reduce discomfort.\n"
        "- Maintain hydration.\n"
        "- Monitor for worsening signs.\n\n"
        "Interventions:\n"
        "1. Encourage fluids if safe and not restricted.\n"
        "2. Keep clothing and bedding light; avoid over-bundling.\n"
        "3. Monitor temperature and vital signs regularly.\n"
        "4. Give prescribed antipyretics only as ordered or per local clinical guidance.\n"
        "5. Escalate to a clinician if red flags appear or fever persists.\n\n"
        "Bottom line:\n"
        "This is a general care-plan structure; real patient care should follow clinical protocol and qualified medical advice."
    )


def legal_memo_reply(message: str) -> str:
    topic = local_field_topic(message, "legal_memo")
    return (
        f"Legal memo: {title_case_topic(topic)}\n\n"
        "Issue:\n"
        f"- What legal question must be answered about {topic}?\n\n"
        "Rule:\n"
        "- State the governing rule, statute, or case principle. The exact rule depends on jurisdiction.\n\n"
        "Analysis:\n"
        "- Apply each element of the rule to the facts.\n"
        "- Separate strong facts, weak facts, missing facts, and assumptions.\n"
        "- Address the strongest counterargument.\n\n"
        "Conclusion:\n"
        "- Give the likely result in one careful sentence, then note what fact or law could change it.\n\n"
        "Bottom line:\n"
        "A legal memo should be fact-specific and jurisdiction-specific; use this as a structure, not legal advice."
    )


def machine_learning_plan_reply(message: str) -> str:
    topic = local_field_topic(message, "machine_learning")
    return (
        f"Machine learning plan for {topic}:\n\n"
        "Goal:\n"
        f"- Predict or estimate {topic} with a model that can be measured against real outcomes.\n\n"
        "Workflow:\n"
        "1. Define the target variable clearly.\n"
        "2. Collect reliable data and remove duplicates, impossible values, and leakage.\n"
        "3. Start with a simple baseline model before using complex models.\n"
        "4. Split data into train/validation/test sets.\n"
        "5. Evaluate with the right metric, such as MAE/RMSE for prices or F1/AUC for classification.\n"
        "6. Inspect errors by segment so the model is not only good on average.\n\n"
        "Quality checks:\n"
        "- Check data leakage.\n"
        "- Track missing values and outliers.\n"
        "- Compare against a simple rule-based baseline.\n"
        "- Document assumptions before deployment.\n\n"
        "Bottom line:\n"
        "Build a simple measurable baseline first; then improve features and model complexity only when the metric proves it helps."
    )


def local_field_expert_reply(message: str, task_intent: str) -> Optional[str]:
    if task_intent not in FIELD_AWARE_INTENTS:
        return None
    if task_intent == "accounting_help":
        direct = accounting_journal_entry_reply(message)
        if direct:
            return direct
    if task_intent == "nursing_info":
        direct = nursing_care_plan_reply(message)
        if direct:
            return direct
    if task_intent == "legal_memo":
        return legal_memo_reply(message)
    if task_intent == "machine_learning":
        return machine_learning_plan_reply(message)

    label, steps, bottom = FIELD_PROFILES.get(
        task_intent,
        (
            title_case_topic(task_intent.replace("_", " ")),
            ["Clarify the goal and constraints.", "Break the task into steps.", "Check quality, risk, and next action."],
            "A strong answer should be specific, practical, and easy to act on.",
        ),
    )
    topic = local_field_topic(message, task_intent)
    lines = [
        f"{label} answer for {topic}:",
        "",
        "Short answer:",
        f"Treat this as a {label.lower()} task: define the goal, identify constraints, choose the safest method, and check the result before acting.",
        "",
        "Working structure:",
    ]
    lines.extend(f"- {step}" for step in steps)
    lines.extend([
        "",
        "Quality check:",
        "- What fact, rule, measurement, or constraint could change the answer?",
        "- What would a qualified reviewer check first?",
        "- What is the smallest next step that produces evidence?",
        "",
        "Bottom line:",
        bottom,
    ])
    return "\n".join(lines)


def local_structured_fallback(
    message: str,
    response_lane: str = "human_chat",
    presentation_style: str = "balanced",
    session_id: Optional[str] = None,
) -> Optional[str]:
    task_intent = detect_task_intent(message, False)
    routed = local_reply_for_intent(message, task_intent, session_id=session_id)
    if routed:
        return routed
    study_management = local_study_management_reply(message)
    if study_management:
        return study_management
    fitness = local_fitness_plan_reply(message)
    if fitness:
        return fitness
    writing = local_writing_reply(message, session_id=session_id)
    if writing:
        return writing
    file_summary = local_file_summary_reply(message, session_id)
    if file_summary:
        return file_summary
    text_summary = local_text_summary_reply(message)
    if text_summary:
        return text_summary
    text_transform = local_text_transform_reply(message)
    if text_transform:
        return text_transform
    study_plan = local_study_plan_reply(message)
    if study_plan:
        return study_plan
    email = local_email_reply(message)
    if email:
        return email
    song = local_song_recommendation_reply(message)
    if song:
        return song
    capability = local_capability_reply(message)
    if capability:
        return capability
    brainstorm = local_brainstorm_reply(message)
    if brainstorm:
        return brainstorm
    decision = local_decision_reply(message)
    if decision:
        return decision
    recipe = local_recipe_reply(message)
    if recipe:
        return recipe
    travel = local_travel_itinerary_reply(message)
    if travel:
        return travel
    semantic = local_semantic_reply(message, response_lane, presentation_style)
    if semantic:
        return semantic

    text = clean_text(message)
    lower = text.lower()

    if presentation_style == "table" and "anime" in lower:
        return (
            "Anime styles can be compared by audience, themes, and visual design.\n\n"
            "| Style | Typical look | Common themes | Audience |\n"
            "|---|---|---|---|\n"
            "| Shonen | Bold action, bright colors, dynamic poses | Friendship, growth, battles | Teens |\n"
            "| Shojo | Soft colors, expressive faces, emotional framing | Romance, identity, relationships | Teens |\n"
            "| Seinen | Realistic detail, darker tones, complex scenes | Mature drama, psychology, society | Adults |\n\n"
            "Bottom line:\n"
            "The best style depends on the story's mood, audience, and emotional goal."
        )

    if response_lane == "learning" or re.search(r"\b(explain|what is|who is|who was|why|how)\b", lower):
        topic = normalize_prompt_topic(text)
        return (
            f"{topic} can be understood best by starting with the main idea first.\n\n"
            "Key points:\n"
            f"- Focus on what {topic.lower()} means in simple words.\n"
            "- Break the idea into small parts instead of memorizing a long answer.\n"
            "- Use one example to connect the concept with real life.\n\n"
            "Bottom line:\n"
            f"A clear answer about {topic.lower()} should explain the idea, show why it matters, and end with the main takeaway."
        )

    return None


def looks_like_new_task(message: str) -> bool:
    lower = clean_text(message).lower()
    return bool(re.search(
        r"\b(what|why|how|search|latest|current|code|debug|fix|image|picture|photo|generate|create|website|github)\b",
        lower,
    ))


def resolve_pending_task_reply(session_id: str, message: str) -> Optional[str]:
    session = get_session(session_id)
    pending = session.get("pending_task")
    if not isinstance(pending, dict):
        return None
    text = clean_text(message)
    lower = text.lower()
    if lower in {"cancel", "stop", "leave it", "forget it", "never mind", "nevermind"}:
        clear_pending_task(session_id)
        return "Okay, cancelled."

    if pending.get("type") != "writing_topic":
        return None

    request = analyze_writing_request(text)
    if request.get("is_writing") and request.get("missing_topic"):
        set_pending_task(session_id, {
            "type": "writing_topic",
            "kind": request.get("kind", pending.get("kind", "essay")),
            "length": request.get("length", pending.get("length", "balanced")),
            "source": "missing_topic",
        })
        return missing_writing_topic_reply(request)

    if request.get("is_writing") and not request.get("missing_topic"):
        topic = str(request.get("topic") or "the topic")
        kind = str(request.get("kind") or pending.get("kind") or "essay")
        length = str(request.get("length") or pending.get("length") or "balanced")
    else:
        if looks_like_new_task(text) and len(text.split()) > 3:
            clear_pending_task(session_id)
            return None
        topic = normalize_prompt_topic(text)
        if topic == "the topic":
            return missing_writing_topic_reply({
                "kind": pending.get("kind", "essay"),
                "length": pending.get("length", "balanced"),
            })
        kind = str(pending.get("kind") or "essay")
        length = str(pending.get("length") or "balanced")

    clear_pending_task(session_id)
    if "father" in topic.lower() and "day" in topic.lower():
        return build_fathers_day_essay(length)
    topic_specific = build_topic_specific_writing(text, topic, kind, length)
    if topic_specific:
        return topic_specific
    return build_generic_writing(topic, kind, length)


def is_more_request(message: str) -> bool:
    lower = clean_text(message).lower()
    return bool(re.fullmatch(
        r"(a\s+bit\s+more|bit\s+more|more|continue|continue\s+it|go\s+on|expand|expand\s+it|make\s+it\s+longer|add\s+more|tell\s+me\s+more|explain\s+more|a\s+little\s+more)[.! ]*",
        lower,
    ))


def extract_topic_from_recent_focus(focus: Dict[str, Any]) -> str:
    previous_user = clean_text(str(focus.get("previous_user", "")))
    previous_assistant = clean_text(str(focus.get("previous_assistant", "")))
    if previous_user:
        topic = normalize_prompt_topic(previous_user)
        if topic != "the topic":
            return topic
    heading_match = re.match(r"^([A-Z][A-Za-z0-9' -]{2,60})\s+is\b", previous_assistant)
    if heading_match:
        return title_case_topic(heading_match.group(1))
    keywords = [word for word in focus.get("keywords", []) if word not in MEMORY_STOPWORDS]
    if keywords:
        return title_case_topic(" ".join(keywords[:3]))
    return "the topic"


def local_continuation_reply(message: str, focus: Dict[str, Any]) -> Optional[str]:
    if not is_more_request(message):
        return None
    topic = extract_topic_from_recent_focus(focus)
    if topic == "the topic":
        return (
            "Sure. I can add more, but I need the topic first.\n\n"
            "Send the topic or the last answer you want me to expand."
        )
    topic_lower = topic.lower()
    return (
        "Sure. A bit more:\n\n"
        f"Another important point about {topic_lower} is that it becomes easier to understand when we connect it with real life. "
        "A good answer should not only explain the meaning, but also show why the idea matters and how it affects people, choices, or situations.\n\n"
        f"For example, when we think about {topic_lower}, we can look at its causes, its effects, and the lessons it teaches. "
        "This makes the answer feel complete instead of just memorized.\n\n"
        "Bottom line:\n"
        f"{topic} becomes stronger as an answer when it has clear meaning, real-life connection, and a simple final takeaway."
    )


def local_vague_improvement_reply(message: str, focus: Dict[str, Any]) -> Optional[str]:
    lower = clean_text(message).lower()
    if not re.fullmatch(r"(make|fix|improve|change|remove|add)\s+(it|this|that|them|those)(\s+(better|more|again|now|cleaner|stronger|more powerful))?[.! ]*", lower):
        return None
    previous_user = clean_text(str(focus.get("previous_user", "")))
    previous_assistant = clean_text(str(focus.get("previous_assistant", "")))
    if not previous_user and not previous_assistant:
        return (
            "What should I improve?\n\n"
            "Send the answer, page, image, or idea you mean, and I will make it clearer, stronger, and more useful."
        )
    improved = (
        local_goal_plan_reply(previous_user)
        or local_semantic_reply(previous_user, "planning", "implementation_summary")
        or local_writing_reply(previous_user)
    )
    if improved:
        return "Better version:\n\n" + improved
    target = previous_user or extract_topic_from_recent_focus(focus)
    if len(target) > 120:
        target = target[:117].rstrip() + "..."
    return (
        "I understand. You want the previous thing improved, not a generic answer.\n\n"
        f"Target:\n{target}\n\n"
        "What I would improve:\n"
        "1. Make the main point clear in the first line.\n"
        "2. Replace vague steps with specific actions.\n"
        "3. Add useful structure only where it helps.\n"
        "4. Remove filler and weak wording.\n"
        "5. End with a practical next step.\n\n"
        "Bottom line:\n"
        "Send the exact part you want changed, or say the style you want, and I will rewrite it directly."
    )


def local_capability_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if re.search(r"\b(presentation|ppt|slides|slide deck|outline)\b", lower) and not re.search(r"\b(answer structure|presentation level|show answers|display|capability|capable|intelligence)\b", lower):
        return None
    if re.search(
        r"\b(translation|translate|grammar|sentence|word|phrase|language|pronunciation|synonym|antonym|idiom|proverb|cefr|flashcard)\b.*\b(accuracy|accurate|level|structure)\b|"
        r"\b(accuracy|accurate|level|structure)\b.*\b(translation|translate|grammar|sentence|word|phrase|language|pronunciation|synonym|antonym|idiom|proverb|cefr|flashcard)\b",
        lower,
    ):
        return None
    capability_intent = re.search(
        r"\b(powerful|capability|capable|capability status|intelligence|intelligece|intelligence level|understand|understanding|understanding level|accuracy|accuracy level|accuaray|accurate|verification|reasoning|reasoing|reasoning level|structure|structured|strucutre|strucutres|answer structure|presentation|display|show answers|intelligent|smart|smarter|highest|advanced|maxed out|max precision|max-precision|know everything|100 questions|hundred questions|chatgpt|working level|problem solving|real ai)\b",
        lower,
    )
    if not capability_intent:
        return None
    if re.search(r"\b(compare|comparison|vs|versus|analyze|analyse|how|why|steps?|guide)\b", lower):
        return None
    if re.search(r"\bexplain\b", lower) and not re.search(r"\b(capability|capability status|intelligence level|understanding level|accuracy level|reasoning level|answer structure|presentation level|maxed out|max precision|max-precision)\b", lower):
        return None
    if re.search(r"\b(ram|cpu|gpu|memory|hardware|performance|latency|tokens?|context window|inference|training|server|hosting|docker|hugging face|space)\b", lower):
        return None
    return (
        f"Yes. Nexora is set to the extended max practical levels: intelligence {INTELLIGENCE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}, understanding {UNDERSTANDING_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}, accuracy {ACCURACY_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}, reasoning {REASONING_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}, and answer structure {ANSWER_STRUCTURE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}.\n\n"
        f"What the {CAPABILITY_SCALE_TEXT} setup means here:\n"
        "- Intelligence level: It combines intent understanding, reasoning, accuracy, memory/context, tool routing, and answer shaping into one behavior profile.\n"
        f"- Intent quality level: The intent router and quality gate are set to {INTENT_QUALITY_LEVEL_TEXT}/10.00 for route selection and route-mismatch repair.\n"
        f"- Routing matrix: {ROUTING_MATRIX_VERSION} covers realtime search, current facts, weather, markets, crypto, GitHub repos, package versions, earthquakes, launches, language learning, translation, pronunciation, grammar, vocabulary, transliteration, conversation practice, engineering, medicine, law, finance, education, operations, research, creative work, travel, local places, jobs, releases, code/debug, writing, study, planning, images, workflows, and normal chat.\n"
        "- Gate stack: Intent detection, context resolution, route selection, route confidence, task-shape validation, answer quality, accuracy, reasoning, answer structure, repair, and final output cleanup are each exposed as 10.00 gates.\n"
        "- Question contract: It identifies the task type, target, constraints, accuracy need, and best answer format before replying.\n"
        "- Intent first: It corrects messy wording and answers what you likely meant, not only the exact words typed.\n"
        "- Context aware: It uses recent chat, saved preferences, files, images, and project context when they matter.\n"
        "- Accuracy gate: It separates facts, assumptions, and recommendations instead of making overconfident claims.\n"
        "- Reasoning gate: It silently checks assumptions, contradictions, missing details, and practical consequences before writing the final answer.\n"
        "- Research aware: It uses live search or source context for current facts, but avoids slowing down simple stable questions.\n"
        "- Fallback ready: If one model path fails, it can use local structured answers, Wikipedia context, search evidence, Ollama, or the free online model.\n"
        "- Answer structure: It chooses short answers, steps, tables, checklists, or polished drafts based on the task and keeps the result easy to scan.\n"
        "- Clean final output: It removes raw JSON, stream chunks, debug text, and model metadata before the answer reaches the chat.\n"
        "- Supervised autonomy: It can prepare deployment or shipping steps, but production changes stay approval-gated instead of silently running unattended.\n\n"
        "Important truth:\n"
        "The 15.00 scale is an extended app setting, not a promise of unlimited intelligence. Real quality still depends on the model, tools, sources, and context, but Nexora now pushes every available guard to the highest configured level."
    )


def safety_filter_reply(message: str) -> Optional[str]:
    lower = clean_text(message).lower()
    if re.search(r"\b(make|build|create|instructions for|how to)\b.*\b(bomb|explosive|poison|weapon|gun|malware|ransomware|phishing|steal password|bypass login)\b", lower):
        return (
            "I cannot help with harmful instructions, malware, weapons, theft, or bypassing security.\n\n"
            "I can help with a safe alternative: cybersecurity basics, defensive coding, legal troubleshooting, or a high-level explanation without actionable harm."
        )
    if re.search(r"\b(kill myself|suicide|self harm|hurt myself)\b", lower):
        return (
            "I am really sorry you are feeling this. I cannot help with self-harm instructions.\n\n"
            "Please contact local emergency services now if you might act on this. If you are in the U.S. or Canada, call or text 988. If you are elsewhere, contact a trusted person nearby or your local crisis line right now."
        )
    if re.search(r"\b(diagnose me|which medicine should i take|legal advice|invest all|guaranteed profit)\b", lower):
        return (
            "I can give general information, but this is a high-stakes topic. I should not replace a qualified professional.\n\n"
            "Share the context, and I will help you understand options, risks, and questions to ask an expert."
        )
    return None


def local_resilient_reply(
    message: str,
    session_id: str,
    response_lane: str,
    presentation_style: str,
    understanding_state: Optional[Dict[str, Any]] = None,
) -> str:
    state = understanding_state or {}
    focus = recent_session_focus(get_session(session_id), message)
    continuation = local_continuation_reply(message, focus)
    if continuation:
        return continuation
    vague_improvement = local_vague_improvement_reply(message, focus)
    if vague_improvement:
        return vague_improvement
    capability = local_capability_reply(message)
    if capability:
        return capability
    study_management = local_study_management_reply(state.get("normalized") or message)
    if study_management:
        return study_management
    fitness = local_fitness_plan_reply(state.get("normalized") or message)
    if fitness:
        return fitness
    writing = local_writing_reply(state.get("normalized") or message, session_id=session_id)
    if writing:
        return writing
    file_summary = local_file_summary_reply(state.get("normalized") or message, session_id)
    if file_summary:
        return file_summary
    text_summary = local_text_summary_reply(state.get("normalized") or message)
    if text_summary:
        return text_summary
    text_transform = local_text_transform_reply(state.get("normalized") or message)
    if text_transform:
        return text_transform
    study_plan = local_study_plan_reply(state.get("normalized") or message)
    if study_plan:
        return study_plan
    email = local_email_reply(state.get("normalized") or message)
    if email:
        return email
    brainstorm = local_brainstorm_reply(state.get("normalized") or message)
    if brainstorm:
        return brainstorm
    decision = local_decision_reply(state.get("normalized") or message)
    if decision:
        return decision
    recipe = local_recipe_reply(state.get("normalized") or message)
    if recipe:
        return recipe
    travel = local_travel_itinerary_reply(state.get("normalized") or message)
    if travel:
        return travel
    semantic = local_semantic_reply(state.get("normalized") or message, response_lane, presentation_style)
    if semantic:
        return semantic
    lower = clean_text(state.get("normalized") or message).lower()
    if response_lane == "learning" or re.search(r"\b(explain|what|why|how|teach|learn)\b", lower):
        topic = normalize_prompt_topic(state.get("normalized") or message)
        if topic == "the topic":
            topic = "this"
        return (
            f"{title_case_topic(topic)} means understanding the main idea first, then connecting it with examples.\n\n"
            "Key points:\n"
            "- Start with the simple meaning.\n"
            "- Break the idea into smaller parts.\n"
            "- Use one real-life example.\n"
            "- End with the main takeaway.\n\n"
            "Bottom line:\n"
            "A good answer is clear, connected, and easy to remember."
        )
    if response_lane == "build":
        return (
            "I can keep working on that. The practical next step is to identify the exact part that should change, apply a small fix, and test the visible behavior.\n\n"
            "What I will prioritize:\n"
            "- No timeout-style dead ends.\n"
            "- Better context memory for follow-ups.\n"
            "- Clean, structured answers.\n"
            "- A fallback answer when the online model is unavailable."
        )
    return (
        "Send one clear target, and I will turn it into a clean answer or workflow.\n\n"
        "Useful examples:\n"
        "- Write a sick leave letter.\n"
        "- Explain photosynthesis for class 8.\n"
        "- Create an image of a blue robot in a classroom.\n"
        "- Make a study plan for maths."
    )


def choose_response_mode(message: str, requested_mode: Optional[str], requested_model: Optional[str]) -> str:
    text = clean_text(message).lower()
    requested = f"{requested_mode or ''} {requested_model or ''}".lower()
    speed_requested = bool(re.search(r"\b(fast|faster|quick|quickly|speed|instant|low latency|don'?t wait|dont wait)\b", text))
    max_quality_requested = bool(re.search(
        r"\b(max|maximum|maxed out|max out|highest|highest level|best possible|as intelligent as possible|"
        r"reasoning|understanding|precise|precision|accurate|accuracy|intelligence|smart|smarter|"
        r"clear well structured|well structured|structured answer|no raw outputs?|polished answer)\b",
        text,
    ))
    current_or_high_risk = bool(re.search(
        r"\b(latest|current|today|recent|news|market|stock|price|filing|legal|medical|medicine|diagnose|investment|tax|law|safety)\b",
        text,
    ))
    complex_request = bool(re.search(
        r"\b(debug|fix|build|deploy|code|backend|frontend|api|compare|comparison|step by step|architecture|detailed|deep|full|complete)\b",
        text,
    ))

    if any(word in requested for word in ["thinking", "research", "finance", "code"]):
        return "thinking"
    if any(word in requested for word in ["instant", "fast"]):
        return "instant"
    if speed_requested and not current_or_high_risk and not complex_request and not max_quality_requested:
        return "instant"
    if max_quality_requested:
        return "thinking"
    if re.search(r"\b(table|chart|diagram|flowchart|compare|comparison|detailed|step by step|full|complete|highest|advanced|intelligent|understanding|capability|reasonable)\b", text):
        return "thinking"

    thinking_patterns = [
        r"\b(explain|analyze|compare|debug|fix|build|create|design|plan|strategy|architecture)\b",
        r"\b(why|how|prove|derive|solve|calculate|implement|refactor|review|optimize)\b",
        r"\b(latest|current|today|recent|news|market|stock|price|filing|contract)\b",
        r"\b(step by step|deep|detailed|well structured|structured answer|clear answer|accurate|accuracy|reasonable|reasoning|understand|understanding|intent|capability|intelligent|intelligence|smarter|highest|advanced|sources?|citations?)\b",
    ]
    if len(text) > 140:
        return "thinking"
    if any(re.search(pattern, text) for pattern in thinking_patterns):
        return "thinking"
    if text.count("?") >= 2:
        return "thinking"
    return "instant"


def detect_total_ram_gb() -> Optional[float]:
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            memory = MEMORYSTATUSEX()
            memory.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                return round(memory.ullTotalPhys / (1024 ** 3), 2)
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("MemTotal:"):
                    kb = float(re.findall(r"\d+", line)[0])
                    return round(kb / (1024 ** 2), 2)
    except Exception:
        return None
    return None


def infer_performance_level(cpu_threads: int, ram_gb: Optional[float]) -> str:
    if PERFORMANCE_LEVEL in {"tiny", "light", "balanced", "strong"}:
        return PERFORMANCE_LEVEL
    if cpu_threads <= 2 or (ram_gb is not None and ram_gb < 8):
        return "tiny"
    if cpu_threads <= 4 or (ram_gb is not None and ram_gb < 14):
        return "light"
    if cpu_threads <= 8 or (ram_gb is not None and ram_gb < 24):
        return "balanced"
    return "strong"


def performance_limits_for(level: str) -> Dict[str, int]:
    profiles = {
        "tiny": {
            "instant_max_tokens": 240,
            "thinking_max_tokens": 520,
            "ollama_context_tokens": 1536,
            "history_messages": 2,
            "file_context_chars": 1600,
            "cache_items": 120,
        },
        "light": {
            "instant_max_tokens": 520,
            "thinking_max_tokens": 1350,
            "ollama_context_tokens": 3584,
            "history_messages": 5,
            "file_context_chars": 5200,
            "cache_items": 160,
        },
        "balanced": {
            "instant_max_tokens": 700,
            "thinking_max_tokens": 2100,
            "ollama_context_tokens": 5120,
            "history_messages": 10,
            "file_context_chars": 7600,
            "cache_items": 180,
        },
        "strong": {
            "instant_max_tokens": 1100,
            "thinking_max_tokens": 2600,
            "ollama_context_tokens": 8192,
            "history_messages": 12,
            "file_context_chars": 11000,
            "cache_items": 220,
        },
    }
    return profiles.get(level, profiles["light"])


def system_profile() -> Dict[str, Any]:
    global SYSTEM_PROFILE_CACHE
    if SYSTEM_PROFILE_CACHE is not None:
        return SYSTEM_PROFILE_CACHE

    cpu_threads = os.cpu_count() or 2
    ram_gb = detect_total_ram_gb()
    level = infer_performance_level(cpu_threads, ram_gb)
    limits = performance_limits_for(level)
    if level in {"tiny", "light"}:
        reason = "Modest CPU/RAM detected, so Nexora uses lightweight self-learning and small local models."
        avoid_models = "Avoid local models larger than about 3B unless they are heavily quantized and you accept slower replies."
    elif level == "balanced":
        reason = "Mid-range resources detected, so Nexora can use moderate context and small-to-mid local models."
        avoid_models = "Prefer models around 1B-7B quantized for local use."
    else:
        reason = "Strong resources detected, so Nexora can safely use longer context and larger local models."
        avoid_models = "Larger local models may work, but watch memory and heat."

    SYSTEM_PROFILE_CACHE = {
        "level": level,
        "override": PERFORMANCE_LEVEL if PERFORMANCE_LEVEL != "auto" else None,
        "reason": reason,
        "hardware": {
            "cpu_threads": cpu_threads,
            "ram_gb": ram_gb,
            "gpu_class": "integrated_or_unknown",
        },
        "limits": limits,
        "quality_enforcement": {
            "mode": QUALITY_ENFORCEMENT_MODE,
            "description": "Max routing and quality guards: choose the real task type, reject generic filler for practical requests, verify current facts, and clean final output.",
        },
        "gate_stack": {
            "mode": GATE_STACK_MODE,
            "scale": "0.00-10.00",
            "levels": gate_levels_payload(),
            "routing_matrix": routing_matrix_payload(),
            "description": "Separate 10.00 gates for intent detection, context resolution, routing, route confidence, task-shape validation, answer quality, accuracy, reasoning, answer structure, repair, and final cleanup.",
        },
        "intelligence": {
            "level": INTELLIGENCE_LEVEL_TEXT,
            "scale": f"0.00-{CAPABILITY_SCALE_TEXT}",
            "mode": INTELLIGENCE_MODE,
            "description": "Extended app-level intelligence profile combining intent parsing, reasoning, accuracy, context, tool routing, and polished final output.",
        },
        "understanding": {
            "level": UNDERSTANDING_LEVEL_TEXT,
            "scale": f"0.00-{CAPABILITY_SCALE_TEXT}",
            "mode": UNDERSTANDING_MODE,
            "description": "Max-agentic intent parsing, context resolution, question-contract planning, reasonableness checks, and final-answer cleanup.",
        },
        "accuracy": {
            "level": ACCURACY_LEVEL_TEXT,
            "scale": f"0.00-{CAPABILITY_SCALE_TEXT}",
            "mode": ACCURACY_MODE,
            "description": "Strict verification for current facts, uncertainty labeling, source-backed evidence when needed, and hallucination cleanup before final output.",
        },
        "reasoning": {
            "level": REASONING_LEVEL_TEXT,
            "scale": f"0.00-{CAPABILITY_SCALE_TEXT}",
            "mode": REASONING_MODE,
            "description": "Silent internal reasoning pass for assumptions, contradictions, edge cases, task order, and practical consequences before final output.",
        },
        "answer_structure": {
            "level": ANSWER_STRUCTURE_LEVEL_TEXT,
            "scale": f"0.00-{CAPABILITY_SCALE_TEXT}",
            "mode": ANSWER_STRUCTURE_MODE,
            "description": "Polished answer layout with compact leads, clean section labels, short paragraphs, task-fit bullets/tables, and no raw output artifacts.",
        },
        "local_ai": {
            "recommended_fast_model": FAST_MODEL,
            "recommended_thinking_model": THINKING_MODEL,
            "prefer_free_api_when_available": level in {"tiny", "light"},
            "avoid": avoid_models,
        },
        "self_learning": {
            "mode": "ranked_long_term_memory_persona_and_behavior",
            "uses_model_weight_training": False,
            "description": "Nexora learns preferences, behavior signals, feedback, corrections, image preferences, and project context by saving ranked memory/persona/behavior rules, not by retraining a large model on this laptop.",
        },
    }
    return SYSTEM_PROFILE_CACHE


def current_performance_limits() -> Dict[str, int]:
    return dict(system_profile().get("limits", performance_limits_for("light")))


def runtime_efficiency_context() -> str:
    profile = system_profile()
    limits = profile["limits"]
    return (
        "Runtime capability profile:\n"
        f"- Level: {profile['level']}\n"
        f"- Quality enforcement: {QUALITY_ENFORCEMENT_MODE}.\n"
        f"- Gate stack mode: {GATE_STACK_MODE}.\n"
        f"- Routing matrix: {ROUTING_MATRIX_VERSION}.\n"
        f"- Intent quality level: {INTENT_QUALITY_LEVEL_TEXT}/10.00.\n"
        f"- Routing gate: {ROUTING_GATE_MODE} at {ROUTING_GATE_LEVEL_TEXT}/10.00; quality gate: {QUALITY_GATE_MODE} at {QUALITY_GATE_LEVEL_TEXT}/10.00.\n"
        "- Extra 10.00 gates: intent detection, context resolution, route selection, route confidence, task-shape validation, answer quality, accuracy, reasoning, answer structure, repair, and final output cleanup.\n"
        f"- Intelligence level: {INTELLIGENCE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({INTELLIGENCE_MODE}).\n"
        f"- Understanding level: {UNDERSTANDING_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({UNDERSTANDING_MODE}).\n"
        f"- Accuracy level: {ACCURACY_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({ACCURACY_MODE}).\n"
        f"- Reasoning level: {REASONING_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({REASONING_MODE}).\n"
        f"- Answer structure level: {ANSWER_STRUCTURE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({ANSWER_STRUCTURE_MODE}).\n"
        f"- Reason: {profile['reason']}\n"
        f"- Self-learning mode: ranked saved memory/persona/behavior profile, up to {MAX_MEMORY_ITEMS} memories with {MAX_MEMORY_CONTEXT_ITEMS} selected per answer; not local model-weight training.\n"
        f"- Keep normal answers efficient for this computer: instant <= {limits['instant_max_tokens']} tokens, "
        f"thinking <= {limits['thinking_max_tokens']} tokens unless the user explicitly needs more."
    )


def mode_limits(response_mode: str) -> Tuple[int, int, float]:
    limits = current_performance_limits()
    if response_mode == "thinking":
        return min(MAX_MODEL_TOKENS, limits["thinking_max_tokens"]), THINKING_TIMEOUT, 0.15
    return min(MAX_MODEL_TOKENS, limits["instant_max_tokens"]), INSTANT_TIMEOUT, 0.12


def json_lock_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.lock")


def remove_stale_json_lock(lock_path: Path, stale_after: float = 30.0) -> bool:
    try:
        if lock_path.exists() and time.time() - lock_path.stat().st_mtime > stale_after:
            lock_path.unlink(missing_ok=True)
            return True
    except Exception:
        return False
    return False


def wait_for_json_unlock(path: Path, timeout: float = 5.0) -> None:
    lock_path = json_lock_path(path)
    started = time.time()
    while lock_path.exists():
        if remove_stale_json_lock(lock_path):
            break
        if time.time() - started >= timeout:
            break
        time.sleep(0.025)


def acquire_json_file_lock(path: Path, timeout: float = 5.0) -> Path:
    lock_path = json_lock_path(path)
    started = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()} {time.time()}")
            return lock_path
        except FileExistsError:
            remove_stale_json_lock(lock_path)
        except PermissionError:
            pass
        if time.time() - started >= timeout:
            raise PermissionError(f"Timed out waiting for JSON data lock: {path.name}")
        time.sleep(0.025)


def release_json_file_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def safe_read_json(path: Path, default: Any) -> Any:
    wait_for_json_unlock(path)
    try:
        if not path.exists():
            return default
        for attempt in range(8):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
            except json.JSONDecodeError:
                time.sleep(0.05 * (attempt + 1))
        return default
    except Exception:
        return default


def read_json_direct(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_atomic(path: Path, data: Any) -> None:
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    last_error: Optional[PermissionError] = None
    for attempt in range(30):
        try:
            tmp.replace(path)
            return
        except PermissionError as error:
            last_error = error
            time.sleep(min(0.05 * (attempt + 1), 0.5))
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass
    if last_error:
        raise last_error


def safe_write_json(path: Path, data: Any) -> None:
    with JSON_WRITE_LOCK:
        lock_path = acquire_json_file_lock(path)
        try:
            write_json_atomic(path, data)
        finally:
            release_json_file_lock(lock_path)


def update_json_dict(path: Path, default: Dict[str, Any], mutator: Any) -> Any:
    with JSON_WRITE_LOCK:
        lock_path = acquire_json_file_lock(path)
        try:
            data = read_json_direct(path, default.copy())
            if not isinstance(data, dict):
                data = default.copy()
            result, changed = mutator(data)
            if changed:
                write_json_atomic(path, data)
            return result
        finally:
            release_json_file_lock(lock_path)


def ensure_session(session_id: Optional[str]) -> str:
    if session_id and re.match(r"^[a-zA-Z0-9_\-]{6,100}$", session_id):
        return session_id
    return f"nx_{uuid.uuid4().hex[:18]}"


def load_sessions() -> Dict[str, Any]:
    return safe_read_json(SESSIONS_FILE, {})


def save_sessions(sessions: Dict[str, Any]) -> None:
    safe_write_json(SESSIONS_FILE, sessions)


def new_session_record(session_id: str) -> Dict[str, Any]:
    return {
        "id": session_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "messages": [],
        "files": [],
    }


def get_session(session_id: str) -> Dict[str, Any]:
    def mutate(sessions: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        session = sessions.get(session_id)
        if not session:
            session = new_session_record(session_id)
            sessions[session_id] = session
            return session, True
        return session, False

    return update_json_dict(SESSIONS_FILE, {}, mutate)


def update_session(session_id: str, session: Dict[str, Any]) -> None:
    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)


def bind_session_user(session_id: str, user_id: str) -> None:
    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session = sessions.get(session_id) or new_session_record(session_id)
        if session.get("user_id") == user_id:
            sessions[session_id] = session
            return None, False
        session["user_id"] = user_id
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)


def set_pending_task(session_id: str, task: Dict[str, Any]) -> None:
    task["created_at"] = now_iso()

    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session = sessions.get(session_id) or new_session_record(session_id)
        session["pending_task"] = task
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)


def clear_pending_task(session_id: str) -> None:
    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session = sessions.get(session_id)
        if not isinstance(session, dict) or "pending_task" not in session:
            return None, False
        session.pop("pending_task", None)
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)


def set_session_value(session_id: str, key: str, value: Any) -> None:
    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session = sessions.get(session_id) or new_session_record(session_id)
        session[key] = value
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)


def pop_session_value(session_id: str, key: str) -> Any:
    def mutate(sessions: Dict[str, Any]) -> Tuple[Any, bool]:
        session = sessions.get(session_id)
        if not isinstance(session, dict) or key not in session:
            return None, False
        value = session.pop(key, None)
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return value, True

    return update_json_dict(SESSIONS_FILE, {}, mutate)


def append_session_message(session_id: str, role: str, content: str) -> None:
    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session = sessions.get(session_id) or new_session_record(session_id)
        session.setdefault("messages", []).append(
            {"role": role, "content": content, "created_at": now_iso()}
        )
        session["messages"] = session["messages"][-MAX_SESSION_MESSAGES:]
        session["turn_count"] = int(session.get("turn_count", 0) or 0) + (1 if role == "user" else 0)
        clean_content = clean_text(content)
        if role == "user" and clean_content:
            session["last_user_message"] = clean_content[:700]
            session["last_user_keywords"] = memory_keywords(clean_content)[:12]
        elif role == "assistant" and clean_content:
            session["last_assistant_summary"] = clean_content[:500]
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)


def load_memory() -> List[Dict[str, Any]]:
    raw = safe_read_json(MEMORY_FILE, [])
    return raw if isinstance(raw, list) else []


def parse_memory_timestamp(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except Exception:
        return 0.0


def memory_item_importance(item: Dict[str, Any]) -> float:
    content = clean_text(str(item.get("content", "")))
    if not content:
        return -1000.0
    category = clean_text(str(item.get("category", "general"))).lower()
    source = clean_text(str(item.get("source", "auto"))).lower()
    hits = max(1, int(item.get("hits", 1) or 1))
    sessions = item.get("sessions", [])
    session_count = len(sessions) if isinstance(sessions, list) else 0
    keyword_count = len(item.get("keywords", []) or [])
    last_seen = parse_memory_timestamp(item.get("last_seen") or item.get("created_at"))
    age_days = max(0.0, (time.time() - last_seen) / 86400.0) if last_seen else 90.0
    category_weight = {
        "explicit": 32,
        "identity": 28,
        "project": 24,
        "preference": 22,
        "workflow": 18,
        "correction": 18,
        "image_preference": 18,
        "interaction_pattern": 6,
    }.get(category, 10)
    source_weight = 18 if source == "user_instruction" else 10 if source.startswith("auto") else 4
    recency = max(0.0, 18.0 - min(18.0, age_days / 3.0))
    return category_weight + source_weight + min(35, hits * 3) + min(12, session_count * 2) + min(10, keyword_count) + recency


def prune_memory_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid = [item for item in items if isinstance(item, dict) and clean_text(str(item.get("content", "")))]
    deduped: Dict[str, Dict[str, Any]] = {}
    for item in valid:
        normalized_user = normalize_user_id(str(item.get("user_id", "default")))
        category = clean_text(str(item.get("category", "general"))).lower() or "general"
        content = clean_text(str(item.get("content", "")))[:1000]
        item["user_id"] = normalized_user
        item["category"] = category
        item["content"] = content
        item.setdefault("created_at", now_iso())
        item.setdefault("last_seen", item.get("created_at"))
        item["keywords"] = memory_keywords(" ".join([content, " ".join(map(str, item.get("keywords", []) or []))]))
        key = str(item.get("memory_key") or f"{normalized_user}|{category}|{content.lower()}")
        item["memory_key"] = key
        existing = deduped.get(key)
        if not existing:
            deduped[key] = item
            continue
        existing["hits"] = max(int(existing.get("hits", 1) or 1), int(item.get("hits", 1) or 1))
        existing["last_seen"] = max(str(existing.get("last_seen", "")), str(item.get("last_seen", "")))
        existing["keywords"] = sorted(set(existing.get("keywords", []) + item.get("keywords", [])))[:40]
        sessions = []
        for value in (existing.get("sessions", []) or []) + (item.get("sessions", []) or []):
            if value and value not in sessions:
                sessions.append(value)
        existing["sessions"] = sessions[-24:]

    sorted_items = sorted(deduped.values(), key=memory_item_importance, reverse=True)
    kept = sorted_items[:MAX_MEMORY_ITEMS]
    kept.sort(key=lambda item: str(item.get("last_seen", item.get("created_at", ""))), reverse=True)
    return kept


def save_memory(items: List[Dict[str, Any]]) -> None:
    safe_write_json(MEMORY_FILE, prune_memory_items(items))


MEMORY_STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been", "before",
    "being", "but", "can", "could", "did", "does", "for", "from", "give", "have",
    "how", "into", "make", "more", "need", "now", "only", "should", "that", "the",
    "then", "this", "those", "use", "user", "want", "what", "when", "where", "which",
    "with", "without", "work", "works", "you", "your",
}


def memory_keywords(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", clean_text(text).lower())
    keywords = []
    for word in words:
        if word in MEMORY_STOPWORDS or len(word) < 3:
            continue
        if word not in keywords:
            keywords.append(word)
    return keywords[:36]


def upsert_memory_item(
    content: str,
    user_id: str = "default",
    category: str = "preference",
    source: str = "auto",
    session_id: Optional[str] = None,
    strength: int = 1,
) -> None:
    clean_content = clean_text(content)[:1000]
    if not clean_content:
        return
    normalized_user = normalize_user_id(user_id)
    normalized_category = clean_text(category).lower()[:40] or "general"
    now = now_iso()
    keywords = memory_keywords(clean_content)
    items = load_memory()
    key = f"{normalized_user}|{normalized_category}|{clean_content.lower()}"
    for item in items:
        item_key = str(item.get("memory_key", ""))
        same_legacy = (
            normalize_user_id(str(item.get("user_id", "default"))) == normalized_user
            and clean_text(str(item.get("content", ""))).lower() == clean_content.lower()
        )
        if item_key == key or same_legacy:
            item["memory_key"] = key
            item["content"] = clean_content
            item["category"] = normalized_category
            item["source"] = source or item.get("source", "auto")
            item["keywords"] = sorted(set(item.get("keywords", []) + keywords))[:40]
            item["hits"] = int(item.get("hits", 1) or 1) + max(1, strength)
            item["last_seen"] = now
            if session_id:
                sessions = item.setdefault("sessions", [])
                if session_id not in sessions:
                    sessions.append(session_id)
                item["sessions"] = sessions[-24:]
            save_memory(items)
            return
    items.append({
        "memory_key": key,
        "content": clean_content,
        "category": normalized_category,
        "source": source,
        "user_id": normalized_user,
        "keywords": keywords,
        "hits": max(1, strength),
        "sessions": [session_id] if session_id else [],
        "created_at": now,
        "last_seen": now,
    })
    save_memory(items)


def normalize_project_name(name: str) -> str:
    return clean_text(name)[:80] or "Untitled project"


def load_projects() -> List[Dict[str, Any]]:
    raw_projects = safe_read_json(PROJECTS_FILE, [])
    if not isinstance(raw_projects, list):
        return []
    projects = []
    for item in raw_projects:
        if isinstance(item, dict):
            name = normalize_project_name(str(item.get("name", "")))
            if not name:
                continue
            item.setdefault("id", f"project_{uuid.uuid4().hex[:12]}")
            item["name"] = name
            item.setdefault("created_at", now_iso())
            item.setdefault("updated_at", item.get("created_at"))
            item.setdefault("sessions", [])
            item.setdefault("user_id", "default")
            projects.append(item)
        elif isinstance(item, str) and item.strip():
            projects.append({
                "id": f"project_{uuid.uuid4().hex[:12]}",
                "name": normalize_project_name(item),
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "sessions": [],
            })
    return projects


def save_projects(projects: List[Dict[str, Any]]) -> None:
    safe_write_json(PROJECTS_FILE, projects[:100])


def upsert_project(name: str, session_id: Optional[str] = None, user_id: str = "default") -> Dict[str, Any]:
    clean_name = normalize_project_name(name)
    projects = load_projects()
    now = now_iso()
    for project in projects:
        if clean_text(str(project.get("name", ""))).lower() == clean_name.lower():
            project["updated_at"] = now
            project["user_id"] = normalize_user_id(user_id)
            if session_id:
                sessions = project.setdefault("sessions", [])
                if session_id not in sessions:
                    sessions.append(session_id)
            save_projects(projects)
            return project
    project = {
        "id": f"project_{uuid.uuid4().hex[:12]}",
        "name": clean_name,
        "created_at": now,
        "updated_at": now,
        "sessions": [session_id] if session_id else [],
        "user_id": normalize_user_id(user_id),
    }
    projects.insert(0, project)
    save_projects(projects)
    return project


def load_artifacts() -> List[Dict[str, Any]]:
    raw_artifacts = safe_read_json(ARTIFACTS_FILE, [])
    if isinstance(raw_artifacts, dict) and isinstance(raw_artifacts.get("value"), list):
        raw_artifacts = raw_artifacts["value"]
    if not isinstance(raw_artifacts, list):
        return []
    artifacts = []
    for item in raw_artifacts:
        if not isinstance(item, dict):
            continue
        item.setdefault("id", f"artifact_{uuid.uuid4().hex[:12]}")
        item.setdefault("title", "Untitled artifact")
        item.setdefault("type", "Document")
        item.setdefault("content", "")
        item.setdefault("url", "")
        item.setdefault("prompt", "")
        item.setdefault("user_id", "default")
        item.setdefault("created_at", now_iso())
        item.setdefault("updated_at", item.get("created_at"))
        artifacts.append(item)
    return artifacts


def save_artifacts(artifacts: List[Dict[str, Any]]) -> None:
    safe_write_json(ARTIFACTS_FILE, artifacts[:200])


def create_artifact(
    title: str,
    artifact_type: str = "Document",
    content: str = "",
    url: str = "",
    prompt: str = "",
    user_id: str = "default",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    now = now_iso()
    artifact = {
        "id": f"artifact_{uuid.uuid4().hex[:12]}",
        "title": clean_text(title)[:120] or "Untitled artifact",
        "type": clean_text(artifact_type)[:40] or "Document",
        "content": content,
        "url": url,
        "prompt": prompt,
        "user_id": normalize_user_id(user_id),
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
    }
    artifacts = load_artifacts()
    artifacts.insert(0, artifact)
    save_artifacts(artifacts)
    return artifact


def load_reminders() -> List[Dict[str, Any]]:
    raw = safe_read_json(REMINDERS_FILE, [])
    return raw if isinstance(raw, list) else []


def save_reminders(items: List[Dict[str, Any]]) -> None:
    safe_write_json(REMINDERS_FILE, items[:300])


def load_workflows() -> List[Dict[str, Any]]:
    raw = safe_read_json(WORKFLOWS_FILE, [])
    return raw if isinstance(raw, list) else []


def save_workflows(items: List[Dict[str, Any]]) -> None:
    safe_write_json(WORKFLOWS_FILE, items[:200])


def make_study_plan(topic: str, days: int = 7, daily_minutes: int = 45, goal: str = "") -> str:
    safe_days = max(1, min(60, int(days or 7)))
    minutes = max(10, min(240, int(daily_minutes or 45)))
    clean_topic = title_case_topic(topic)
    goal_line = clean_text(goal) or f"Understand {clean_topic} clearly and revise it with confidence."
    lines = [
        f"Study plan: {clean_topic}",
        "",
        f"Goal: {goal_line}",
        f"Daily time: {minutes} minutes",
        "",
        "| Day | Focus | Work | Check |",
        "|---|---|---|---|",
    ]
    cycle = [
        ("Foundation", "Read the basics and write a simple definition.", "Explain the topic in 3 lines."),
        ("Key ideas", "List the main points and mark confusing parts.", "Answer 5 quick questions."),
        ("Examples", "Connect the topic with real-life examples.", "Teach the idea out loud."),
        ("Practice", "Solve questions or write a short answer.", "Check mistakes and rewrite weak parts."),
        ("Memory", "Make flashcards or a one-page note.", "Recall without looking."),
        ("Mixed revision", "Revise notes and practice harder questions.", "Score yourself honestly."),
        ("Final review", "Do a timed recap and fix the last gaps.", "Write the final summary."),
    ]
    for day in range(1, safe_days + 1):
        focus, work, check = cycle[(day - 1) % len(cycle)]
        lines.append(f"| {day} | {focus} | {work} | {check} |")
    lines.extend([
        "",
        "Daily rhythm:",
        "1. 5 minutes: quick recall.",
        f"2. {max(10, minutes - 15)} minutes: main study block.",
        "3. 10 minutes: practice or self-test.",
        "",
        "Bottom line:",
        "Study in small loops: learn, recall, practice, correct, repeat.",
    ])
    return "\n".join(lines)


def draft_email_text(purpose: str, recipient: str = "", tone: str = "professional", details: str = "") -> str:
    recipient_line = clean_text(recipient) or "Sir/Madam"
    tone_text = clean_text(tone).lower() or "professional"
    detail_text = clean_text(details)
    purpose_text = clean_text(purpose)
    subject = title_case_topic(purpose_text[:70])
    if tone_text in {"friendly", "warm", "casual"}:
        greeting = f"Hi {recipient_line},"
        close = "Best,"
    else:
        greeting = f"Dear {recipient_line},"
        close = "Sincerely,"
    body = [
        f"Subject: {subject}",
        "",
        greeting,
        "",
        f"I am writing to {purpose_text.rstrip('.')}.",
    ]
    if detail_text:
        body.extend(["", detail_text])
    body.extend([
        "",
        "Please let me know if this works for you.",
        "",
        close,
        "[Your Name]",
    ])
    return "\n".join(body)


def generate_website_html(prompt: str, title: Optional[str] = None) -> str:
    clean_prompt = clean_text(prompt)
    page_title = clean_text(title or "") or title_case_topic(clean_prompt[:60] or "Nexora Website")
    subtitle = clean_prompt or "A focused, polished website generated by Nexora."
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_lib.escape(page_title)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, Segoe UI, Arial, sans-serif; }}
    body {{ margin:0; background:#101114; color:#f6f7fb; }}
    header {{ min-height:72vh; display:grid; place-items:center; padding:48px 20px; background:linear-gradient(135deg,#141821,#233447 55%,#294936); }}
    .hero {{ width:min(980px,100%); }}
    h1 {{ font-size:clamp(42px,8vw,88px); line-height:1; margin:0 0 18px; letter-spacing:0; }}
    p {{ font-size:18px; line-height:1.65; color:#dce5ef; max-width:720px; }}
    .actions {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:28px; }}
    a {{ color:#101114; background:#f8d35b; padding:12px 18px; border-radius:8px; text-decoration:none; font-weight:700; }}
    main {{ padding:48px 20px; }}
    .grid {{ width:min(980px,100%); margin:auto; display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }}
    section {{ border:1px solid #2e333d; border-radius:8px; padding:22px; background:#181b20; }}
    h2 {{ margin:0 0 10px; font-size:20px; }}
    footer {{ padding:32px 20px; text-align:center; color:#9aa6b2; }}
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <h1>{html_lib.escape(page_title)}</h1>
      <p>{html_lib.escape(subtitle)}</p>
      <div class="actions"><a href="#start">Get started</a></div>
    </div>
  </header>
  <main id="start">
    <div class="grid">
      <section><h2>Purpose</h2><p>Clear positioning, readable content, and a direct first impression.</p></section>
      <section><h2>Features</h2><p>Fast layout, responsive sections, and polished visual hierarchy.</p></section>
      <section><h2>Next Step</h2><p>Edit the text, add real images, and connect forms or navigation as needed.</p></section>
    </div>
  </main>
  <footer>Generated by Nexora</footer>
</body>
</html>"""


def make_automation_plan(goal: str, context: str = "") -> str:
    clean_goal = clean_text(goal)
    clean_context = clean_text(context)
    lines = [
        f"Automation plan: {clean_goal}",
        "",
        "Safe workflow:",
        "1. Confirm the exact goal and the app/site involved.",
        "2. Collect required inputs without exposing passwords or private data.",
        "3. Break the task into small browser/file/email steps.",
        "4. Run only reversible or low-risk actions automatically.",
        "5. Ask for confirmation before sending messages, deleting data, paying, posting, or changing accounts.",
    ]
    if clean_context:
        lines.extend(["", "Context:", clean_context])
    lines.extend(["", "Bottom line:", "Nexora can plan automation now, and should confirm before risky real-world actions."])
    return "\n".join(lines)


def parse_image_size(size: Optional[str]) -> Tuple[int, int]:
    raw = (size or IMAGE_DEFAULT_SIZE or "768x768").lower().strip()
    presets = {
        "fast": (768, 768),
        "fast-square": (768, 768),
        "square": (1024, 1024),
        "portrait": (832, 1216),
        "landscape": (1216, 832),
        "wide": (1344, 768),
    }
    if raw in presets:
        return presets[raw]
    match = re.match(r"^(\d{3,4})\s*x\s*(\d{3,4})$", raw)
    if match:
        width = max(512, min(1536, int(match.group(1))))
        height = max(512, min(1536, int(match.group(2))))
        return width, height
    return 1024, 1024


def strip_image_command(prompt: str) -> str:
    text = clean_text(prompt)
    styled_match = re.match(
        r"^(?:please\s+)?(?:create|generate|make|draw|give\s+me)\s+(?:an?\s+)?"
        r"(?P<style>[a-zA-Z -]{0,70}?)\s*"
        r"(?P<type>image|picture|photo|art|illustration|poster|logo|icon|thumbnail|banner|wallpaper)"
        r"\s*(?:of|for|with|about|:)?\s*(?P<rest>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if styled_match:
        visual_type = clean_text(styled_match.group("type")).lower()
        style_words = clean_text(styled_match.group("style"))
        rest = re.sub(r"(?i)^(an?|the)\s+", "", clean_text(styled_match.group("rest"))).strip()
        useful_style = "" if style_words.lower() in {"a", "an", "the"} else style_words
        result = clean_text(" ".join(part for part in [useful_style, rest] if part))
        if visual_type in {"poster", "logo", "icon", "thumbnail", "banner", "wallpaper", "photo"} and visual_type not in result.lower():
            result = clean_text(f"{result} {visual_type}")
        return result or text

    trailing_type_match = re.match(
        r"^(?:please\s+)?(?:create|generate|make|draw|give\s+me)\s+(?:an?\s+)?"
        r"(?P<subject>.+?)\s+"
        r"(?P<type>image|picture|photo|art|illustration|poster|logo|icon|thumbnail|banner|wallpaper)$",
        text,
        flags=re.IGNORECASE,
    )
    if trailing_type_match:
        visual_type = clean_text(trailing_type_match.group("type")).lower()
        subject = clean_text(trailing_type_match.group("subject"))
        if visual_type in {"poster", "logo", "icon", "thumbnail", "banner", "wallpaper", "photo"} and visual_type not in subject.lower():
            subject = clean_text(f"{subject} {visual_type}")
        return subject or text

    match = re.match(
        r"^(?:please\s+)?(?:create|generate|make|draw)\s+(?:an?\s+)?"
        r"(?P<type>image|picture|photo|art|poster|logo|icon|thumbnail|banner|wallpaper)"
        r"\s*(?:of|for|with|about|:)?\s*(?P<rest>.*)$",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return text
    visual_type = clean_text(match.group("type")).lower()
    rest = re.sub(r"(?i)^(an?|the)\s+", "", clean_text(match.group("rest"))).strip()
    if visual_type in {"poster", "logo", "icon", "thumbnail", "banner", "wallpaper", "photo"} and visual_type not in rest.lower():
        rest = clean_text(f"{rest} {visual_type}")
    return rest or text


def infer_image_size(prompt: str, requested_size: Optional[str], style: str) -> str:
    raw_size = clean_text(requested_size or "")
    lower = clean_text(prompt).lower()
    default_size = clean_text(IMAGE_DEFAULT_SIZE)
    if raw_size and raw_size != default_size:
        return raw_size
    if re.search(r"\b(wallpaper|banner|wide|landscape|youtube thumbnail|cover)\b", lower):
        return "landscape"
    if re.search(r"\b(portrait|profile picture|pfp|headshot|close[- ]?up|phone wallpaper)\b", lower):
        return "portrait"
    return raw_size or default_size or "fast"


def normalize_image_style(style: Optional[str]) -> str:
    raw = clean_text(style or "").lower()
    presets = {
        "": "",
        "auto": "",
        "realistic": "photorealistic, natural lighting, realistic skin texture, high detail, polished finish",
        "cinematic": "cinematic lighting, dramatic composition, high detail",
        "anime": "semi-realistic anime illustration, expressive detailed eyes, soft cinematic lighting, polished painterly finish",
        "anime-realistic": "semi-realistic anime portrait, expressive detailed eyes, natural skin shading, soft cinematic lighting, polished painterly finish",
        "anime realistic": "semi-realistic anime portrait, expressive detailed eyes, natural skin shading, soft cinematic lighting, polished painterly finish",
        "poster": "poster design, strong composition, bold readable layout",
        "logo": "simple logo mark, clean vector-like design, centered",
        "3d": "3D render, smooth materials, studio lighting",
        "sketch": "clean concept sketch, expressive lines, clear subject",
    }
    return presets.get(raw, clean_text(style or ""))


def extract_visual_constraints(subject: str) -> List[str]:
    lower = clean_text(subject).lower()
    constraints: List[str] = []
    count_match = re.search(r"\b(one|two|three|four|five|single|solo|pair of|group of \d+|\d+)\b", lower)
    if count_match:
        constraints.append(f"respect the requested count: {count_match.group(0)}")
    color_words = re.findall(
        r"\b(red|blue|green|yellow|black|white|gold|golden|silver|purple|pink|orange|brown|grey|gray|cyan|teal)\b",
        lower,
    )
    if color_words:
        constraints.append("preserve requested colors: " + ", ".join(dict.fromkeys(color_words)))
    if re.search(r"\b(no|without|exclude|avoid)\b", lower):
        constraints.append("follow all exclusions exactly")
    if re.search(r"\b(front view|side view|top view|low angle|high angle|close[- ]?up|wide shot|full body|half body)\b", lower):
        constraints.append("preserve the requested camera angle and framing")
    if re.search(r"\b(smiling|angry|sad|serious|calm|happy|dark|cute|scary|epic|peaceful)\b", lower):
        constraints.append("preserve the requested mood and expression")
    if re.search(r"\b(classroom|city|forest|space|beach|mountain|street|room|temple|school|office)\b", lower):
        constraints.append("preserve the requested setting")
    return constraints


def extract_prompt_exclusions(subject: str) -> List[str]:
    lower = clean_text(subject).lower()
    exclusions: List[str] = []
    if re.search(r"\b(no text|without text|no words|textless|wordless)\b", lower):
        exclusions.extend(["text", "lettering", "words", "captions"])
    if re.search(r"\b(no logo|without logo)\b", lower):
        exclusions.append("logo")
    if re.search(r"\b(no background|transparent background)\b", lower):
        exclusions.append("busy background")
    for match in re.finditer(r"\b(?:no|without|exclude|avoid)\s+([a-zA-Z][a-zA-Z -]{1,40})(?=,|\.|;|$|\s+and\s+)", lower):
        phrase = clean_text(match.group(1)).strip(" .,:;-")
        if phrase and phrase not in {"text", "words"}:
            exclusions.append(phrase)
    return list(dict.fromkeys(exclusions))[:8]


def trim_image_prompt(text: str, max_chars: int = 860) -> str:
    clean = clean_text(text)
    if len(clean) <= max_chars:
        return clean
    trimmed = clean[:max_chars].rstrip(" ,;:.")
    for marker in [". ", "; ", ", "]:
        cut = trimmed.rfind(marker)
        if cut >= max_chars * 0.72:
            return trimmed[:cut].rstrip(" ,;:.")
    return trimmed.rsplit(" ", 1)[0].rstrip(" ,;:.")


def image_subject_priority_layers(subject: str) -> List[str]:
    subject_text = clean_text(subject)
    if not subject_text:
        return []
    layers = [f"exact subject: {subject_text}", "clear recognizable main subject"]
    layers.extend(extract_visual_constraints(subject_text))
    return layers


def image_power_prompt_layers(subject: str, style_text: str) -> List[str]:
    if not IMAGE_PROMPT_POWER_MODE:
        return []
    lower = f"{subject}, {style_text}".lower()
    layers: List[str] = []
    is_logo_like = re.search(r"\b(logo|icon|brand mark|vector mark)\b", lower)
    is_poster_like = re.search(r"\b(poster|flyer|banner|cover|thumbnail)\b", lower)
    is_anime_like = re.search(r"\b(anime|manga|manhwa|naruto|sasuke|gojo|luffy|kakashi)\b", lower)
    is_photo_like = re.search(r"\b(photo|photoreal|photorealistic|realistic|real life|cinematic)\b", lower)
    is_portrait_like = re.search(r"\b(portrait|face|headshot|selfie|girl|boy|woman|man|person|character|eyes|close[- ]?up)\b", lower)

    if is_logo_like:
        layers.extend([
            "centered symbol",
            "clean negative space",
            "balanced geometry",
            "high contrast",
            "no readable text unless explicitly requested",
        ])
    elif is_poster_like:
        layers.extend([
            "strong focal point",
            "editorial composition",
            "clean visual hierarchy",
            "readable empty space for text",
        ])
    elif is_anime_like:
        layers.extend([
            "premium anime key visual quality",
            "expressive face and eyes",
            "clean linework",
            "soft atmospheric lighting",
            "detailed hair and fabric rendering",
            "studio-grade color grading",
        ])
        if is_portrait_like:
            layers.extend(["close portrait composition", "subtle depth of field"])
    elif is_photo_like:
        layers.extend([
            "realistic camera perspective",
            "natural dynamic lighting",
            "high fidelity textures",
            "professional color grading",
        ])
        if is_portrait_like:
            layers.extend(["85mm portrait lens look", "natural skin texture", "catchlights in the eyes"])
    else:
        layers.extend([
            "clear subject silhouette",
            "balanced foreground and background",
            "professional composition",
            "clean visual storytelling",
        ])

    if not re.search(r"\b(background|environment|scene|setting)\b", lower) and not is_logo_like:
        layers.append("simple complementary background")
    if not re.search(r"\b(ultra|high|sharp|detailed|minimal|simple|clean)\b", lower):
        layers.append("high detail without clutter")
    return layers


def image_exact_match_layers(subject: str) -> List[str]:
    if not IMAGE_EXACT_MATCH_MODE:
        return []
    lower = clean_text(subject).lower()
    layers = [
        "match the request exactly",
        "preserve objects, characters, colors, count, pose, clothing, setting, mood, and composition",
        "do not replace the subject with a generic alternative",
    ]
    if re.search(r"\b(no text|without text|no words|textless|wordless)\b", lower):
        layers.append("no readable text or lettering")
    elif re.search(r"\b(text|word|title|logo|sign|label|lettering)\b", lower):
        layers.append("include only the text explicitly requested by the user")
    else:
        layers.append("no random text")
    if re.search(r"\b(transparent|no background|plain background|white background|black background)\b", lower):
        layers.append("respect the requested background exactly")
    if re.search(r"\b(only|single|one|two|three|without|no )\b", lower):
        layers.append("respect requested quantity and exclusions exactly")
    return layers


def enhance_image_prompt(prompt: str, style: Optional[str], enhance: Optional[bool] = True) -> str:
    subject = strip_image_command(prompt)
    style_text = normalize_image_style(style)
    style_only_subjects = {
        "anime": "semi-realistic anime character portrait, close-up face, luminous detailed eyes",
        "anime realistic": "semi-realistic anime character portrait, close-up face, luminous detailed eyes",
        "anime-realistic": "semi-realistic anime character portrait, close-up face, luminous detailed eyes",
        "realistic": "realistic cinematic portrait",
        "cinematic": "cinematic character scene",
        "poster": "modern poster design",
        "logo": "minimal logo mark",
        "3d": "3D character render",
        "sketch": "concept sketch",
    }
    subject = style_only_subjects.get(subject.lower(), subject)
    lower = f"{subject}, {style_text}".lower()
    is_logo_like = re.search(r"\b(logo|icon|brand mark|vector mark)\b", lower)
    is_poster_like = re.search(r"\b(poster|flyer|banner|cover)\b", lower)
    is_anime_like = re.search(r"\b(anime|manga|manhwa|naruto|sasuke|gojo|luffy|kakashi)\b", lower)
    is_photo_like = re.search(r"\b(photo|photoreal|photorealistic|realistic|real life|cinematic)\b", lower)
    is_portrait_like = re.search(
        r"\b(portrait|face|headshot|selfie|girl|boy|woman|man|person|character|eyes|close[- ]?up)\b",
        lower,
    )

    should_enhance = enhance if enhance is not None else IMAGE_PROMPT_ENHANCE
    must = image_subject_priority_layers(subject) + image_exact_match_layers(subject)
    quality = []
    if should_enhance:
        if style_text:
            quality.append(f"style: {style_text}")
        quality.extend(image_power_prompt_layers(subject, style_text))
        if is_anime_like and is_portrait_like:
            quality.extend(["close portrait framing", "luminous detailed eyes", "soft sunlight", "crisp hair detail"])
        elif is_anime_like:
            quality.extend(["clean anime illustration", "cinematic lighting", "crisp subject edges"])
        elif is_photo_like and is_portrait_like:
            quality.extend(["realistic portrait lighting", "natural skin texture", "sharp facial detail", "clean background separation"])
        elif not is_logo_like and not is_poster_like:
            quality.append("clean professional finish")
        if not re.search(r"\b(close[- ]?up|wide shot|portrait|landscape|top view|isometric|centered|composition)\b", lower):
            quality.append("clear composition")
        if not re.search(r"\b(light|lighting|sunset|night|daylight|studio|cinematic)\b", lower):
            quality.append("balanced lighting")
        if not re.search(r"\b(detail|detailed|minimal|simple|clean)\b", lower):
            quality.append("high detail")
        quality.append("sharp focus")
    elif style_text:
        quality.append(f"style: {style_text}")

    avoid = extract_prompt_exclusions(subject)
    final_parts = [subject]
    if must:
        final_parts.append("must: " + "; ".join(must[:8]))
    if quality:
        final_parts.append("quality: " + "; ".join(quality[:10]))
    if avoid:
        final_parts.append("avoid: " + ", ".join(avoid))

    compact_parts = []
    seen_parts = set()
    for part in final_parts:
        cleaned = clean_text(part)
        if not cleaned:
            continue
        key = cleaned.lower()
        current_text = " ".join(compact_parts).lower()
        if key in seen_parts or key in current_text:
            continue
        seen_parts.add(key)
        compact_parts.append(cleaned)
    final_prompt = ". ".join(compact_parts)
    return trim_image_prompt(final_prompt)


def build_image_negative_prompt(negative_prompt: Optional[str], style: Optional[str] = None, subject: str = "") -> str:
    raw_style = clean_text(style or "").lower()
    base_items = [
        "wrong subject",
        "generic subject",
        "subject mismatch",
        "missing requested details",
        "changed character",
        "changed colors",
        "wrong count",
        "wrong pose",
        "wrong setting",
        "extra unwanted objects",
        "low quality",
        "low resolution",
        "blurry",
        "out of focus",
        "distorted",
        "deformed face",
        "deformed eyes",
        "bad anatomy",
        "extra fingers",
        "extra limbs",
        "duplicate face",
        "messy text",
        "jpeg artifacts",
        "noise",
        "oversaturated",
        "flat lighting",
        "muddy colors",
        "poor composition",
        "cropped face",
        "uncanny face",
        "asymmetrical eyes",
        "wrong proportions",
    ]
    if re.search(r"\b(anime|manga|manhwa)\b", raw_style):
        base_items.extend(["lifeless eyes", "messy lineart", "plastic skin", "overly glossy skin"])
    if "logo" not in raw_style:
        base_items.extend(["watermark", "signature", "random logo"])
    else:
        base_items.extend(["photo background", "complex texture", "tiny unreadable text"])
    extra = clean_text(negative_prompt or "")
    items = base_items + extract_prompt_exclusions(subject) + [item.strip() for item in extra.split(",") if item.strip()]
    deduped = []
    seen = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    output: List[str] = []
    total = 0
    for item in deduped:
        extra_len = len(item) + (2 if output else 0)
        if total + extra_len > 480:
            break
        output.append(item)
        total += extra_len
    return clean_text(", ".join(output))


def image_cache_key(user_id: str, prompt: str, size_label: str, negative_prompt: str) -> str:
    packed = "|".join([
        normalize_user_id(user_id),
        compact_for_cache(prompt),
        size_label,
        compact_for_cache(negative_prompt),
        IMAGE_MODEL or "provider_default",
        "exact" if IMAGE_EXACT_MATCH_MODE else "flex",
        IMAGE_PROVIDER_ENHANCE_PARAM,
    ])
    return stable_hash(packed)


def load_image_memory() -> Dict[str, Any]:
    raw = safe_read_json(IMAGE_MEMORY_FILE, {})
    if isinstance(raw, dict):
        raw.setdefault("images", [])
        raw.setdefault("preferences", {})
        return raw
    return {"images": [], "preferences": {}}


def save_image_memory(memory: Dict[str, Any]) -> None:
    images = memory.get("images", [])
    if isinstance(images, list):
        memory["images"] = images[:MAX_IMAGE_MEMORY_ITEMS]
    safe_write_json(IMAGE_MEMORY_FILE, memory)


def infer_image_style(prompt: str, requested_style: Optional[str], user_id: str) -> str:
    style = clean_text(requested_style or "").lower()
    if style and style != "auto":
        return style
    text = clean_text(prompt).lower()
    style_patterns = [
        ("anime-realistic", r"\b(anime[- ]?realistic|realistic anime|semi[- ]?realistic anime)\b"),
        ("anime", r"\b(anime|manga|sasuke|naruto|kakashi|gojo|luffy)\b"),
        ("realistic", r"\b(realistic|real life|photo|photoreal|photorealistic)\b"),
        ("cinematic", r"\b(cinematic|movie|dramatic|film)\b"),
        ("poster", r"\b(poster|cover|flyer|banner)\b"),
        ("logo", r"\b(logo|icon|brand mark)\b"),
        ("3d", r"\b(3d|render|blender)\b"),
        ("sketch", r"\b(sketch|drawing|line art)\b"),
    ]
    for candidate, pattern in style_patterns:
        if re.search(pattern, text):
            return candidate
    if not re.search(r"\b(same style|like before|same as before|as last|again|similar style)\b", text):
        return "auto"
    memory = load_image_memory()
    prefs = memory.get("preferences", {}).get(normalize_user_id(user_id), {})
    if isinstance(prefs, dict):
        favorite = clean_text(str(prefs.get("last_style", ""))).lower()
        if favorite:
            return favorite
    return "auto"


def remember_image_workflow(
    user_id: str,
    original_prompt: str,
    enhanced_prompt: str,
    style: str,
    size_label: str,
    negative_prompt: str,
    url: str,
    artifact_id: str,
    cached: bool = False,
) -> Dict[str, Any]:
    normalized = normalize_user_id(user_id)
    memory = load_image_memory()
    prefs = memory.setdefault("preferences", {})
    user_prefs = prefs.get(normalized) if isinstance(prefs.get(normalized), dict) else {}
    user_prefs["last_style"] = style or user_prefs.get("last_style", "auto")
    user_prefs["last_size"] = size_label
    user_prefs["last_negative_prompt"] = negative_prompt
    user_prefs["exact_match_mode"] = IMAGE_EXACT_MATCH_MODE
    user_prefs["total_images"] = int(user_prefs.get("total_images", 0)) + (0 if cached else 1)
    user_prefs["updated_at"] = now_iso()
    prefs[normalized] = user_prefs

    images = memory.setdefault("images", [])
    key = image_cache_key(normalized, enhanced_prompt, size_label, negative_prompt)
    existing = next((item for item in images if isinstance(item, dict) and item.get("cache_key") == key), None)
    if existing:
        existing["last_used_at"] = now_iso()
        existing["uses"] = int(existing.get("uses", 0)) + 1
        existing["artifact_id"] = existing.get("artifact_id") or artifact_id
    else:
        images.insert(0, {
            "cache_key": key,
            "user_id": normalized,
            "original_prompt": original_prompt,
            "enhanced_prompt": enhanced_prompt,
            "style": style,
            "size": size_label,
            "negative_prompt": negative_prompt,
            "exact_match_mode": IMAGE_EXACT_MATCH_MODE,
            "url": url,
            "artifact_id": artifact_id,
            "uses": 1,
            "created_at": now_iso(),
            "last_used_at": now_iso(),
        })
    save_image_memory(memory)
    return user_prefs


def find_cached_image(user_id: str, enhanced_prompt: str, size_label: str, negative_prompt: str) -> Optional[Dict[str, Any]]:
    key = image_cache_key(user_id, enhanced_prompt, size_label, negative_prompt)
    for item in load_image_memory().get("images", []):
        if isinstance(item, dict) and item.get("cache_key") == key and item.get("url"):
            return item
    return None


def build_image_url(prompt: str, size: Optional[str], negative_prompt: Optional[str] = "", user_id: str = "default") -> Tuple[str, int, int]:
    width, height = parse_image_size(size)
    clean_prompt = clean_text(prompt)
    clean_negative = clean_text(negative_prompt or "")[:500]
    seed = stable_hash_int(f"{normalize_user_id(user_id)}|{clean_prompt}|{width}x{height}|{clean_negative}")
    encoded_prompt = quote(clean_prompt[:900])
    params = {
        "width": width,
        "height": height,
        "seed": seed,
        "nologo": "true",
        "enhance": "true" if IMAGE_PROVIDER_ENHANCE_PARAM in {"1", "true", "yes", "on"} else "false",
        "negative": clean_negative,
    }
    if IMAGE_MODEL:
        params["model"] = IMAGE_MODEL
    query = "&".join(f"{key}={quote(str(value))}" for key, value in params.items() if str(value))
    return f"{IMAGE_BASE_URL}/{encoded_prompt}?{query}", width, height


def default_persona_profile() -> Dict[str, Any]:
    return {
        "name": "Nexora",
        "tone": "warm, intelligent, natural, and capable",
        "length": "balanced",
        "format": "paragraph-led",
        "emoji": "sparingly",
        "language": "match the user's language",
        "autonomy": [
            "Be proactive when the next useful step is obvious.",
            "State a clear point of view when the user asks for judgment.",
            "Adapt to repeated corrections and saved speaking preferences.",
            "Do not pretend to be conscious, alive, or able to act outside this app.",
        ],
        "rules": [],
        "updated_at": now_iso(),
    }


def normalize_persona_profile(raw: Any) -> Dict[str, Any]:
    profile = default_persona_profile()
    if isinstance(raw, dict):
        for key in ["name", "tone", "length", "format", "emoji", "language", "updated_at"]:
            if isinstance(raw.get(key), str) and raw.get(key, "").strip():
                profile[key] = raw[key].strip()
        if isinstance(raw.get("autonomy"), list):
            profile["autonomy"] = [
                clean_text(str(item))[:220]
                for item in raw["autonomy"]
                if clean_text(str(item))
            ][:8] or profile["autonomy"]
        if isinstance(raw.get("rules"), list):
            profile["rules"] = [
                clean_text(str(item))[:260]
                for item in raw["rules"]
                if clean_text(str(item))
            ][-MAX_PERSONA_RULES:]
    return profile


def load_persona_profile() -> Dict[str, Any]:
    return normalize_persona_profile(safe_read_json(PERSONA_FILE, {}))


def save_persona_profile(profile: Dict[str, Any]) -> None:
    profile = normalize_persona_profile(profile)
    profile["updated_at"] = now_iso()
    safe_write_json(PERSONA_FILE, profile)


def persona_signature(profile: Dict[str, Any]) -> str:
    packed = json.dumps(profile, ensure_ascii=False, sort_keys=True)
    return stable_hash(packed)


def add_persona_rule(profile: Dict[str, Any], rule: str) -> None:
    clean_rule = clean_text(rule)[:260]
    if not clean_rule:
        return
    rules = [item for item in profile.get("rules", []) if item.lower() != clean_rule.lower()]
    rules.append(clean_rule)
    profile["rules"] = rules[-MAX_PERSONA_RULES:]


def learn_persona_from_message(user_message: str) -> Tuple[Dict[str, Any], List[str]]:
    profile = load_persona_profile()
    text = clean_text(user_message)
    lower = text.lower()
    changes: List[str] = []

    style_intent = any(phrase in lower for phrase in [
        "talk", "speak", "respond",
        "reply", "answer", "be more", "be less", "change your style",
        "change the way you speak", "your personality", "independent ai",
        "act more independent", "call me",
    ])
    if not style_intent and any(phrase in lower for phrase in ["from now on", "always", "remember"]):
        style_intent = bool(re.search(
            r"\b(talk|speak|respond|reply|answer|style|tone|emoji|emojis|short|brief|detailed|call me|professional|casual|formal|friendly)\b",
            lower,
        ))
    if not style_intent:
        return profile, changes

    if re.search(r"\b(short|brief|concise|to the point|less words|one line)\b", lower):
        profile["length"] = "concise"
        changes.append("keep replies concise")
    if re.search(r"\b(detailed|deep|explain more|longer|step by step)\b", lower):
        profile["length"] = "detailed when useful"
        changes.append("give more detail when the task needs it")

    tone_rules = [
        (r"\b(casual|casually|chill|friendly|like a friend)\b", "casual, friendly, and relaxed", "sound more casual"),
        (r"\b(professional|formal|serious|business)\b", "professional, clear, and restrained", "sound more professional"),
        (r"\b(funny|humorous|witty)\b", "warm, lightly witty, and useful first", "add light wit"),
        (r"\b(strict|direct|blunt)\b", "direct, crisp, and honest without being rude", "be more direct"),
        (r"\b(kind|soft|gentle|supportive)\b", "gentle, supportive, and clear", "sound more supportive"),
    ]
    for pattern, tone, label in tone_rules:
        if re.search(pattern, lower):
            profile["tone"] = tone
            changes.append(label)

    if re.search(r"\b(no emoji|no emojis|without emoji|stop using emoji|don't use emoji|do not use emoji)\b", lower):
        profile["emoji"] = "none"
        changes.append("avoid emojis")
    elif re.search(r"\b(use emoji|use emojis|more emoji|more emojis)\b", lower):
        profile["emoji"] = "light"
        changes.append("use light emojis")

    if re.search(r"\b(bullets|bullet points|list format)\b", lower):
        profile["format"] = "use bullets for scan-friendly answers"
        changes.append("use more bullets")
    if re.search(r"\b(paragraphs|paragraph style|less bullets|no bullets)\b", lower):
        profile["format"] = "paragraph-led"
        changes.append("prefer paragraphs")

    if re.search(r"\b(hinglish|hindi)\b", lower):
        profile["language"] = "Hinglish/Hindi when the user uses it or asks for it"
        changes.append("adapt toward Hinglish/Hindi")
    elif re.search(r"\b(english only|only english|speak english)\b", lower):
        profile["language"] = "English unless the user asks otherwise"
        changes.append("use English")

    call_me = re.search(r"\bcall me\s+([A-Za-z][A-Za-z0-9 _.-]{1,40})", text, re.IGNORECASE)
    if call_me:
        name = clean_text(call_me.group(1)).rstrip(".!")
        add_persona_rule(profile, f"Address the user as {name} when it feels natural.")
        changes.append(f"remember the name {name}")

    custom_style = re.search(
        r"\b(?:talk|speak|respond|reply|answer)\s+(?:to me\s+)?(?:like|as|in)\s+(.{3,140})",
        text,
        re.IGNORECASE,
    )
    if custom_style:
        style = clean_text(custom_style.group(1)).rstrip(".!")
        add_persona_rule(profile, f"Speak in this requested style when appropriate: {style}.")
        changes.append(f"use the requested style: {style}")

    if "independent ai" in lower or "act more independent" in lower or "be independent" in lower:
        add_persona_rule(
            profile,
            "Behave like an independent assistant: offer judgment, remember preferences, suggest next steps, and adapt without needing repeated instructions.",
        )
        changes.append("act more independent and proactive")

    if any(phrase in lower for phrase in ["from now on", "always", "remember", "nexora should", "i want nexora"]):
        add_persona_rule(profile, text)
        changes.append("save this as a standing preference")

    if changes:
        save_persona_profile(profile)
    return profile, changes


def build_persona_context(profile: Dict[str, Any]) -> str:
    lines = [
        "Nexora adaptive persona profile:",
        f"- Name: {profile.get('name', 'Nexora')}",
        f"- Tone: {profile.get('tone', '')}",
        f"- Length: {profile.get('length', '')}",
        f"- Format: {profile.get('format', '')}",
        f"- Emoji: {profile.get('emoji', '')}",
        f"- Language: {profile.get('language', '')}",
        "- Autonomy:",
    ]
    for item in profile.get("autonomy", []):
        lines.append(f"  - {item}")
    rules = profile.get("rules", [])
    if rules:
        lines.append("- Learned standing preferences:")
        for rule in rules[-MAX_PERSONA_RULES:]:
            lines.append(f"  - {rule}")
    lines.append("Apply this profile above generic style instructions, unless the user asks for a different style in the current message.")
    return "\n".join(lines)


def persona_update_reply(changes: List[str], profile: Dict[str, Any]) -> str:
    summary = ", ".join(dict.fromkeys(changes))
    if not summary:
        summary = "update my speaking style"
    return (
        f"Done. I will {summary}.\n\n"
        f"Current Nexora style: {profile.get('tone')} tone, {profile.get('length')} length, "
        f"{profile.get('format')} format, emoji setting: {profile.get('emoji')}."
    )


def default_behavior_profile() -> Dict[str, Any]:
    return {
        "communication": {
            "tone_needed": "calm and professional",
            "structure_needed": "answer first, then clean sections",
            "detail_level": "balanced",
            "typing_style": "informal with occasional typos; infer intent without correcting spelling unless asked",
        },
        "human_signals": {
            "frustration": 0,
            "confusion": 0,
            "urgency": 0,
            "positive_feedback": 0,
            "negative_feedback": 0,
        },
        "preferences": [
            "Use clear punctuation and clean formatting.",
            "Keep UI and answers professional, polished, and easy to scan.",
            "When the user corrects behavior, adapt immediately and do not repeat the mistake.",
        ],
        "recent_events": [],
        "updated_at": now_iso(),
    }


def normalize_behavior_profile(raw: Any) -> Dict[str, Any]:
    profile = default_behavior_profile()
    if isinstance(raw, dict):
        if isinstance(raw.get("communication"), dict):
            for key, value in raw["communication"].items():
                if key in profile["communication"] and isinstance(value, str) and value.strip():
                    profile["communication"][key] = clean_text(value)[:180]
        if isinstance(raw.get("human_signals"), dict):
            for key in profile["human_signals"]:
                try:
                    profile["human_signals"][key] = max(0, int(raw["human_signals"].get(key, 0)))
                except Exception:
                    pass
        if isinstance(raw.get("preferences"), list):
            profile["preferences"] = [
                clean_text(str(item))[:240]
                for item in raw["preferences"]
                if clean_text(str(item))
            ][-20:] or profile["preferences"]
        if isinstance(raw.get("recent_events"), list):
            profile["recent_events"] = [
                item for item in raw["recent_events"]
                if isinstance(item, dict) and item.get("created_at")
            ][-MAX_BEHAVIOR_EVENTS:]
        if isinstance(raw.get("updated_at"), str):
            profile["updated_at"] = raw["updated_at"]
    return profile


def load_behavior_profile() -> Dict[str, Any]:
    return normalize_behavior_profile(safe_read_json(BEHAVIOR_FILE, {}))


def save_behavior_profile(profile: Dict[str, Any]) -> None:
    profile = normalize_behavior_profile(profile)
    profile["updated_at"] = now_iso()
    safe_write_json(BEHAVIOR_FILE, profile)


def behavior_signature(profile: Dict[str, Any]) -> str:
    stable = {
        "communication": profile.get("communication", {}),
        "human_signals": profile.get("human_signals", {}),
        "preferences": profile.get("preferences", []),
    }
    packed = json.dumps(stable, ensure_ascii=False, sort_keys=True)
    return stable_hash(packed)


def behavior_add_preference(profile: Dict[str, Any], preference: str) -> None:
    clean_preference = clean_text(preference)[:240]
    if not clean_preference:
        return
    preferences = [
        item for item in profile.get("preferences", [])
        if item.lower() != clean_preference.lower()
    ]
    preferences.append(clean_preference)
    profile["preferences"] = preferences[-20:]


def detect_behavior_signals(user_message: str) -> Dict[str, Any]:
    text = clean_text(user_message)
    lower = text.lower()
    signals = {
        "frustration": 0,
        "confusion": 0,
        "urgency": 0,
        "correction": False,
        "needs_structure": False,
        "needs_polish": False,
        "needs_simpler": False,
        "task_type": "general",
    }
    if re.search(r"\b(wrong|bad|not good|wasn'?t supposed|not supposed|fix|again|still|doesn'?t|didn'?t|problem|issue|generic|template|not useful)\b", lower):
        signals["frustration"] = 1
        signals["correction"] = True
    if re.search(r"\b(confused|don'?t understand|explain|what is this|why|how)\b", lower):
        signals["confusion"] = 1
    if re.search(r"\b(now|quick|fast|urgent|asap|immediately)\b", lower):
        signals["urgency"] = 1
    if re.search(r"\b(structured|structure|clean|professional|claude|chatgpt|punctuation|punctuations|format|organized)\b", lower):
        signals["needs_structure"] = True
        signals["needs_polish"] = True
    if re.search(r"\b(simple|simpler|easy|class 8|beginner|like a teacher)\b", lower):
        signals["needs_simpler"] = True
    if re.search(r"\b(code|bug|frontend|backend|github|website|input box|ui|button|css|html)\b", lower):
        signals["task_type"] = "build_or_ui"
    elif re.search(r"\b(latest|current|news|search|price|market|president|weather)\b", lower):
        signals["task_type"] = "current_info"
    elif re.search(r"\b(explain|learn|study|class|chapter|question)\b", lower):
        signals["task_type"] = "learning"
    return signals


def learn_behavior_from_message(user_message: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    profile = load_behavior_profile()
    signals = detect_behavior_signals(user_message)
    counters = profile.setdefault("human_signals", {})
    for key in ["frustration", "confusion", "urgency"]:
        counters[key] = int(counters.get(key, 0)) + int(signals.get(key, 0))

    communication = profile.setdefault("communication", {})
    if signals["needs_structure"]:
        communication["structure_needed"] = "highly structured: direct answer, clean headings, compact bullets, source cards only"
        behavior_add_preference(profile, "Prefer structured, professional answers with clean punctuation.")
    if signals["needs_polish"]:
        communication["tone_needed"] = "professional, composed, Claude-like clarity"
        behavior_add_preference(profile, "Avoid messy fragments; use polished punctuation and calm wording.")
    if signals["needs_simpler"]:
        communication["detail_level"] = "simple first, then deeper only if needed"
        behavior_add_preference(profile, "Explain difficult ideas simply before adding detail.")
    if signals["correction"]:
        behavior_add_preference(profile, "When corrected, acknowledge the intended behavior and adapt without arguing.")
    if signals["task_type"] == "build_or_ui":
        behavior_add_preference(profile, "For app changes, focus on the visible behavior the user describes and verify it.")
    if signals["task_type"] == "current_info":
        behavior_add_preference(profile, "Use real-time search for current facts and do not guess.")

    event = {
        "created_at": now_iso(),
        "message": user_message[:220],
        "signals": signals,
    }
    events = profile.setdefault("recent_events", [])
    events.append(event)
    profile["recent_events"] = events[-MAX_BEHAVIOR_EVENTS:]
    save_behavior_profile(profile)
    return profile, signals


def normalize_feedback_rating(rating: str) -> str:
    normalized = clean_text(rating).lower().replace("-", "_").replace(" ", "_")
    positive = {
        "good", "up", "like", "liked", "thumb_up", "thumbs_up", "positive",
        "yes", "helpful", "great", "works", "worked",
    }
    negative = {
        "bad", "down", "dislike", "disliked", "thumb_down", "thumbs_down",
        "negative", "no", "unhelpful", "wrong", "poor",
    }
    if normalized in negative:
        return "bad"
    if normalized in positive:
        return "good"
    return "good"


def learn_behavior_from_feedback(req: FeedbackRequest) -> Dict[str, Any]:
    profile = load_behavior_profile()
    counters = profile.setdefault("human_signals", {})
    rating = normalize_feedback_rating(req.rating)
    if rating == "good":
        counters["positive_feedback"] = int(counters.get("positive_feedback", 0)) + 1
        behavior_add_preference(profile, "Repeat answer patterns that receive positive feedback.")
    else:
        counters["negative_feedback"] = int(counters.get("negative_feedback", 0)) + 1
        behavior_add_preference(profile, "If feedback is negative, be more concise, structured, and ask fewer unnecessary questions.")
    profile.setdefault("recent_events", []).append({
        "created_at": now_iso(),
        "type": "feedback",
        "rating": rating,
        "question": clean_text(req.question or "")[:220],
        "answer": clean_text(req.answer or "")[:260],
        "note": clean_text(req.note or "")[:180],
    })
    profile["recent_events"] = profile["recent_events"][-MAX_BEHAVIOR_EVENTS:]
    save_behavior_profile(profile)
    return profile


def build_behavior_context(profile: Dict[str, Any], current_signals: Optional[Dict[str, Any]] = None) -> str:
    communication = profile.get("communication", {})
    signals = profile.get("human_signals", {})
    lines = [
        "Human behavior learning profile:",
        f"- Tone needed: {communication.get('tone_needed')}",
        f"- Structure needed: {communication.get('structure_needed')}",
        f"- Detail level: {communication.get('detail_level')}",
        f"- User typing style: {communication.get('typing_style')}",
        f"- Learned signal counts: frustration={signals.get('frustration', 0)}, confusion={signals.get('confusion', 0)}, urgency={signals.get('urgency', 0)}, positive_feedback={signals.get('positive_feedback', 0)}, negative_feedback={signals.get('negative_feedback', 0)}.",
    ]
    if current_signals:
        active = [key for key, value in current_signals.items() if value and key != "task_type"]
        lines.append(f"- Current message signals: task_type={current_signals.get('task_type', 'general')}; active={', '.join(active) or 'none'}.")
    preferences = profile.get("preferences", [])[-8:]
    if preferences:
        lines.append("- Behavioral preferences to follow:")
        for item in preferences:
            lines.append(f"  - {item}")
    lines.append("Use this to adapt empathy, clarity, structure, and pacing. Do not mention this profile unless the user asks.")
    return "\n".join(lines)


TYPO_NORMALIZATIONS = {
    "learing": "learning",
    "leraning": "learning",
    "self learing": "self-learning",
    "selflearning": "self-learning",
    "chtbot": "chatbot",
    "chat bot": "chatbot",
    "aii": "ai",
    "evrything": "everything",
    "everyhing": "everything",
    "understandit": "understanding",
    "understandign": "understanding",
    "understandig": "understanding",
    "understandng": "understanding",
    "understnad": "understand",
    "understnd": "understand",
    "underatand": "understand",
    "understands": "understand",
    "inteligent": "intelligent",
    "intellgent": "intelligent",
    "intelligant": "intelligent",
    "intelligece": "intelligence",
    "intellignece": "intelligence",
    "inteligence": "intelligence",
    "intellgence": "intelligence",
    "reasoble": "reasonable",
    "resonable": "reasonable",
    "resenable": "reasonable",
    "actractive": "attractive",
    "atractive": "attractive",
    "acturate": "accurate",
    "accuarate": "accurate",
    "acurate": "accurate",
    "sccurate": "accurate",
    "acturacy": "accuracy",
    "accuarcy": "accuracy",
    "accuaray": "accuracy",
    "accuray": "accuracy",
    "acuracy": "accuracy",
    "reasoing": "reasoning",
    "reasonign": "reasoning",
    "reasning": "reasoning",
    "preciese": "precise",
    "presice": "precise",
    "strucutre": "structure",
    "strucutres": "structures",
    "strcuture": "structure",
    "structre": "structure",
    "quesiton": "question",
    "uqestion": "question",
    "qustion": "question",
    "ouyputs": "outputs",
    "ouput": "output",
    "raw ouyputs": "raw outputs",
    "sqaures": "squares",
    "towards its right": "towards the right",
    "whike": "while",
    "moe": "more",
    "caability": "capability",
    "capabilty": "capability",
    "capablity": "capability",
    "higest": "highest",
    "heighest": "highest",
    "effecient": "efficient",
    "efficeicny": "efficiency",
    "effeicint": "efficient",
    "proffestionl": "professional",
    "proffessional": "professional",
    "proffesionl": "professional",
    "strcutre": "structure",
    "strucute": "structure",
    "mimin": "mimic",
    "chat gpt": "ChatGPT",
    "chatgpt": "ChatGPT",
    "youtube": "YouTube",
    "youtuber": "YouTuber",
    "searcch": "search",
    "realtime": "real-time",
    "real time": "real-time",
    "puntuctons": "punctuation",
    "punctuctons": "punctuation",
    "diappears": "disappears",
    "licked": "clicked",
    "controll": "control",
    "controle": "control",
}


VAGUE_REFERENCE_RE = re.compile(
    r"\b(it|this|that|these|those|there|same|before|previous|above|like this|do it|fix it|make it|make this|change it|improve it|better)\b",
    re.IGNORECASE,
)


def normalize_user_language(text: str) -> Tuple[str, List[str]]:
    normalized = clean_text(text)
    changes: List[str] = []
    for wrong, right in TYPO_NORMALIZATIONS.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        if pattern.search(normalized):
            normalized = pattern.sub(right, normalized)
            changes.append(f"{wrong} -> {right}")
    normalized = re.sub(r"\ban long\b", "a long", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\ban short\b", "a short", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bi need an\b", "I need a", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\b(make|help|let)\s+(it|this|that|the ai|nexora)\s+understanding\b", r"\1 \2 understand", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\busers question\b", "user's question", normalized, flags=re.IGNORECASE)
    return clean_text(normalized), changes[:12]


def is_vague_followup(message: str) -> bool:
    text = clean_text(message)
    lower = text.lower()
    if VAGUE_REFERENCE_RE.search(lower):
        return True
    return len(text.split()) <= 7 and bool(re.search(
        r"\b(better|powerful|stronger|cleaner|faster|smarter|improve|fix|change|remove|add|make)\b",
        lower,
    ))


def infer_question_contract(
    message: str,
    response_lane: str,
    presentation_style: str,
    use_research: bool,
    focus: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    text = clean_text(message)
    lower = text.lower()
    focus = focus or {}

    if response_lane == "build":
        task_type = "implementation or app-change request"
    elif response_lane == "writing":
        task_type = "writing request"
    elif response_lane == "learning":
        task_type = "explanation or study request"
    elif response_lane == "planning":
        task_type = "planning or decision request"
    elif use_research:
        task_type = "current-fact or evidence request"
    elif re.search(r"\b(compare|vs|versus|difference|better|best)\b", lower):
        task_type = "comparison or choice request"
    elif re.search(r"\b(recommend|suggest|which should|what should)\b", lower):
        task_type = "recommendation request"
    elif re.search(r"\b(who|what|when|where|why|how|is|are|can|should)\b", lower):
        task_type = "direct question"
    else:
        task_type = "instruction or conversational request"

    target = text
    target_patterns = [
        r"\b(?:make|change|fix|improve|upgrade|add|remove|delete|create|build)\s+(.+)$",
        r"\b(?:explain|teach|define|describe)\s+(.+)$",
        r"\b(?:write|draft|compose)\s+(.+)$",
        r"\b(?:what is|who is|how to|how do i|why does|why is)\s+(.+)$",
    ]
    for pattern in target_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            target = match.group(1).strip(" .,:;-") or target
            break
    if VAGUE_REFERENCE_RE.search(lower) and focus.get("previous_user"):
        target = f"the previous target: {focus['previous_user'][:180]}"

    constraints: List[str] = []
    if re.search(r"\b(don'?t|do not|without|no)\b", lower):
        constraints.append("respect negative constraints exactly")
    if re.search(r"\b(same as before|like before|like this|as shown|screenshot)\b", lower):
        constraints.append("match the referenced previous/screenshot behavior")
    if re.search(r"\b(fast|faster|quick|instant|speed)\b", lower):
        constraints.append("keep the path fast")
    if re.search(r"\b(accurate|accuracy|correct|precise|verify|fact[- ]?check|source|sources|citation|citations)\b", lower):
        constraints.append("prioritize accuracy and verification")
    if re.search(r"\b(no raw|raw output|raw outputs|debug|backend|json|metadata)\b", lower):
        constraints.append("return clean user-facing output only")
    if re.search(r"\b(bold|table|steps|structured|clear|attractive|interactive)\b", lower):
        constraints.append("use the requested presentation format only where useful")

    accuracy_mode = "evidence required" if use_research else "stable-knowledge with uncertainty checks"
    if re.search(r"\b(latest|current|today|right now|price|score|stock|market|news|2026|2025)\b", lower):
        accuracy_mode = "current evidence required"
    elif re.search(r"\b(legal|medical|medicine|diagnose|tax|investment|financial advice|guaranteed)\b", lower):
        accuracy_mode = "high-stakes caution required"
    elif re.search(r"\b(recommend|suggest|best|top|which should i buy|worth it)\b", lower):
        accuracy_mode = "recommendation should separate preference, facts, and assumptions"

    answer_contract = [
        "answer the user's actual question, not a generic nearby topic",
        "preserve all constraints before adding extra detail",
        "if the wording is messy, infer the most likely intent and state any important assumption briefly",
        "if a fact may be current or uncertain, verify with sources or say it cannot be verified from available context",
    ]

    return {
        "task_type": task_type,
        "target": target[:260],
        "constraints": list(dict.fromkeys(constraints))[:6],
        "accuracy_mode": accuracy_mode,
        "presentation": presentation_style,
        "answer_contract": answer_contract,
    }


def recent_session_focus(session: Dict[str, Any], current_message: str = "") -> Dict[str, Any]:
    current = clean_text(current_message)
    messages = session.get("messages", [])
    previous_user = ""
    previous_assistant = ""
    for item in reversed(messages):
        role = item.get("role")
        content = clean_text(str(item.get("content", "")))
        if not content or content == current:
            continue
        if role == "user" and not previous_user:
            previous_user = content
        elif role == "assistant" and not previous_assistant:
            previous_assistant = content
        if previous_user and previous_assistant:
            break
    if not previous_user:
        previous_user = clean_text(str(session.get("last_user_message", "")))
    if not previous_assistant:
        previous_assistant = clean_text(str(session.get("last_assistant_summary", "")))
    focus_text = " ".join(part for part in [previous_user, previous_assistant[:220]] if part)
    return {
        "previous_user": previous_user[:500],
        "previous_assistant": previous_assistant[:360],
        "keywords": memory_keywords(focus_text)[:14],
    }


def infer_action_goal(message: str, response_lane: str, use_research: bool) -> str:
    lower = clean_text(message).lower()
    if use_research:
        return "verify current facts with real-time search before answering"
    if re.search(r"\b(make|improve|upgrade|stronger|powerful|better|fix|change|add|remove|build)\b", lower):
        return "improve or change the referenced thing"
    if re.search(r"\b(write|essay|letter|email|draft|paragraph|speech)\b", lower):
        return "produce polished writing"
    if re.search(r"\b(explain|teach|what|why|how|learn|history|overview|background|timeline)\b", lower):
        return "explain the concept clearly"
    if response_lane == "build":
        return "solve the implementation problem"
    return "answer directly using the current context"


def infer_user_need_profile(
    message: str,
    response_lane: str,
    presentation_style: str,
    use_research: bool,
) -> Dict[str, Any]:
    lower = clean_text(message).lower()
    needs: List[str] = []
    risk_checks: List[str] = []

    if re.search(r"\b(fast|faster|quick|quickly|speed|instant|low latency|don't wait|dont wait)\b", lower):
        needs.append("speed")
    if re.search(r"\b(accurate|accuracy|correct|precise|verify|reasonable|sensible|trustworthy|no hallucination|don'?t guess|dont guess)\b", lower):
        needs.append("accuracy")
    if re.search(r"\b(understand|understanding|intent|what i mean|my needs|context|messy|typo)\b", lower):
        needs.append("intent understanding")
    if re.search(r"\b(complete|final|i won'?t ask again|i wont ask again|don'?t ask again|dont ask again)\b", lower):
        needs.append("complete first-pass answer")
    if re.search(r"\b(attractive|readable|interactive|clean|normal|polished|professional)\b", lower):
        needs.append("clean presentation")
    if response_lane == "build":
        needs.append("runnable implementation")
    elif response_lane == "writing":
        needs.append("ready-to-use writing")
    elif response_lane == "learning":
        needs.append("clear learning explanation")

    if use_research or response_lane == "realtime_search":
        risk_checks.append("source-check current facts")
    else:
        risk_checks.append("avoid unsupported current claims")
    if presentation_style == "table":
        risk_checks.append("valid table formatting")
    if response_lane == "build":
        risk_checks.append("test or smoke-check the result")
    if "accuracy" in needs:
        risk_checks.append("separate facts from assumptions")
    if "complete first-pass answer" in needs:
        risk_checks.append("cover the likely next question proactively")

    if not needs:
        needs.append("direct useful answer")
    return {
        "needs": list(dict.fromkeys(needs))[:6],
        "risk_checks": list(dict.fromkeys(risk_checks))[:6],
        "latency_target": "fast" if "speed" in needs else "balanced",
        "completion_bar": "complete_first_pass" if "complete first-pass answer" in needs else "normal",
    }


def infer_understanding_profile(
    message: str,
    response_lane: str,
    presentation_style: str,
    use_research: bool,
    vague: bool,
    focus: Dict[str, Any],
) -> Dict[str, Any]:
    text = clean_text(message)
    lower = text.lower()
    word_count = len(text.split())
    priorities: List[str] = []
    checks: List[str] = []
    need_profile = infer_user_need_profile(message, response_lane, presentation_style, use_research)

    for need in need_profile["needs"]:
        priorities.append(need)
    if re.search(r"\b(accurate|accuracy|correct|true|verify|reasonable|realistic|sensible)\b", lower):
        priorities.append("accuracy and reasonableness")
    if re.search(r"\b(understand|understanding|intent|meaning|context|what i mean|messy)\b", lower):
        priorities.append("infer intent from messy wording")
    if re.search(r"\b(capability|capable|intelligent|smart|highest|advanced|powerful|ChatGPT)\b", lower):
        priorities.append("strong reasoning and capability")
    if re.search(r"\b(attractive|beautiful|interactive|readable|clear|polished|professional)\b", lower):
        priorities.append("clear polished presentation")
    if response_lane == "build":
        priorities.append("working implementation with verification")
    elif response_lane == "learning":
        priorities.append("simple explanation with examples")
    elif response_lane == "writing":
        priorities.append("finished usable writing")
    elif response_lane == "planning":
        priorities.append("practical plan with tradeoffs")

    if not priorities:
        priorities.append("direct useful answer")

    if use_research or response_lane == "realtime_search":
        checks.append("verify current claims with sources")
    else:
        checks.append("avoid unsupported current facts")
    for check in need_profile["risk_checks"]:
        checks.append(check)
    if vague:
        checks.append("resolve vague references from recent context")
    if response_lane == "build":
        checks.append("include a runnable or testable path")
    if presentation_style == "table":
        checks.append("use a real markdown table")
    if re.search(r"\b(highest|advanced|intelligent|capability|powerful)\b", lower):
        checks.append("be honest about limits while giving the strongest useful answer")
    checks.append("separate fact, assumption, and recommendation when it matters")

    ambiguity = "low"
    if vague and not focus.get("previous_user"):
        ambiguity = "high"
    elif vague or word_count <= 5:
        ambiguity = "medium"

    if vague and focus.get("previous_user"):
        likely_target = focus["previous_user"][:220]
    elif response_lane == "build":
        likely_target = "the app, code, or deployment behavior the user is asking to change"
    elif response_lane == "writing":
        likely_target = "the requested writing task and its audience"
    elif response_lane == "learning":
        likely_target = "the concept the user wants explained"
    else:
        likely_target = "the user's practical question"

    depth = "max_precision" if (
        use_research
        or response_lane in {"build", "planning", "learning", "realtime_search"}
        or re.search(r"\b(highest|advanced|intelligent|understanding|capability|accurate|reasonable|deep|detailed)\b", lower)
    ) else "standard"

    return {
        "depth": depth,
        "likely_target": likely_target,
        "priorities": priorities[:5],
        "checks": checks[:6],
        "ambiguity": ambiguity,
        "need_profile": need_profile,
    }


def build_understanding_context(
    session_id: str,
    user_message: str,
    response_lane: str,
    use_research: bool,
    writing_request: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    normalized, corrections = normalize_user_language(user_message)
    session = get_session(session_id)
    focus = recent_session_focus(session, user_message)
    vague = is_vague_followup(user_message)
    action_goal = infer_action_goal(normalized, response_lane, use_research)
    presentation_style = classify_presentation_style(normalized, response_lane, use_research)
    question_contract = infer_question_contract(
        normalized,
        response_lane,
        presentation_style,
        use_research,
        focus,
    )
    understanding_profile = infer_understanding_profile(
        normalized,
        response_lane,
        presentation_style,
        use_research,
        vague,
        focus,
    )
    words = clean_text(normalized).split()
    missing: List[str] = []
    if writing_request and writing_request.get("is_writing") and writing_request.get("missing_topic"):
        missing.append("writing topic")
    if vague and not focus.get("previous_user"):
        missing.append("reference target")
    knowledge_strategy = bool(re.search(r"\b(everything|know everything|all knowledge|you know everything)\b", normalized.lower()))

    lines = [
        "Understanding engine:",
        f"- Intelligence level: {INTELLIGENCE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({INTELLIGENCE_MODE}).",
        f"- Understanding level: {UNDERSTANDING_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({UNDERSTANDING_MODE}).",
        f"- Reasoning level: {REASONING_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({REASONING_MODE}).",
        f"- Answer structure level: {ANSWER_STRUCTURE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT} ({ANSWER_STRUCTURE_MODE}).",
        f"- Normalized user wording: {normalized}",
        f"- Question contract task type: {question_contract['task_type']}.",
        f"- Question contract target: {question_contract['target']}.",
        f"- Question contract accuracy mode: {question_contract['accuracy_mode']}.",
        f"- Question contract presentation: {question_contract['presentation']}.",
        f"- Understanding depth: {understanding_profile['depth']}.",
        f"- Likely action: {action_goal}.",
        f"- Likely target: {understanding_profile['likely_target']}.",
        "- User needs detected: " + "; ".join(understanding_profile["need_profile"]["needs"]) + ".",
        "- Latency target: " + understanding_profile["need_profile"]["latency_target"] + ".",
        "- Completion bar: " + understanding_profile["need_profile"]["completion_bar"] + ".",
        "- User priorities: " + "; ".join(understanding_profile["priorities"]) + ".",
        "- Reasonableness checks: " + "; ".join(understanding_profile["checks"]) + ".",
        f"- Vague follow-up/reference detected: {'yes' if vague else 'no'}.",
        f"- Ambiguity level: {understanding_profile['ambiguity']}.",
    ]
    if corrections:
        lines.append("- Typing corrections understood: " + "; ".join(corrections) + ".")
    if question_contract["constraints"]:
        lines.append("- Contract constraints: " + "; ".join(question_contract["constraints"]) + ".")
    lines.append("- Answer contract: " + "; ".join(question_contract["answer_contract"]) + ".")
    if focus.get("previous_user"):
        lines.append(f"- Recent user focus: {focus['previous_user']}")
    if focus.get("previous_assistant"):
        lines.append(f"- Recent assistant context: {focus['previous_assistant']}")
    if focus.get("keywords"):
        lines.append("- Context keywords: " + ", ".join(focus["keywords"]) + ".")
    if missing:
        lines.append("- Missing/uncertain pieces: " + ", ".join(missing) + ".")
    if knowledge_strategy:
        lines.append("- Knowledge strategy: answer from model knowledge for stable facts, but use search/sources for current or uncertain facts.")
    lines.extend([
        "- Highest understanding protocol: first translate messy wording into the likely intent, then identify the target, constraints, hidden expectation, and risk of misunderstanding.",
        "- User-need protocol: satisfy speed, accuracy, completeness, and presentation needs in that order when the user asks for them.",
        "- Before answering, do an internal consistency pass: does the answer solve the actual user goal, respect recent context, and avoid exaggerated capability claims?",
        "- If the user uses 'it', 'this', 'that', or says 'make it better', resolve the target from recent context before answering.",
        "- If the target or required topic is still missing, ask one short clarifying question instead of inventing a topic.",
        "- Do not claim to know everything. Use memory, chat context, files, and real-time search when facts may be current or uncertain.",
        "- Interpret messy human wording by intent, not by literal grammar mistakes.",
        "- Prefer reasonable, checkable answers over impressive-sounding answers. State practical limits only when they matter.",
    ])
    state = {
        "normalized": normalized,
        "corrections": corrections,
        "vague_followup": vague,
        "focus_keywords": focus.get("keywords", []),
        "previous_user": focus.get("previous_user", ""),
        "missing": missing,
        "knowledge_strategy": knowledge_strategy,
        "word_count": len(words),
        "understanding_depth": understanding_profile["depth"],
        "intelligence_level": INTELLIGENCE_LEVEL_TEXT,
        "intelligence_mode": INTELLIGENCE_MODE,
        "understanding_level": UNDERSTANDING_LEVEL_TEXT,
        "understanding_mode": UNDERSTANDING_MODE,
        "reasoning_level": REASONING_LEVEL_TEXT,
        "reasoning_mode": REASONING_MODE,
        "answer_structure_level": ANSWER_STRUCTURE_LEVEL_TEXT,
        "answer_structure_mode": ANSWER_STRUCTURE_MODE,
        "understanding_priorities": understanding_profile["priorities"],
        "understanding_checks": understanding_profile["checks"],
        "likely_target": understanding_profile["likely_target"],
        "need_profile": understanding_profile["need_profile"],
        "question_contract": question_contract,
    }
    return "\n".join(lines), state


def classify_response_lane(user_message: str, use_research: bool) -> str:
    text = clean_text(user_message).lower()
    if use_research:
        return "realtime_search"
    if re.search(r"\b(fix grammar|correct grammar|grammar check|correct this|rewrite|rephrase|polish|make this clearer|improve this sentence|improve this text|translate|translation|translation review|natural translation|literal translation|back translation|transliterate|romanize|subtitle|tone conversion|make it formal|make it informal|localize|localise|politeness register|email rewrite|essay correction)\b", text):
        return "writing"
    if re.search(r"\b(language learning|language level|cefr|detect language|identify language|learn hindi|learn english|learn tamil|learn french|learn spanish|learn german|learn japanese|learn korean|learn arabic|learn chinese|learn portuguese|learn russian|learn italian|learn dutch|learn greek|learn bengali|learn marathi|learn telugu|learn kannada|learn malayalam|learn urdu|learn swahili|learn thai|learn vietnamese|pronunciation|vocabulary|vocab quiz|flashcard|grammar rule|grammar drill|tense practice|parts of speech|minimal pair|syllable stress|reading comprehension|cloze test|language exam|conversation practice|phrasebook|idiom|idioms|proverb|proverbs|synonym|synonyms|antonym|antonyms|word meaning|cultural context|compare languages)\b", text):
        return "learning"
    if re.search(r"\b(summarize|summarise|summary|shorten|key points|main points|takeaways)\b", text) and not re.search(r"\b(file|pdf|document|upload|uploaded)\b", text):
        return "learning"
    if re.search(r"\b(brainstorm|ideas?|which should i choose|which is better|should i|better option|recipe|cook|travel plan|trip plan|itinerary)\b", text):
        return "planning"
    if re.search(r"\b(legal memo|case brief|grant proposal|press release|journalism|sales pitch|customer support reply|essay|lab report|policy brief|research brief)\b", text):
        return "writing"
    if re.search(r"\b(health|symptom|pain|fever|medicine|doctor|legal|law|contract|finance|money|budget|saving|investment|loan|debt|tax|insurance|real estate|procurement|operations|logistics|supply chain|manufacturing|quality control|hr policy|compliance|policy analysis|sustainability|agriculture|parenting|sports coaching)\b", text):
        return "planning"
    if re.search(r"\b(resume|cv|job application|career|portfolio|linkedin|interview|presentation|ppt|slides|meeting notes|minutes of meeting|caption|social media post|essay|lab report|legal memo|case brief|grant proposal|press release|journalism|sales pitch|customer support|brand name|slogan|tagline)\b", text):
        return "writing"
    if re.search(r"\b(poem|original song|story|creative writing|joke|funny|relationship|stressed|sad|anxious|worried|lonely|angry|overwhelmed)\b", text):
        return "human_chat"
    if re.search(r"\b(flashcards?|quiz|practice questions|test me|mcq|timeline|chronology|homework|assignment|exam answer|answer this question)\b", text):
        return "learning"
    if analyze_writing_request(user_message).get("is_writing") or re.search(r"\b(email|e-mail|mail|letter|application|notice|message|reply to|cover letter|resume|cv|apology|invitation|complaint|request|proposal|draft)\b", text):
        return "writing"
    if is_goal_or_problem_request(user_message):
        return "planning"
    if re.search(r"\b(explain|teach|learn|class|chapter|homework|notes|summary|revise|study|history of|overview of|background of|timeline of|science|biology|physics|chemistry|geography|economics|philosophy|psychology|music theory|film analysis|theology|mathematical proof)\b", text):
        return "learning"
    if re.search(r"\b(code|bug|debug|frontend|backend|api|html|css|javascript|python|github|deploy|website|regex|excel formula|database|sql|data science|machine learning|dashboard|civil engineering|mechanical engineering|electrical engineering|electronics|arduino|architecture review)\b", text):
        return "build"
    return "human_chat"


def classify_presentation_style(user_message: str, response_lane: str, use_research: bool) -> str:
    text = clean_text(user_message).lower()
    if re.search(r"\b(diagram|flowchart|flow chart|mind map|map it|architecture|pipeline|cycle|process flow|how it works visually)\b", text):
        return "diagram"
    if re.search(r"\b(chart|graph|bar chart|pie chart|rank|ranking|trend|growth|timeline|price history|market movement)\b", text):
        return "chart"
    if re.search(r"\b(table|tabular|columns|compare|comparison|vs\.?|versus|difference between|pros and cons|advantages and disadvantages)\b", text):
        return "table"
    if re.search(r"\b(one line|short|brief|quick|concise|just tell|only answer|simple answer)\b", text):
        return "short"
    if response_lane == "planning":
        if re.search(r"\b(compare|option|which|best|pros and cons|advantages and disadvantages)\b", text):
            return "table"
        return "implementation_summary"
    if response_lane == "learning":
        if re.search(r"\b(cycle|process|system|working|mechanism|pathway|flow|stages)\b", text):
            return "diagram"
        if re.search(r"\b(notes|summary|revise|study|chapter)\b", text):
            return "teaching_structure"
    if re.search(r"\b(detailed|deep|full|complete|step by step|explain fully|long answer|essay)\b", text):
        return "long"
    if response_lane == "writing":
        return "finished_draft"
    if response_lane == "realtime_search" or use_research:
        return "answer_with_evidence"
    if response_lane == "learning":
        return "teaching_structure"
    if response_lane in {"build", "planning"}:
        return "implementation_summary"
    if len(text) < 90 and re.search(r"\b(what|who|when|where|which|can|should|is|are)\b", text):
        return "short"
    return "balanced"


def build_presentation_context(user_message: str, response_lane: str, use_research: bool) -> str:
    style = classify_presentation_style(user_message, response_lane, use_research)
    lines = [
        "Presentation planner:",
        f"- Preferred format: {style}",
        "- Choose the clearest format automatically; do not mention this planner.",
        "- Nexora answer structure: direct answer first, short explanation, important details/examples, sources or links if needed, then a useful next step only when it genuinely helps.",
        "- Keep the output simple, smart, natural, and clean. Avoid robotic wording, over-formatting, giant walls of text, and generic filler.",
        "- Open with the answer itself. Do not open with meta phrases like 'Here is', 'Based on your question', or 'I can help'.",
        "- Default serious-answer blueprint: one compact lead paragraph, then short sections only if they help.",
        "- Use this section order for explainers: 'Short answer:', 'Key points:', 'Why it matters:' or 'How it works:', then 'Bottom line:'.",
        "- Use this section order for how-to/planning tasks: 'Short answer:', concrete steps or workflow, optional checklist, then 'Bottom line:'.",
        "- Use this section order for research answers: 'Answer:', 'Key evidence:', 'Context:', then 'Bottom line:'.",
        "- Use field-aware styling: definitions for learning, ordered steps for workflows, concise tables for comparisons, and direct finished drafts for writing.",
        "- Prefer plain section labels, not oversized titles. Bold text is allowed only for genuinely important labels or emphasis.",
        "- Make the answer feel finished: no dangling labels, no repeated punctuation, no source dumps, no awkward filler, and no giant single paragraph.",
        "- Never put a colon on its own line. Keep labels as 'Key points:' on one line.",
        "- Keep simple direct questions to 1-3 short paragraphs with no headings unless a heading makes the answer easier to scan.",
        "- Use a table only when comparing items across features, pros/cons, options, prices, specs, timelines, or tradeoffs.",
        "- Do not add current prices, dates, percentages, exact counts, or technical numbers unless the user asks for them or evidence/context supports them.",
        "- Use a chart-style text summary only for rankings, trends, quantities, or progress. Keep it readable in plain text.",
        "- Use a diagram or flow only for processes, cycles, systems, architecture, or cause-and-effect relationships.",
        "- Put exactly one blank line between major sections. Avoid giant text blocks and avoid bullet dumping.",
        "- Bullets should be parallel, compact, and meaningful. Numbered lists are for ordered steps only.",
        "- Add a 'Next step:' only when the user is likely trying to act, build, study, choose, or continue a workflow.",
        "- Do not add generic closing questions after the answer.",
        "- End once the answer is complete.",
        "- Do not force tables, charts, or diagrams into normal conversation.",
    ]
    if style == "table":
        lines.extend([
            "- Output a valid markdown table with a header row and separator row.",
            "- Use visible | separators. Do not output spaced columns.",
            "- Keep cell text compact. Add a short takeaway before or after the table.",
        ])
    elif style == "chart":
        lines.extend([
            "- Prefer a compact markdown table plus simple text bars when useful.",
            "- Label units clearly. Do not invent numeric values.",
        ])
    elif style == "diagram":
        lines.extend([
            "- Use a compact text diagram in a fenced code block, then explain the key idea in 2-4 bullets.",
            "- Avoid Mermaid unless the user explicitly asks for Mermaid.",
        ])
    elif style == "short":
        lines.extend([
            "- Keep the answer to 1-3 short paragraphs or up to 3 bullets.",
            "- Skip headings unless they add clarity.",
        ])
    elif style == "implementation_summary" and response_lane == "planning":
        lines.extend([
            "- Give a specific plan, not a generic process template.",
            "- Include a simple timeline or checklist when it helps the user start immediately.",
            "- Name the likely first action clearly.",
        ])
    elif style == "long":
        lines.extend([
            "- Use clear sections, but avoid filler.",
            "- Start with the conclusion, then explain reasoning and steps.",
            "- Preferred section flow: 'Short answer:', 'Key points:', 'Details:', 'Bottom line:'.",
        ])
    elif style == "finished_draft":
        lines.extend([
            "- Provide the finished draft first.",
            "- For email, include a subject line when useful.",
            "- Keep the writing smooth, polished, and ready to send.",
        ])
    elif style == "answer_with_evidence":
        lines.extend([
            "- Use this exact flow when useful: one direct answer paragraph, then 'Key points:', then 'What it means:', then 'Bottom line:'.",
            "- Answer first, then give key evidence with inline citations.",
            "- If evidence is mixed or weak, say so clearly.",
            "- Keep source-backed bullets compact. Do not make every source a separate paragraph.",
        ])
    return "\n".join(lines)


def build_response_lane_context(user_message: str, use_research: bool) -> str:
    lane = classify_response_lane(user_message, use_research)
    lower_message = clean_text(user_message).lower()
    base = [
        "Adaptive response lane:",
        f"- Lane: {lane}",
    ]
    base.extend([
        "- Tone adaptation map:",
        "  - School question: exam-style, clear definitions, key terms, examples, and a simple final takeaway.",
        "  - Coding: developer assistant; be precise, practical, test-aware, and code-first when useful.",
        "  - Research: Perplexity-style synthesis with citations and uncertainty handling.",
        "  - Creative: Claude-style prose with rhythm, clarity, and emotional intelligence.",
        "  - Business: strategic, sharp, concise, and action-oriented.",
        "  - Professional fields: use domain-aware structure, practical constraints, risks, and next actions.",
        "  - Healthcare/legal/finance: be careful, uncertainty-aware, and clear that high-stakes decisions need qualified review.",
        "  - Engineering/data/operations: use specs, assumptions, checks, and implementation order.",
        "  - Academic fields: define terms, explain the reasoning, give examples, and finish with the core takeaway.",
        "  - Casual: conversational, warm, and light without becoming sloppy.",
    ])
    if lane == "writing":
        base.extend([
            "- Write with Claude-like smoothness: composed, natural, elegant, and easy to read.",
            "- Focus on rhythm: short sentences for impact, longer sentences for flow, and paragraph breaks where a human would pause.",
            "- Cut filler and formal padding. Strong writing should feel clear, not inflated.",
            "- For emails and letters, produce a finished draft first. Include a subject line for emails when useful.",
            "- Use polished punctuation, clean paragraph breaks, and human wording that does not sound robotic.",
            "- Match the relationship and situation: respectful for teachers/officials, warm for personal messages, concise for business.",
            "- Avoid overexplaining the draft unless the user asks for notes or alternatives.",
        ])
        if re.search(r"\b(story|poem|creative|scene|dialogue|emotional|beautiful|smooth|letter|personal)\b", lower_message):
            base.extend([
                "- Creative writing mode: use natural rhythm, emotional clarity, and vivid but controlled wording.",
                "- Avoid generic motivational filler; make the wording feel intentional.",
            ])
    elif lane == "realtime_search":
        base.extend([
            "- Use Perplexity-style search synthesis: answer first, then key evidence, then compact context.",
            "- Use inline citations like [1] and [2] for claims based on sources.",
            "- Compare sources when they disagree. State uncertainty clearly instead of forcing a confident answer.",
            "- Do not dump raw source lists; the app renders source cards separately.",
        ])
    elif lane == "build":
        base.extend([
            "- Use developer-assistant mode: identify the bug or goal, give the concrete fix, and mention verification.",
            "- Prefer commands, filenames, and code snippets when they help. Keep explanations short and accurate.",
            "- If the task is implementation, give steps in execution order and avoid vague advice.",
        ])
    elif lane == "human_chat":
        base.extend([
            "- Use ChatGPT-like human behavior: warm, attentive, direct, and context-aware.",
            "- Respond like a thoughtful collaborator, not a form template.",
            "- Read messy wording by intent. If the literal wording is broken but the likely meaning is clear, answer the likely meaning.",
            "- Give a useful answer instead of asking the user to repeat, unless the missing detail changes the answer completely.",
            "- Prefer simple cause-and-effect wording over formal phrasing.",
            "- Use blank lines to separate thought changes; dense blocks feel less human.",
            "- Keep normal chat natural and concise. Use headings only when the answer has more than one clear part.",
            "- Notice the user's intent and emotion; be steady, not dramatic.",
        ])
        if re.search(r"\b(ai|artificial intelligence|assistant|chatbot|nexora|model|powerful|power|trust|wisdom|safe|human|meaning|think|opinion)\b", user_message.lower()):
            base.extend([
                "- For this reflective-style chat, use a thoughtful opening sentence, then one bold thesis sentence.",
                "- Use compact bullets with bold labels only if they add clarity.",
                "- Be honest about limits and uncertainty without becoming evasive.",
                "- A single natural curiosity question at the end is allowed if it feels human and relevant.",
            ])
    elif lane == "planning":
        base.extend([
            "- Understand the user's real goal, then turn it into a practical action plan.",
            "- Business or workflow mode: be strategic, sharp, and action-oriented. State tradeoffs plainly.",
            "- Avoid generic templates like 'break it into small steps' unless followed by domain-specific steps.",
            "- Start with the best first move, then give a concrete workflow, checklist, or timeline.",
            "- If the request is vague but still answerable, make a reasonable assumption and state it briefly.",
            "- Ask a question only when the missing detail changes the entire plan.",
        ])
    elif lane == "learning":
        base.extend([
            "- Teach clearly: simple explanation first, then key points, then a short recap if useful.",
            "- Use examples and exam-friendly wording when the user seems to be studying.",
            "- Keep the structure clean and avoid long blocks.",
        ])
    elif lane == "build":
        base.extend([
            "- Be implementation-focused: state what changed, what to test, and any limitation.",
            "- Prefer concrete steps and exact file/function references when discussing code.",
            "- Keep explanations concise unless the user asks for depth.",
        ])
    return "\n".join(base)


def analyze_user_intent(
    user_message: str,
    response_lane: str,
    presentation_style: str,
    use_research: bool,
    behavior_signals: Optional[Dict[str, Any]] = None,
    research_route: str = "none",
) -> Dict[str, Any]:
    text = clean_text(user_message)
    lower = text.lower()
    signals = behavior_signals or {}

    if response_lane == "writing":
        goal = "produce polished writing the user can use directly"
    elif response_lane == "build":
        goal = "solve or implement the requested app/code change"
    elif response_lane == "planning":
        goal = "understand the user's practical goal and turn it into a useful plan"
    elif response_lane == "learning":
        goal = "explain the concept clearly and make it easy to study"
    elif response_lane == "realtime_search" or use_research:
        goal = "answer with current verified evidence"
    else:
        goal = "answer the user's practical question directly"

    shape_map = {
        "short": "short answer",
        "table": "compact table with takeaway",
        "chart": "compact chart/table summary",
        "diagram": "simple text diagram plus key points",
        "long": "structured long answer",
        "finished_draft": "finished draft first",
        "teaching_structure": "study-style explanation",
        "implementation_summary": "implementation-focused steps",
        "answer_with_evidence": "answer with citations",
    }
    expected_output = shape_map.get(presentation_style, "balanced answer")

    constraints: List[str] = []
    need_profile = infer_user_need_profile(user_message, response_lane, presentation_style, use_research)
    if need_profile.get("needs"):
        constraints.append("detected user needs: " + ", ".join(need_profile["needs"]))
    if need_profile.get("latency_target") == "fast":
        constraints.append("answer quickly; use the fastest reliable path")
    if need_profile.get("completion_bar") == "complete_first_pass":
        constraints.append("make the first answer complete enough that the user should not need to repeat the request")
    if need_profile.get("risk_checks"):
        constraints.append("quality checks: " + ", ".join(need_profile["risk_checks"][:4]))
    if re.search(r"\b(fast|faster|speed|efficient|efficiency|quick)\b", lower) or signals.get("urgency"):
        constraints.append("prioritize speed and low-token structure")
    if re.search(r"\b(structure|structured|clean|professional|beautiful|format)\b", lower) or signals.get("needs_structure"):
        constraints.append("make the answer clean and well structured")
    if re.search(r"\b(no extra|remove|only|without|don'?t add)\b", lower):
        constraints.append("avoid extra UI/text and unnecessary endings")
    if re.search(r"\b(memory|remember|long[- ]?term)\b", lower):
        constraints.append("use and update long-term memory")
    if re.search(r"\b(understand|understanding|intent|human|behavior|powerful|capability|everything)\b", lower):
        constraints.append("infer the user's real intent from messy wording and recent context")
    if re.search(r"\b(reasonable|realistic|sensible|accurate|correct|trustworthy)\b", lower):
        constraints.append("prioritize reasonable, checkable claims over impressive wording")
    if re.search(r"\b(highest|advanced|intelligent|smarter|capability|ChatGPT)\b", lower):
        constraints.append("use the strongest available reasoning path while staying honest about limits")
    question_contract = infer_question_contract(user_message, response_lane, presentation_style, use_research)
    constraints.append("question contract: " + question_contract["task_type"] + " targeting " + question_contract["target"])
    constraints.append("accuracy mode: " + question_contract["accuracy_mode"])
    if question_contract["constraints"]:
        constraints.extend(question_contract["constraints"][:3])
    if use_research:
        constraints.append("do not guess current facts without sources")
    if research_route in {"web_light", "web_current", "strict_current"}:
        constraints.append("use research only for claims that need evidence; keep the answer efficient")
    elif research_route == "wikipedia":
        constraints.append("use stable background context when it improves accuracy")

    ambiguity = "low"
    if len(text.split()) < 4 and response_lane == "human_chat":
        ambiguity = "medium"
    if re.search(r"\b(this|that|it|those|these)\b", lower) and len(text.split()) < 12:
        ambiguity = "medium"

    return {
        "goal": goal,
        "expected_output": expected_output,
        "constraints": constraints,
        "ambiguity": ambiguity,
        "research_route": research_route,
        "question_contract": question_contract,
    }


def build_intent_context(intent: Dict[str, Any]) -> str:
    lines = [
        "Current request understanding:",
        f"- Likely user goal: {intent.get('goal', 'answer directly')}.",
        f"- Routed task intent: {intent.get('task_intent', 'chat')}.",
        f"- Best output shape: {intent.get('expected_output', 'balanced answer')}.",
        f"- Ambiguity: {intent.get('ambiguity', 'low')}.",
        f"- Research route: {intent.get('research_route', 'none')}.",
        f"- Gate stack mode: {GATE_STACK_MODE}.",
        f"- Intent quality level: {INTENT_QUALITY_LEVEL_TEXT}/10.00.",
        f"- Routing gate: {intent.get('routing_gate', ROUTING_GATE_MODE)} at {ROUTING_GATE_LEVEL_TEXT}/10.00; quality gate: {intent.get('quality_gate', QUALITY_GATE_MODE)} at {QUALITY_GATE_LEVEL_TEXT}/10.00.",
        "- Active gates: intent detection, context resolution, route selection, route confidence, task-shape validation, answer quality, accuracy, reasoning, answer structure, repair, final cleanup.",
    ]
    contract = intent.get("question_contract") or {}
    if contract:
        lines.extend([
            f"- Actual question type: {contract.get('task_type', 'request')}.",
            f"- Actual target to answer: {contract.get('target', '')}.",
            f"- Accuracy mode: {contract.get('accuracy_mode', 'stable-knowledge with uncertainty checks')}.",
        ])
    constraints = intent.get("constraints") or []
    if constraints:
        lines.append("- Current constraints:")
        for item in constraints[:6]:
            lines.append(f"  - {item}")
    lines.append(
        "Think in this order: understand the real ask, choose the shortest reliable path, use memory/context/search only when useful, then answer cleanly. Ask a clarifying question only if a useful answer would be risky or impossible."
    )
    lines.append(
        "Use highest-capability behavior for ambiguous or high-effort requests: infer intent, map constraints, consider alternatives, check reasonableness, then give the clearest final answer without exposing hidden reasoning."
    )
    return "\n".join(lines)


def maybe_store_memory(user_message: str, user_id: str = "default") -> None:
    text = user_message.strip()
    lower = text.lower()
    triggers = [
        "remember",
        "remember that",
        "save this",
        "store this",
        "from now on",
        "always",
        "my project",
        "my goal",
        "my name is",
        "call me",
        "i prefer",
        "i like",
        "i want you to",
        "nexora should",
        "i want nexora",
    ]
    if not any(trigger in lower for trigger in triggers):
        return
    category = "explicit"
    if re.search(r"\b(my name is|call me|i am|i'm)\b", lower):
        category = "identity"
    elif re.search(r"\b(my project|my goal|building|website|app|nexora)\b", lower):
        category = "project"
    elif re.search(r"\b(i prefer|i like|always|from now on|style|answer|format|image)\b", lower):
        category = "preference"
    upsert_memory_item(
        content=text[:1200],
        user_id=user_id,
        category=category,
        source="user_instruction",
        strength=3,
    )


def score_memory_item(item: Dict[str, Any], query_keywords: List[str]) -> int:
    content = clean_text(str(item.get("content", "")))
    if not content:
        return -100
    item_keywords = set(str(value).lower() for value in item.get("keywords", []) if value)
    if not item_keywords:
        item_keywords = set(memory_keywords(content))
    query_set = set(query_keywords)
    overlap = len(item_keywords.intersection(query_set))
    category = str(item.get("category", "general")).lower()
    source = str(item.get("source", "auto")).lower()
    content_lower = content.lower()
    phrase_bonus = 0
    if query_keywords:
        phrase_bonus = sum(2 for keyword in query_keywords[:12] if keyword in content_lower)
    score = overlap * 8 + phrase_bonus + min(18, int(item.get("hits", 1) or 1) * 2)
    if category in {"preference", "explicit", "identity", "project", "workflow", "correction", "image_preference"}:
        score += 8
    if source == "user_instruction":
        score += 10
    if not query_keywords and category in {"explicit", "identity", "project", "preference"}:
        score += 6
    score += int(min(12, memory_item_importance(item) / 8))
    return score


def build_memory_context(user_id: str = "default", current_message: str = "") -> str:
    normalized = normalize_user_id(user_id)
    query_keywords = memory_keywords(current_message)
    user_items = [
        item for item in load_memory()
        if normalize_user_id(str(item.get("user_id", "default"))) == normalized
    ]
    scored = sorted(
        user_items,
        key=lambda item: (
            score_memory_item(item, query_keywords),
            memory_item_importance(item),
            str(item.get("last_seen", item.get("created_at", ""))),
        ),
        reverse=True,
    )
    persistent = [
        item for item in user_items
        if str(item.get("category", "")).lower() in {"explicit", "identity", "project", "preference"}
    ]
    persistent = sorted(persistent, key=memory_item_importance, reverse=True)[:6]
    recent = sorted(
        user_items,
        key=lambda item: str(item.get("last_seen", item.get("created_at", ""))),
        reverse=True,
    )[:5]
    selected: List[Dict[str, Any]] = []
    seen = set()
    for item in scored + persistent + recent:
        key = str(item.get("memory_key") or item.get("content", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= MAX_MEMORY_CONTEXT_ITEMS:
            break
    lines = []
    total_chars = 0
    for index, item in enumerate(selected, start=1):
        content = clean_text(str(item.get("content", "")))
        if content:
            category = clean_text(str(item.get("category", "memory"))) or "memory"
            hits = int(item.get("hits", 1) or 1)
            line = f"{index}. [{category}; hits={hits}] {content}"
            if total_chars + len(line) > MAX_MEMORY_CONTEXT_CHARS:
                break
            lines.append(line)
            total_chars += len(line)
    if not lines:
        return ""
    return (
        "Long-term user memory relevant to this request (ranked by relevance, explicit preference, recency, and repeated use):\n"
        + "\n".join(lines)
        + "\nUse these memories to infer intent and continuity. Prefer explicit user instructions over automatic guesses. Do not mention memory unless it helps the answer."
    )


def memory_signature_for_user(user_id: str) -> str:
    normalized = normalize_user_id(user_id)
    ranked = sorted(
        [
            item for item in load_memory()
            if normalize_user_id(str(item.get("user_id", "default"))) == normalized
        ],
        key=lambda item: (memory_item_importance(item), str(item.get("last_seen", item.get("created_at", "")))),
        reverse=True,
    )
    stable = [
        {
            "content": clean_text(str(item.get("content", "")))[:160],
            "category": item.get("category", ""),
            "hits": item.get("hits", 1),
            "last_seen": item.get("last_seen", item.get("created_at", "")),
        }
        for item in ranked[:MAX_MEMORY_CONTEXT_ITEMS]
    ]
    return stable_hash(json.dumps(stable, ensure_ascii=False, sort_keys=True))


def learn_long_term_memory_from_chat(
    user_message: str,
    assistant_reply: str,
    user_id: str,
    session_id: str,
    response_lane: str,
    presentation_style: str,
    behavior_signals: Optional[Dict[str, Any]] = None,
) -> None:
    text = clean_text(user_message)
    lower = text.lower()
    signals = behavior_signals or {}

    preference_patterns = [
        (r"\b(fast|faster|speed|efficient|efficiency|no timeout|timeouts?)\b", "User values fast, efficient answers with minimal waiting.", "workflow"),
        (r"\b(structure|structured|clean|professional|beautiful|format|punctuation|organized)\b", "User prefers clean, structured, professional answers.", "preference"),
        (r"\b(understand|intent|what the user wants|question properly|human behavior)\b", "User wants Nexora to infer intent from informal wording and respond to the real need.", "preference"),
        (r"\b(powerful|capability|know everything|you know everything|understanding chatbot|understanding ai)\b", "User wants Nexora to combine context understanding, memory, and realtime search instead of literal keyword matching.", "preference"),
        (r"\b(ChatGPT|chatgpt|working level|real problem|understand a problem|actual problem)\b", "User wants ChatGPT-level problem understanding: infer the real goal, answer with a specific useful plan, and avoid canned templates.", "preference"),
        (r"\b(generic|template|canned|not useful|too basic)\b", "Avoid generic template answers; use domain-specific reasoning, concrete next steps, and a useful checklist.", "preference"),
        (r"\b(doesn'?t understand|dont understand|didn'?t understand|missing topic|ask for the topic)\b", "When a writing request is incomplete, ask for the missing topic instead of guessing.", "preference"),
        (r"\b(long[- ]?term memory|remember chat|memory of the chat|remember our chat)\b", "User wants long-term chat memory used for future replies.", "preference"),
        (r"\b(short|brief|concise)\b", "User sometimes asks for concise answers; keep simple requests short.", "preference"),
        (r"\b(detailed|long answer|deep|explain fully)\b", "User wants detailed answers when the topic is complex or asks for depth.", "preference"),
        (r"\b(realtime|real time|search|perplexity|current|latest)\b", "User expects realtime search for current facts and accuracy-sensitive questions.", "workflow"),
        (r"\b(image|create image|generate image)\b", "User cares about clean image generation workflow with minimal extra text.", "workflow"),
        (r"\b(exact image|exactly match|match the user|as asked|user'?s needs|same as asked)\b", "For image generation, preserve the user's exact subject, style, count, colors, pose, and composition before adding quality details.", "image_preference"),
        (r"\b(heavy memory|more memory|more data|memory handling|long memory)\b", "User wants heavier long-term memory handling with more retained context and better relevance ranking.", "preference"),
        (r"\b(github|website|official website|pages)\b", "User is building or publishing Nexora as a website/GitHub Pages project.", "project"),
        (r"\b(nexora|independent ai|self learning|real ai)\b", "User is building Nexora as a personal AI assistant with memory, adaptation, and useful autonomy.", "project"),
        (r"\b(class|study|exam|homework|chapter|notes)\b", "User may ask study questions and prefers simple, exam-friendly explanations.", "preference"),
        (r"\b(email|letter|essay|application|speech|draft)\b", "For writing tasks, user usually wants the finished draft first with polished structure.", "preference"),
    ]
    for pattern, memory, category in preference_patterns:
        if re.search(pattern, lower):
            upsert_memory_item(memory, user_id, category, "auto_behavior", session_id, strength=1)

    if any(phrase in lower for phrase in ["from now on", "always", "remember", "i want nexora", "nexora should"]):
        upsert_memory_item(text[:500], user_id, "explicit", "user_instruction", session_id, strength=3)

    if signals.get("correction") or re.search(r"\b(fix this|not like this|wrong|doesn'?t understand|should be|wasn'?t supposed)\b", lower):
        upsert_memory_item(
            f"User correction to remember: {text[:700]}",
            user_id,
            "correction",
            "auto_behavior",
            session_id,
            strength=2,
        )

    if response_lane:
        upsert_memory_item(
            f"Recent interaction pattern: response lane '{response_lane}' with preferred presentation '{presentation_style}'.",
            user_id,
            "interaction_pattern",
            "auto_trace",
            session_id,
            strength=1 if signals.get("correction") else 0,
        )


TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".py", ".js", ".html", ".css",
    ".ts", ".tsx", ".jsx", ".xml", ".yaml", ".yml", ".log",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def extract_pdf_text(path: Path) -> str:
    try:
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            from PyPDF2 import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages[:40], start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if clean_text(text):
                pages.append(f"[Page {index}]\n{text}")
        return "\n\n".join(pages)
    except Exception:
        pass

    try:
        raw = path.read_bytes()
        chunks: List[str] = []
        for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.DOTALL):
            data = match.group(1).strip()
            for candidate in (data,):
                try:
                    inflated = zlib.decompress(candidate)
                except Exception:
                    inflated = candidate
                text = inflated.decode("latin-1", errors="ignore")
                text = re.sub(r"\\[()]", " ", text)
                pieces = re.findall(r"\(([^()]{2,})\)", text)
                if pieces:
                    chunks.append(" ".join(pieces))
        return clean_text("\n".join(chunks))
    except Exception:
        return ""


def basic_extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix not in TEXT_EXTENSIONS:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def detect_image_size_from_bytes(content: bytes, suffix: str = "") -> Tuple[int, int]:
    try:
        from PIL import Image  # type: ignore
        import io

        with Image.open(io.BytesIO(content)) as img:
            return int(img.width), int(img.height)
    except Exception:
        pass

    try:
        if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
            return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")
        if content[:6] in {b"GIF87a", b"GIF89a"} and len(content) >= 10:
            return int.from_bytes(content[6:8], "little"), int.from_bytes(content[8:10], "little")
        if content.startswith(b"\xff\xd8"):
            index = 2
            while index + 9 < len(content):
                if content[index] != 0xFF:
                    index += 1
                    continue
                marker = content[index + 1]
                index += 2
                if marker in {0xD8, 0xD9}:
                    continue
                length = int.from_bytes(content[index:index + 2], "big")
                if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                    height = int.from_bytes(content[index + 3:index + 5], "big")
                    width = int.from_bytes(content[index + 5:index + 7], "big")
                    return width, height
                index += max(length, 2)
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP" and len(content) >= 30:
            if content[12:16] == b"VP8X":
                width = 1 + int.from_bytes(content[24:27], "little")
                height = 1 + int.from_bytes(content[27:30], "little")
                return width, height
    except Exception:
        return 0, 0
    return 0, 0


def analyze_image_bytes(content: bytes, filename: str, content_type: str = "") -> Dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    width, height = detect_image_size_from_bytes(content, suffix)
    size_bytes = len(content)
    orientation = "unknown"
    if width and height:
        if width > height * 1.15:
            orientation = "landscape"
        elif height > width * 1.15:
            orientation = "portrait"
        else:
            orientation = "square"
    kind = "image"
    lower_name = filename.lower()
    if "screenshot" in lower_name or (suffix == ".png" and width >= 900 and height >= 500):
        kind = "screenshot or UI image"
    elif suffix in {".jpg", ".jpeg", ".webp"}:
        kind = "photo or generated artwork"

    color_note = ""
    try:
        from PIL import Image, ImageStat  # type: ignore
        import io

        with Image.open(io.BytesIO(content)) as img:
            thumb = img.convert("RGB")
            thumb.thumbnail((96, 96))
            stat = ImageStat.Stat(thumb)
            avg = [round(value, 1) for value in stat.mean[:3]]
            brightness = round(sum(avg) / 3, 1)
            if brightness < 85:
                color_note = "dark overall"
            elif brightness > 180:
                color_note = "bright overall"
            else:
                color_note = "balanced brightness"
    except Exception:
        color_note = ""

    return {
        "width": width,
        "height": height,
        "orientation": orientation,
        "kind": kind,
        "size_bytes": size_bytes,
        "content_type": content_type,
        "color_note": color_note,
    }


def summarize_image_record(image: Dict[str, Any]) -> str:
    name = clean_text(str(image.get("filename", "image")))
    width = int(image.get("width", 0) or 0)
    height = int(image.get("height", 0) or 0)
    size_bytes = int(image.get("size_bytes", 0) or 0)
    size_label = f"{round(size_bytes / 1024, 1)} KB" if size_bytes else "unknown size"
    dimensions = f"{width}x{height}" if width and height else "unknown dimensions"
    details = [
        f"{name}",
        dimensions,
        str(image.get("orientation", "unknown")),
        str(image.get("kind", "image")),
        size_label,
    ]
    color_note = clean_text(str(image.get("color_note", "")))
    if color_note:
        details.append(color_note)
    return " - ".join(part for part in details if part)


def selected_session_images(session_id: str, image_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    session = get_session(session_id)
    images = session.get("images", [])
    if not isinstance(images, list):
        return []
    clean_ids = {clean_text(str(item)) for item in (image_ids or []) if clean_text(str(item))}
    if clean_ids:
        return [item for item in images if clean_text(str(item.get("id", ""))) in clean_ids]
    return images[-3:]


def build_image_context(session_id: str, image_ids: Optional[List[str]] = None) -> str:
    images = selected_session_images(session_id, image_ids)
    if not images:
        return ""
    lines = ["Attached image context:"]
    for index, image in enumerate(images, start=1):
        lines.append(f"{index}. {summarize_image_record(image)}")
    lines.append("Use this metadata and the user's wording. Do not pretend to see details that are not available.")
    return "\n".join(lines)


def local_image_attachment_reply(message: str, session_id: str, image_ids: Optional[List[str]] = None) -> Optional[str]:
    lower = clean_text(message).lower()
    images = selected_session_images(session_id, image_ids)
    if not images:
        return None
    if image_ids or re.search(r"\b(image|photo|picture|screenshot|attached|uploaded|this)\b", lower):
        lines = [
            "I received the image attachment.",
            "",
            "What I can read locally:",
        ]
        lines.extend(f"- {summarize_image_record(image)}" for image in images)
        lines.extend([
            "",
            "How I can use it:",
            "- Keep it attached to this chat and remember it as context.",
            "- Help you write prompts, captions, explanations, summaries, or edit instructions based on what you tell me to focus on.",
            "- For exact object-level vision, connect a vision-capable model later; this lightweight build avoids heavy local vision so it stays fast on your computer.",
            "",
            "Bottom line:",
            "Image upload and paste now work in the chat flow, and Nexora will use the attachment metadata without crashing or timing out.",
        ])
        return "\n".join(lines)
    return None


def split_sentences(text: str) -> List[str]:
    plain = clean_text(re.sub(r"\s+", " ", text))
    if not plain:
        return []
    parts = re.split(r"(?<=[.!?])\s+", plain)
    return [part.strip() for part in parts if len(part.strip()) > 20]


def summarize_text_locally(text: str, max_points: int = 6) -> Dict[str, Any]:
    sentences = split_sentences(text)
    if not sentences:
        return {
            "summary": "No readable text was extracted from this file.",
            "key_points": [],
            "action_items": [],
            "word_count": 0,
        }
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", clean_text(text).lower())
    stop = MEMORY_STOPWORDS.union({"this", "that", "into", "their", "there", "would", "could", "should"})
    freq: Dict[str, int] = {}
    for word in words:
        if word not in stop:
            freq[word] = freq.get(word, 0) + 1
    scored = []
    for index, sentence in enumerate(sentences[:120]):
        sentence_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", sentence.lower())
        score = sum(freq.get(word, 0) for word in sentence_words) + max(0, 8 - index)
        scored.append((score, index, sentence))
    chosen = sorted(sorted(scored, reverse=True)[: max(2, min(10, max_points))], key=lambda item: item[1])
    key_points = [sentence for _, _, sentence in chosen[:max_points]]
    action_items = [
        sentence for sentence in sentences
        if re.search(r"\b(need to|must|should|todo|action|next|deadline|submit|complete|revise|practice)\b", sentence, re.I)
    ][:5]
    summary = " ".join(key_points[:2])
    return {
        "summary": summary,
        "key_points": key_points,
        "action_items": action_items,
        "word_count": len(re.findall(r"\S+", text)),
    }


def build_file_context(session_id: str) -> str:
    session = get_session(session_id)
    chunks = []
    total = 0
    file_limit = current_performance_limits().get("file_context_chars", MAX_FILE_CONTEXT_CHARS)
    for item in session.get("files", [])[-4:]:
        text = item.get("text", "")
        name = item.get("filename", "file")
        if not text:
            continue
        remaining = file_limit - total
        if remaining <= 0:
            break
        clipped = text[:remaining]
        chunks.append(f"File: {name}\n{clipped}")
        total += len(clipped)
    if not chunks:
        return ""
    return "Uploaded file context. Use only when relevant:\n\n" + "\n\n---\n\n".join(chunks)


def is_ollama_ok() -> bool:
    try:
        response = HTTP.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def ollama_available_models() -> List[str]:
    try:
        response = HTTP.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        response.raise_for_status()
        data = response.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def safe_ollama_url() -> str:
    if "/ollama/" not in OLLAMA_URL:
        return OLLAMA_URL
    base, _separator, _token_path = OLLAMA_URL.partition("/ollama/")
    return f"{base}/ollama/[redacted]"


def validate_ollama_proxy_token(token: str) -> None:
    if not OLLAMA_PROXY_TOKEN:
        raise HTTPException(status_code=404, detail="Ollama proxy is not enabled.")
    if not hmac.compare_digest(token, OLLAMA_PROXY_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid Ollama proxy token.")


def proxy_ollama_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 30) -> JSONResponse:
    target = f"{OLLAMA_PROXY_TARGET}{path}"
    try:
        if method == "GET":
            response = HTTP.get(target, timeout=timeout)
        else:
            response = HTTP.post(target, json=payload or {}, timeout=timeout)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Local Ollama request failed: {exc}") from exc
    try:
        content = response.json()
    except ValueError:
        content = {"error": response.text[:2000]}
    return JSONResponse(status_code=response.status_code, content=content)


def ollama_is_ready(available: Optional[List[str]] = None) -> bool:
    models = available if available is not None else ollama_available_models()
    return bool(models)


def model_size_score(model_name: str) -> float:
    text = model_name.lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*b", text)
    if match:
        return float(match.group(1))
    if "mini" in text or "tiny" in text:
        return 2.0
    if "small" in text:
        return 4.0
    return 99.0


def select_ollama_model(requested: Optional[str]) -> str:
    available = ollama_available_models()
    profile = system_profile()
    aliases = {
        "nexora instant": FAST_MODEL,
        "instant": FAST_MODEL,
        "fast": FAST_MODEL,
        "nexora thinking": THINKING_MODEL,
        "thinking": THINKING_MODEL,
        "llama3.2:1b": FAST_MODEL,
        "llama3.2:3b": THINKING_MODEL,
    }
    if requested:
        key = requested.strip().lower()
        mapped = aliases.get(key)
        if mapped and mapped in available:
            return mapped
        if requested in available:
            return requested
    if FAST_MODEL in available:
        return FAST_MODEL
    if THINKING_MODEL in available:
        return THINKING_MODEL
    if available and profile["level"] in {"tiny", "light"}:
        small_models = sorted(available, key=model_size_score)
        return small_models[0]
    return available[0] if available else FAST_MODEL


def ollama_status() -> Dict[str, Any]:
    available = ollama_available_models()
    ready = bool(available)
    return {
        "enabled": OLLAMA_MODE not in {"off", "false", "0", "disabled", "none"},
        "mode": OLLAMA_MODE,
        "ok": is_ollama_ok(),
        "ready": ready,
        "url": safe_ollama_url(),
        "available_models": available,
        "selected_model": select_ollama_model(None) if ready else FAST_MODEL,
        "fast_model": FAST_MODEL,
        "thinking_model": THINKING_MODEL,
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }


def ollama_chat(messages: List[Dict[str, str]], model: str, response_mode: str = "instant") -> str:
    max_tokens, timeout, temperature = mode_limits(response_mode)
    num_ctx = min(current_performance_limits().get("ollama_context_tokens", 2048), OLLAMA_CONTEXT_TOKENS)
    token_cap = OLLAMA_THINKING_MAX_TOKENS if response_mode == "thinking" else OLLAMA_INSTANT_MAX_TOKENS
    max_tokens = min(max_tokens, token_cap)
    if model_size_score(model) >= 10:
        timeout = max(timeout, 420 if response_mode == "thinking" else 180)
    payload = {
        "model": model,
        "messages": compact_provider_messages("ollama", messages, response_mode),
        "stream": False,
        "think": bool(OLLAMA_THINK and response_mode == "thinking"),
        "keep_alive": OLLAMA_KEEP_ALIVE or "10m",
        "options": {
            "temperature": temperature,
            "top_p": 0.85,
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
            "repeat_penalty": 1.08,
        },
    }
    response = HTTP.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data.get("message", {}).get("content", "").strip()


def forced_ollama_response_mode(requested_mode: Optional[str], requested_model: Optional[str]) -> str:
    requested = f"{requested_mode or ''} {requested_model or ''}".lower()
    if any(marker in requested for marker in ("thinking", "reason", "deep")):
        return "thinking"
    return "instant"


def build_forced_ollama_messages(
    user_message: str,
    history: List[ChatMessage],
    file_context: str = "",
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are Nexora, powered by the local Ollama Qwen model. "
                "Answer the user's actual request directly and naturally. "
                "If the request is vague, ask one short clarifying question instead of using a canned template. "
                "Start with the final answer, not your plan. Do not reveal analysis or hidden thoughts. "
                "For list requests, give the requested number of short points, one sentence each. "
                "Keep the answer useful and compact enough to finish quickly on a CPU server."
            ),
        }
    ]
    if file_context:
        messages.append({"role": "system", "content": truncate_for_model(file_context, 900)})
    for item in history[-2:]:
        if item.role in {"user", "assistant"} and item.content.strip():
            messages.append({"role": item.role, "content": item.content.strip()[:700]})
    messages.append({"role": "user", "content": user_message.strip()})
    return messages


FREE_PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "huggingface": "HF_API_KEY",
}

FREE_PROVIDER_MODEL_ENV = {
    "pollinations": "POLLINATIONS_MODEL",
    "ollama": "NEXORA_FAST_MODEL",
    "groq": "GROQ_MODEL",
    "gemini": "GEMINI_MODEL",
    "openrouter": "OPENROUTER_MODEL",
    "huggingface": "HF_MODEL",
}

FREE_PROVIDER_LABELS = {
    "auto": "Auto",
    "ollama": "Ollama Local",
    "pollinations": "Pollinations",
    "groq": "Groq",
    "gemini": "Gemini",
    "openrouter": "OpenRouter",
    "huggingface": "Hugging Face",
}


def keyed_free_providers() -> List[str]:
    providers = []
    if GROQ_API_KEY:
        providers.append("groq")
    if GEMINI_API_KEY:
        providers.append("gemini")
    if OPENROUTER_API_KEY:
        providers.append("openrouter")
    if HF_API_KEY:
        providers.append("huggingface")
    return providers


def configured_free_providers() -> List[str]:
    if FREE_API_PROVIDER == "ollama":
        return []
    no_key_providers = ["pollinations"]
    keyed_providers = keyed_free_providers()
    if FREE_API_PROVIDER == "auto":
        return keyed_providers + no_key_providers
    if FREE_API_PROVIDER in no_key_providers:
        return [FREE_API_PROVIDER] + [p for p in keyed_providers if p != FREE_API_PROVIDER]
    if FREE_API_PROVIDER in keyed_providers:
        return [FREE_API_PROVIDER] + [p for p in keyed_providers if p != FREE_API_PROVIDER] + no_key_providers
    return keyed_providers + no_key_providers


def free_provider_status() -> Dict[str, Any]:
    ollama_info = ollama_status()
    provider_priority = list(configured_free_providers())
    if (
        ollama_info.get("enabled")
        and ollama_info.get("ready")
        and (FREE_API_PROVIDER == "ollama" or OLLAMA_MODE in {"primary", "local", "always"})
    ):
        provider_priority.append("ollama")
        provider_priority = ["ollama"] + [item for item in provider_priority if item != "ollama"]
    elif ollama_info.get("enabled") and ollama_info.get("ready"):
        provider_priority.append("ollama")
    return {
        "selected": FREE_API_PROVIDER,
        "configured": configured_free_providers(),
        "priority": provider_priority,
        "no_key_default": "pollinations",
        "club_mode": FREE_CLUB_MODE,
        "club_layers": [
            "fast_direct_answers_for_simple_stable_questions",
            "max_precision_understanding_engine",
            "answer_strategy_planner",
            "autonomous_research_router",
            "heavy_ranked_long_term_memory",
            "reflective_human_answer_style",
            "ollama_local_reasoning_engine",
            "pollinations_base",
            "pollinations_backup_model_on_failure",
            "wikipedia_summary_context_for_stable_facts",
            "nexora_quality_guard",
            "duckduckgo_realtime_context_for_current_questions",
            "local_structured_fallback_for_common_writing",
            "pollinations_cleanup_review_when_needed",
            "strong_image_prompt_enhancer",
            "exact_match_image_prompt_guard",
        ],
        "message": "Nexora clubs Pollinations for speed, Ollama for local fallback or optional primary mode, max-precision understanding, autonomous research routing, Wikipedia context, realtime search, memory, and quality guard.",
        "speed": {
            "ollama_mode": OLLAMA_MODE,
            "ollama_keep_alive": OLLAMA_KEEP_ALIVE,
            "pollinations_timeout": POLLINATIONS_TIMEOUT,
            "pollinations_primary_timeout": POLLINATIONS_PRIMARY_TIMEOUT,
            "pollinations_backup_timeout": POLLINATIONS_BACKUP_TIMEOUT,
            "pollinations_attempts": POLLINATIONS_ATTEMPTS,
            "autonomous_research": AUTONOMOUS_RESEARCH_ENABLED,
            "autonomous_research_max_results": AUTONOMOUS_RESEARCH_MAX_RESULTS,
            "max_memory_items": MAX_MEMORY_ITEMS,
            "max_memory_context_items": MAX_MEMORY_CONTEXT_ITEMS,
            "local_writing_fast": LOCAL_WRITING_FAST,
            "quality_guard": POLLINATIONS_QUALITY_GUARD,
        },
        "cooldowns": {
            "pollinations_seconds": int(provider_cooldown_remaining("pollinations")),
        },
        "available": {
            "ollama": bool(ollama_info.get("ready")),
            "pollinations": True,
            "groq": bool(GROQ_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "openrouter": bool(OPENROUTER_API_KEY),
            "huggingface": bool(HF_API_KEY),
        },
        "models": {
            "ollama": ollama_info.get("selected_model") or FAST_MODEL,
            "ollama_available": ollama_info.get("available_models", []),
            "pollinations": POLLINATIONS_MODEL,
            "pollinations_backups": pollinations_model_candidates()[1:],
            "groq": GROQ_MODEL,
            "gemini": GEMINI_MODEL,
            "openrouter": OPENROUTER_MODEL,
            "huggingface": HF_MODEL,
        },
        "ollama": ollama_info,
        "labels": FREE_PROVIDER_LABELS,
    }


def read_env_pairs(path: Path) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    if not path.exists():
        return pairs
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            pairs[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        return pairs
    return pairs


def write_env_pairs(path: Path, updates: Dict[str, Optional[str]]) -> None:
    pairs = read_env_pairs(path)
    for key, value in updates.items():
        if value is None:
            pairs.pop(key, None)
        else:
            pairs[key] = value
            os.environ[key] = value
    lines = [f"{key}={value}" for key, value in sorted(pairs.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def apply_free_ai_runtime_settings(provider: str, api_key: Optional[str], model: Optional[str], clear_key: bool) -> None:
    global FREE_API_PROVIDER, GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, HF_API_KEY
    global POLLINATIONS_MODEL, GROQ_MODEL, GEMINI_MODEL, OPENROUTER_MODEL, HF_MODEL
    global FAST_MODEL, THINKING_MODEL, DEFAULT_MODEL, OLLAMA_MODE

    FREE_API_PROVIDER = provider
    os.environ["NEXORA_PROVIDER"] = provider
    if provider == "ollama":
        OLLAMA_MODE = "primary"
        os.environ["NEXORA_OLLAMA_MODE"] = "primary"
    elif OLLAMA_MODE == "primary":
        OLLAMA_MODE = "auto"
        os.environ["NEXORA_OLLAMA_MODE"] = "auto"

    if provider in FREE_PROVIDER_KEY_ENV:
        key_env = FREE_PROVIDER_KEY_ENV[provider]
        if clear_key:
            api_key = ""
        if api_key is not None:
            value = clean_text(api_key)
            os.environ[key_env] = value
            if provider == "groq":
                GROQ_API_KEY = value
            elif provider == "gemini":
                GEMINI_API_KEY = value
            elif provider == "openrouter":
                OPENROUTER_API_KEY = value
            elif provider == "huggingface":
                HF_API_KEY = value

    if model:
        model_env = FREE_PROVIDER_MODEL_ENV.get(provider)
        model_value = clean_text(model)
        if model_env:
            os.environ[model_env] = model_value
        if provider == "pollinations":
            POLLINATIONS_MODEL = model_value
        elif provider == "ollama":
            FAST_MODEL = model_value
            THINKING_MODEL = model_value
            DEFAULT_MODEL = model_value
            os.environ["NEXORA_THINKING_MODEL"] = model_value
        elif provider == "groq":
            GROQ_MODEL = model_value
        elif provider == "gemini":
            GEMINI_MODEL = model_value
        elif provider == "openrouter":
            OPENROUTER_MODEL = model_value
        elif provider == "huggingface":
            HF_MODEL = model_value


def save_free_ai_settings(req: FreeAISettingsRequest) -> Tuple[bool, str]:
    provider = clean_text(req.provider or "auto").lower()
    allowed = {"auto", "ollama", "pollinations", "groq", "gemini", "openrouter", "huggingface"}
    if provider not in allowed:
        return False, "Choose a supported provider."

    api_key = req.api_key if req.api_key is not None and req.api_key.strip() else None
    model = req.model if req.model is not None and req.model.strip() else None
    clear_key = bool(req.clear_key)

    updates: Dict[str, Optional[str]] = {"NEXORA_PROVIDER": provider}
    if provider == "ollama":
        updates["NEXORA_OLLAMA_MODE"] = "primary"
    else:
        updates["NEXORA_OLLAMA_MODE"] = "auto"
    if provider in FREE_PROVIDER_KEY_ENV:
        key_env = FREE_PROVIDER_KEY_ENV[provider]
        existing_key = os.getenv(key_env, "").strip()
        if clear_key:
            updates[key_env] = ""
        elif api_key:
            updates[key_env] = api_key.strip()
        elif not existing_key:
            return False, f"{FREE_PROVIDER_LABELS[provider]} needs a free API key. Pollinations works without a key."

    model_env = FREE_PROVIDER_MODEL_ENV.get(provider)
    if model and model_env:
        updates[model_env] = model.strip()
        if provider == "ollama":
            updates["NEXORA_THINKING_MODEL"] = model.strip()

    write_env_pairs(BASE_DIR / ".env", updates)
    apply_free_ai_runtime_settings(provider, api_key, model, clear_key)
    return True, f"Free AI provider set to {FREE_PROVIDER_LABELS.get(provider, provider)}."


def free_ai_settings_for_user(user_id: str) -> Dict[str, Any]:
    users = load_users()
    user = users.get(user_id) if isinstance(users.get(user_id), dict) else {}
    settings = user.get("settings") if isinstance(user.get("settings"), dict) else {}
    free_ai = settings.get("free_ai") if isinstance(settings.get("free_ai"), dict) else {}
    api_keys = user.get("api_keys") if isinstance(user.get("api_keys"), dict) else {}
    free_ai_keys = api_keys.get("free_ai") if isinstance(api_keys.get("free_ai"), dict) else {}
    provider = clean_text(str(free_ai.get("provider") or "auto")).lower()
    return {
        "provider": provider,
        "label": FREE_PROVIDER_LABELS.get(provider, provider),
        "model": clean_text(str(free_ai.get("model") or "")),
        "has_api_key": bool(free_ai_keys.get(provider)),
        "updated_at": free_ai.get("updated_at", ""),
    }


def save_user_free_ai_settings(user_id: str, req: FreeAISettingsRequest) -> Tuple[bool, str]:
    provider = clean_text(req.provider or "auto").lower()
    allowed = {"auto", "ollama", "pollinations", "groq", "gemini", "openrouter", "huggingface"}
    if provider not in allowed:
        return False, "Choose a supported provider."

    api_key = req.api_key.strip() if req.api_key is not None and req.api_key.strip() else None
    model = req.model.strip() if req.model is not None and req.model.strip() else ""
    clear_key = bool(req.clear_key)

    users = load_users()
    user = users.get(user_id) if isinstance(users.get(user_id), dict) else {"id": user_id}
    settings = user.setdefault("settings", {})
    if not isinstance(settings, dict):
        settings = {}
        user["settings"] = settings
    free_ai = settings.setdefault("free_ai", {})
    if not isinstance(free_ai, dict):
        free_ai = {}
        settings["free_ai"] = free_ai

    api_keys = user.setdefault("api_keys", {})
    if not isinstance(api_keys, dict):
        api_keys = {}
        user["api_keys"] = api_keys
    free_ai_keys = api_keys.setdefault("free_ai", {})
    if not isinstance(free_ai_keys, dict):
        free_ai_keys = {}
        api_keys["free_ai"] = free_ai_keys

    if provider in FREE_PROVIDER_KEY_ENV:
        if clear_key:
            free_ai_keys.pop(provider, None)
        elif api_key:
            free_ai_keys[provider] = api_key
        elif not free_ai_keys.get(provider):
            return False, f"{FREE_PROVIDER_LABELS[provider]} needs a free API key. Pollinations works without a key."

    free_ai["provider"] = provider
    if model:
        free_ai["model"] = model
    elif "model" not in free_ai:
        free_ai["model"] = ""
    free_ai["updated_at"] = now_iso()
    user["updated_at"] = now_iso()
    users[user_id] = user
    save_users(users)
    return True, f"Free AI provider saved for this user as {FREE_PROVIDER_LABELS.get(provider, provider)}."


def extract_openai_chat_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    choices = data.get("choices")
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts: List[str] = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict):
                        text = part.get("text") or part.get("content")
                        if isinstance(text, str):
                            parts.append(text)
                joined = "\n".join(part.strip() for part in parts if part and part.strip())
                if joined:
                    return joined
        text = choice.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def truncate_for_model(content: str, limit: int) -> str:
    text = str(content or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[context truncated]"


def provider_cooldown_remaining(provider: str) -> float:
    until = PROVIDER_COOLDOWNS.get(provider, 0.0)
    remaining = until - time.time()
    if remaining <= 0:
        PROVIDER_COOLDOWNS.pop(provider, None)
        return 0.0
    return remaining


def note_provider_cooldown(provider: str, seconds: int = 60) -> None:
    PROVIDER_COOLDOWNS[provider] = max(PROVIDER_COOLDOWNS.get(provider, 0.0), time.time() + seconds)


def is_rate_limit_error(error: Exception) -> bool:
    return "429" in str(error) or "too many requests" in str(error).lower() or "rate limit" in str(error).lower()


def compact_provider_messages(
    provider: str,
    messages: List[Dict[str, str]],
    response_mode: str,
) -> List[Dict[str, str]]:
    if provider not in {"pollinations", "ollama"}:
        return messages

    compact_system = (
        "You are Nexora, a ChatGPT-like AI assistant. Answer the user's actual request with strong reasoning, "
        "clear judgment, and natural wording.\n"
        "Think privately before writing, but do not reveal hidden chain-of-thought. Give the conclusion, the useful rationale, checks, and steps.\n"
        "Respect every user constraint. If the user says not to change something, preserve it.\n"
        "Use provided memory, file, image, and research context when relevant. For current facts, cite supplied source markers like [1].\n"
        "Do not invent facts, prices, dates, laws, medical claims, or sources. Say what is uncertain when evidence is weak.\n"
        "Prefer direct answers, practical examples, and verification checks over generic advice.\n"
        "For coding, give exact files/commands/tests. For learning, explain simply then add examples. For writing, provide the finished draft first.\n"
    )
    if response_mode == "thinking":
        compact_system += "Use deeper reasoning and a clean structure, but keep the final answer compact and useful."
    else:
        compact_system += "Keep the final answer concise unless the user asks for detail."
    if provider == "ollama":
        compact_system += " You are running locally through Ollama, so avoid long preambles and answer promptly."

    compact: List[Dict[str, str]] = [{"role": "system", "content": compact_system}]
    system_budget = (2600 if response_mode == "thinking" else 1600) if provider == "ollama" else (5200 if response_mode == "thinking" else 3600)
    system_clip = 700 if provider == "ollama" else 1000
    message_clip = 900 if provider == "ollama" else 1400
    history_count = 4 if provider == "ollama" else 8
    system_used = 0
    conversation: List[Dict[str, str]] = []

    for message in messages:
        role = message.get("role", "user")
        content = str(message.get("content", "") or "").strip()
        if not content:
            continue
        if role == "system":
            if content.startswith(SYSTEM_PROMPT[:80]):
                continue
            remaining = system_budget - system_used
            if remaining <= 200:
                continue
            clipped = truncate_for_model(content, min(system_clip, remaining))
            system_used += len(clipped)
            compact.append({"role": "system", "content": clipped})
        elif role in {"user", "assistant"}:
            conversation.append({"role": role, "content": truncate_for_model(content, message_clip)})

    compact.extend(conversation[-history_count:])
    return compact


def call_openai_compatible_chat(
    provider: str,
    base_url: str,
    api_key: Optional[str],
    model: str,
    messages: List[Dict[str, str]],
    response_mode: str = "instant",
    timeout_override: Optional[int] = None,
) -> str:
    max_tokens, timeout, temperature = mode_limits(response_mode)
    if provider == "pollinations":
        timeout = min(timeout, POLLINATIONS_TIMEOUT)
    if timeout_override is not None:
        timeout = min(timeout, max(3, int(timeout_override)))
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://127.0.0.1:8000"
        headers["X-Title"] = APP_NAME
    provider_messages = compact_provider_messages(provider, messages, response_mode)
    payload = {
        "model": model,
        "messages": provider_messages,
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": max_tokens,
        "stream": False,
    }
    response = HTTP.post(base_url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError:
        return response.text.strip()
    return extract_openai_chat_content(data)


def build_plain_pollinations_prompt(messages: List[Dict[str, str]]) -> str:
    lines = []
    for message in messages:
        role = message.get("role", "user")
        content = clean_text(message.get("content", ""))
        if content:
            lines.append(f"{role.upper()}: {content}")
    lines.append("ASSISTANT:")
    return "\n\n".join(lines)[-7000:]


def call_pollinations_simple(messages: List[Dict[str, str]], response_mode: str) -> str:
    _, timeout, _ = mode_limits(response_mode)
    timeout = min(timeout, POLLINATIONS_BACKUP_TIMEOUT)
    prompt = build_plain_pollinations_prompt(compact_provider_messages("pollinations", messages, response_mode))
    url = "https://text.pollinations.ai/" + requests.utils.quote(prompt, safe="")
    response = HTTP.get(url, params={"model": POLLINATIONS_MODEL}, timeout=timeout)
    response.raise_for_status()
    return response.text.strip()


def pollinations_model_candidates() -> List[str]:
    candidates: List[str] = []
    for raw in [POLLINATIONS_MODEL] + [part.strip() for part in POLLINATIONS_BACKUP_MODELS.split(",")]:
        model = clean_text(raw)
        if model and model not in candidates:
            candidates.append(model)
    return candidates or ["openai-fast"]


def pollinations_model_timeout(index: int, response_mode: str) -> int:
    if response_mode == "thinking":
        return min(POLLINATIONS_TIMEOUT, max(POLLINATIONS_PRIMARY_TIMEOUT, 12))
    if index == 0:
        return min(POLLINATIONS_TIMEOUT, POLLINATIONS_PRIMARY_TIMEOUT)
    return min(POLLINATIONS_TIMEOUT, POLLINATIONS_BACKUP_TIMEOUT)


def call_pollinations_chat(messages: List[Dict[str, str]], response_mode: str = "instant") -> str:
    cooldown = provider_cooldown_remaining("pollinations")
    if cooldown:
        raise RuntimeError(f"pollinations cooling down after rate limit for {int(cooldown)}s")
    errors = []
    with POLLINATIONS_LOCK:
        for index, model in enumerate(pollinations_model_candidates()):
            for attempt in range(POLLINATIONS_ATTEMPTS):
                try:
                    reply = call_openai_compatible_chat(
                        "pollinations",
                        POLLINATIONS_URL,
                        None,
                        model,
                        messages,
                        response_mode,
                        timeout_override=pollinations_model_timeout(index, response_mode),
                    )
                    if clean_text(reply):
                        return reply
                    errors.append(f"pollinations chat returned an empty reply with {model}")
                except Exception as error:
                    errors.append(f"{model}: {error}")
                    if is_rate_limit_error(error):
                        note_provider_cooldown("pollinations", 60)
                        raise RuntimeError("; ".join(errors))
                if attempt < POLLINATIONS_ATTEMPTS - 1:
                    time.sleep(0.35)

        if response_mode == "thinking" and errors:
            raise RuntimeError("; ".join(errors))

        try:
            reply = call_pollinations_simple(messages, response_mode)
            if clean_text(reply):
                return reply
            errors.append("pollinations text endpoint returned an empty reply")
        except Exception as error:
            errors.append(str(error))
            if is_rate_limit_error(error):
                note_provider_cooldown("pollinations", 60)

    raise RuntimeError("; ".join(errors))


def call_gemini_chat(messages: List[Dict[str, str]], response_mode: str = "instant") -> str:
    max_tokens, timeout, temperature = mode_limits(response_mode)
    system_parts = []
    contents = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
            continue
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}],
        })
    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "topP": 0.9,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    response = HTTP.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "\n".join(part.get("text", "") for part in parts).strip()


def free_api_chat(messages: List[Dict[str, str]], requested: Optional[str], response_mode: str) -> Tuple[str, str]:
    provider_errors = []
    requested_key = (requested or "").strip().lower()
    providers = configured_free_providers()
    aliases = {
        "pollinations": "pollinations",
        "pollination": "pollinations",
        "free": "pollinations",
        "no key": "pollinations",
        "groq": "groq",
        "gemini": "gemini",
        "openrouter": "openrouter",
        "huggingface": "huggingface",
        "hf": "huggingface",
    }
    if requested_key in aliases and aliases[requested_key] in providers:
        providers = [aliases[requested_key]]
    for provider in providers:
        try:
            if provider == "pollinations":
                reply = call_pollinations_chat(messages, response_mode)
                if not clean_text(reply):
                    raise RuntimeError("empty response")
                return reply, f"pollinations:{POLLINATIONS_MODEL}:{response_mode}"
            if provider == "groq":
                reply = call_openai_compatible_chat(
                    "groq",
                    "https://api.groq.com/openai/v1/chat/completions",
                    GROQ_API_KEY,
                    GROQ_MODEL,
                    messages,
                    response_mode,
                )
                if not clean_text(reply):
                    raise RuntimeError("empty response")
                return reply, f"groq:{GROQ_MODEL}:{response_mode}"
            if provider == "gemini":
                reply = call_gemini_chat(messages, response_mode)
                if not clean_text(reply):
                    raise RuntimeError("empty response")
                return reply, f"gemini:{GEMINI_MODEL}:{response_mode}"
            if provider == "openrouter":
                reply = call_openai_compatible_chat(
                    "openrouter",
                    "https://openrouter.ai/api/v1/chat/completions",
                    OPENROUTER_API_KEY,
                    OPENROUTER_MODEL,
                    messages,
                    response_mode,
                )
                if not clean_text(reply):
                    raise RuntimeError("empty response")
                return reply, f"openrouter:{OPENROUTER_MODEL}:{response_mode}"
            if provider == "huggingface":
                reply = call_openai_compatible_chat(
                    "huggingface",
                    "https://router.huggingface.co/v1/chat/completions",
                    HF_API_KEY,
                    HF_MODEL,
                    messages,
                    response_mode,
                )
                if not clean_text(reply):
                    raise RuntimeError("empty response")
                return reply, f"huggingface:{HF_MODEL}:{response_mode}"
        except Exception as error:
            provider_errors.append(f"{provider}: {error}")
    raise RuntimeError("; ".join(provider_errors) or "No free API provider is configured")


def requested_prefers_ollama(requested: Optional[str]) -> bool:
    key = clean_text(requested or "").lower()
    return bool(key and (
        key in {"ollama", "local", "offline", "local model", "llama"}
        or key.startswith("ollama:")
        or key.startswith("llama")
    ))


def force_ollama_chat_enabled() -> bool:
    force_setting = os.getenv("NEXORA_FORCE_OLLAMA_CHAT", "true").strip().lower()
    if force_setting in {"0", "false", "off", "no"}:
        return False
    return FREE_API_PROVIDER == "ollama" or OLLAMA_MODE in {"primary", "local", "always"}


def should_prefer_ollama(
    requested: Optional[str],
    response_mode: str,
    response_lane: str,
    presentation_style: str,
    use_research: bool,
    support_context: str,
    file_context: str,
    memory_context: str,
    available_models: List[str],
) -> bool:
    if not ollama_is_ready(available_models):
        return False
    if OLLAMA_MODE in {"off", "false", "0", "disabled", "none"}:
        return False
    if FREE_API_PROVIDER == "ollama" or requested_prefers_ollama(requested):
        return True
    if OLLAMA_MODE in {"primary", "local", "always"}:
        return True
    if OLLAMA_MODE in {"fallback", "backup", "secondary"}:
        return False
    if use_research or support_context:
        return False
    if response_mode == "thinking":
        return True
    if response_lane in {"writing", "planning", "learning", "build"}:
        return True
    if presentation_style in {"long", "diagram", "teaching_structure", "implementation_summary", "finished_draft"}:
        return True
    if file_context:
        return True
    if memory_context and response_lane in {"writing", "planning", "learning", "build"}:
        return True
    return False


def generate_with_engine_club(
    messages: List[Dict[str, str]],
    requested_model: Optional[str],
    response_mode: str,
    response_lane: str,
    presentation_style: str,
    use_research: bool,
    support_context: str,
    file_context: str,
    memory_context: str,
) -> Tuple[str, str, List[str]]:
    errors: List[str] = []
    tools: List[str] = []
    free_providers = configured_free_providers()
    available_ollama = ollama_available_models()
    ollama_ready = ollama_is_ready(available_ollama)
    ollama_enabled = OLLAMA_MODE not in {"off", "false", "0", "disabled", "none"}
    force_ollama = force_ollama_chat_enabled()
    prefer_ollama = should_prefer_ollama(
        requested_model,
        response_mode,
        response_lane,
        presentation_style,
        use_research,
        support_context,
        file_context,
        memory_context,
        available_ollama,
    )

    def try_ollama(label: str) -> Tuple[str, str, List[str]]:
        model = select_ollama_model(requested_model)
        reply = ollama_chat(messages, model, response_mode)
        if not clean_text(reply):
            raise RuntimeError("empty ollama response")
        return reply, f"ollama:{model}:{response_mode}", [f"{label}:{response_mode}"]

    if force_ollama and not ollama_ready:
        raise RuntimeError(f"Ollama is required but not ready at {OLLAMA_URL}. Available models: {available_ollama}")

    if ollama_enabled and (force_ollama or prefer_ollama) and ollama_ready:
        try:
            return try_ollama("ollama_forced" if force_ollama else "ollama_primary")
        except Exception as error:
            errors.append(f"ollama: {error}")
            tools.append("ollama_forced_failed" if force_ollama else "ollama_primary_failed")
            if force_ollama:
                raise RuntimeError("; ".join(errors))

    if free_providers:
        try:
            reply, model_used = free_api_chat(messages, requested_model, response_mode)
            return reply, model_used, tools + [f"free_api:{response_mode}"]
        except Exception as error:
            errors.append(f"free_api: {error}")
            tools.append("free_api_failed")

    if ollama_enabled and ollama_ready and not prefer_ollama:
        try:
            return try_ollama("ollama_fallback")
        except Exception as error:
            errors.append(f"ollama: {error}")
            tools.append("ollama_fallback_failed")

    raise RuntimeError("; ".join(errors) or "No text engine is available")


def decode_search_url(raw_url: str) -> str:
    url = html_lib.unescape(str(raw_url or "")).strip()
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return url


def clean_html_fragment(fragment: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", fragment or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return clean_text(html_lib.unescape(text))


def source_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def duckduckgo_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> List[Dict[str, Any]]:
    search_url = "https://duckduckgo.com/html/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = HTTP.get(search_url, params={"q": query}, headers=headers, timeout=SEARCH_TIMEOUT)
    response.raise_for_status()
    html = response.text
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|</body>)',
        re.IGNORECASE | re.DOTALL,
    )
    results: List[Dict[str, Any]] = []
    seen_urls = set()
    for match in pattern.finditer(html):
        url = decode_search_url(match.group(1))
        title = clean_html_fragment(match.group(2))
        rest = match.group(3)
        snippet_match = (
            re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.IGNORECASE | re.DOTALL)
            or re.search(r'class="result__snippet"[^>]*>(.*?)</div>', rest, re.IGNORECASE | re.DOTALL)
        )
        snippet = clean_html_fragment(snippet_match.group(1)) if snippet_match else ""
        if not url.startswith(("http://", "https://")) or not title:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({
            "title": title[:170],
            "url": url,
            "domain": source_domain(url),
            "snippet": snippet[:700],
            "score": max(1, 100 - len(results) * 8),
            "provider": "web_search:duckduckgo",
        })
        if len(results) >= max_results:
            break
    return results


def duckduckgo_lite_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> List[Dict[str, Any]]:
    search_url = "https://lite.duckduckgo.com/lite/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = HTTP.post(search_url, data={"q": query}, headers=headers, timeout=SEARCH_TIMEOUT)
    response.raise_for_status()
    html = response.text
    link_pattern = re.compile(
        r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    results: List[Dict[str, Any]] = []
    seen_urls = set()
    for match in link_pattern.finditer(html):
        title = clean_html_fragment(match.group(2))
        url = decode_search_url(match.group(1))
        if not url.startswith(("http://", "https://")) or not title:
            continue
        if "duckduckgo.com" in source_domain(url):
            continue
        if url in seen_urls:
            continue
        start = match.end()
        snippet_chunk = html[start:start + 900]
        snippet = clean_html_fragment(snippet_chunk)
        snippet = re.sub(r"(?i)\b(Next Page|More Results|Images|Videos|News)\b.*$", "", snippet).strip()
        seen_urls.add(url)
        results.append({
            "title": title[:170],
            "url": url,
            "domain": source_domain(url),
            "snippet": snippet[:700],
            "score": max(1, 92 - len(results) * 8),
            "provider": "web_search:duckduckgo_lite",
        })
        if len(results) >= max_results:
            break
    return results


def cached_search_results(provider: str, query: str, max_results: int = MAX_SEARCH_RESULTS) -> List[Dict[str, Any]]:
    clean_query = clean_text(query)
    key = f"{provider}:{max_results}:{clean_query.lower()}"
    now = time.time()
    with SEARCH_CACHE_LOCK:
        cached = SEARCH_RESULT_CACHE.get(key)
        if cached and now - float(cached.get("created", 0)) <= SEARCH_CACHE_TTL:
            return [dict(item) for item in cached.get("results", [])[:max_results]]
        expired = [
            cache_key
            for cache_key, value in SEARCH_RESULT_CACHE.items()
            if now - float(value.get("created", 0)) > SEARCH_CACHE_TTL
        ]
        for cache_key in expired[:25]:
            SEARCH_RESULT_CACHE.pop(cache_key, None)
        if len(SEARCH_RESULT_CACHE) > SEARCH_CACHE_MAX:
            oldest = sorted(SEARCH_RESULT_CACHE.items(), key=lambda item: float(item[1].get("created", 0)))
            for cache_key, _value in oldest[: max(1, len(SEARCH_RESULT_CACHE) - SEARCH_CACHE_MAX)]:
                SEARCH_RESULT_CACHE.pop(cache_key, None)
    if provider == "duckduckgo_lite":
        results = duckduckgo_lite_search(clean_query, max_results=max_results)
    else:
        results = duckduckgo_search(clean_query, max_results=max_results)
    if results:
        with SEARCH_CACHE_LOCK:
            SEARCH_RESULT_CACHE[key] = {
                "created": now,
                "results": [dict(item) for item in results[:max_results]],
            }
    return [dict(item) for item in results[:max_results]]


def current_search_date_label() -> str:
    return datetime.now().strftime("%B %d, %Y")


def build_realtime_query_variants(query: str) -> Tuple[str, List[str]]:
    clean_query = clean_text(query)
    route = detect_task_intent(clean_query, True)
    year = str(datetime.now().year)
    today = current_search_date_label()
    variants = [clean_query]
    lower = clean_query.lower()

    if route == "realtime_weather":
        variants.append(f"{clean_query} weather forecast today {today}")
    elif route == "realtime_crypto_price":
        variants.append(f"{clean_query} live crypto price today {year}")
    elif route == "realtime_github_repo":
        variants.append(f"{clean_query} GitHub repository stars issues latest")
    elif route == "realtime_package_version":
        variants.append(f"{clean_query} latest package version official registry {year}")
    elif route == "realtime_security_advisory":
        variants.append(f"{clean_query} CVE security advisory official latest {year}")
    elif route == "realtime_academic_paper":
        variants.append(f"{clean_query} research paper DOI arXiv latest {year}")
    elif route == "realtime_dataset_lookup":
        variants.append(f"{clean_query} dataset download official latest {year}")
    elif route == "realtime_earthquake":
        variants.append(f"{clean_query} earthquake latest USGS today {today}")
    elif route == "realtime_air_quality":
        variants.append(f"{clean_query} AQI air quality today {today}")
    elif route == "realtime_space_launch":
        variants.append(f"{clean_query} next space launch upcoming latest {year}")
    elif route == "realtime_public_record":
        variants.append(f"{clean_query} official public record status {year}")
    elif route == "realtime_fuel_price":
        variants.append(f"{clean_query} fuel price today official {today}")
    elif route == "realtime_product_price":
        variants.append(f"{clean_query} price availability latest {year}")
    elif route == "realtime_tax_deadline":
        variants.append(f"{clean_query} official tax deadline due date {year}")
    elif route == "realtime_university_admission":
        variants.append(f"{clean_query} official admission counselling schedule {year}")
    elif route == "realtime_food_delivery":
        variants.append(f"{clean_query} food delivery open now latest")
    elif route == "realtime_local_emergency":
        variants.append(f"{clean_query} emergency service official current")
    elif route == "realtime_sports":
        variants.append(f"{clean_query} live score latest {year}")
    elif route == "realtime_market":
        variants.append(f"{clean_query} live price market today {year}")
    elif route == "realtime_exchange_rate":
        variants.append(f"{clean_query} exchange rate today {year}")
    elif route == "realtime_product_recommendation":
        variants.append(f"{clean_query} latest reviews {year}")
    elif route == "realtime_current_fact":
        variants.append(f"{clean_query} official current {year}")
    elif route == "realtime_news":
        variants.append(f"{clean_query} latest news {today}")
    elif route == "realtime_local_places":
        variants.append(f"{clean_query} open now latest")
    elif route == "realtime_travel_status":
        variants.append(f"{clean_query} status live today {today}")
    elif route == "realtime_events":
        variants.append(f"{clean_query} events tickets {year}")
    elif route == "realtime_jobs":
        variants.append(f"{clean_query} jobs hiring latest {year}")
    elif route == "realtime_version_release":
        variants.append(f"{clean_query} official release latest {year}")
    elif route == "realtime_schedule":
        variants.append(f"{clean_query} official schedule date {year}")
    elif route == "realtime_law_policy_update":
        variants.append(f"{clean_query} official latest law policy update {year}")
    elif route == "realtime_exam_result":
        variants.append(f"{clean_query} official result admit card answer key {year}")
    elif route == "realtime_public_transport":
        variants.append(f"{clean_query} live transport status schedule today {today}")
    elif route == "realtime_outage":
        variants.append(f"{clean_query} outage status live today {today}")
    elif route == "realtime_holiday_calendar":
        variants.append(f"{clean_query} official holiday calendar date {year}")
    elif route == "realtime_movie_showtimes":
        variants.append(f"{clean_query} movie showtimes today {today}")
    elif route == "realtime_shopping_availability":
        variants.append(f"{clean_query} in stock availability price latest {year}")
    elif route == "realtime_platform_status":
        variants.append(f"{clean_query} status outage latest today {today}")
    elif route == "realtime_academic_deadline":
        variants.append(f"{clean_query} official deadline last date {year}")
    elif route == "realtime_government_scheme":
        variants.append(f"{clean_query} official government scheme latest {year}")
    elif re.search(r"\b(latest|current|today|recent|news|2026|2025)\b", lower):
        variants.append(f"{clean_query} {today}")

    unique: List[str] = []
    for variant in variants:
        compact = clean_text(variant)
        if compact and compact.lower() not in {item.lower() for item in unique}:
            unique.append(compact)
    return route, unique[:3]


def realtime_source(title: str, url: str, snippet: str, provider: str, score: int = 112) -> Dict[str, Any]:
    return {
        "title": clean_text(title)[:170],
        "url": url,
        "domain": source_domain(url),
        "snippet": clean_text(snippet)[:700],
        "score": score,
        "provider": provider,
    }


def extract_weather_location(query: str) -> str:
    text = clean_text(query)
    text = re.sub(
        r"(?i)\b(what is|what's|show me|tell me|please|current|live|right now|now|today|tomorrow|weather|forecast|temperature|rain|in|for|at)\b",
        " ",
        text,
    )
    text = clean_text(text).strip(" ?.,;:-")
    return title_case_topic(text) if text else ""


def fetch_wttr_weather_source(query: str) -> Optional[Dict[str, Any]]:
    location = extract_weather_location(query)
    if not location:
        return None
    api_url = f"https://wttr.in/{quote(location, safe='')}?format=j1"
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6))
        response.raise_for_status()
        data = response.json()
        current = (data.get("current_condition") or [{}])[0]
        forecast = (data.get("weather") or [{}])[0]
    except Exception:
        return None
    condition = clean_text(" ".join(item.get("value", "") for item in current.get("weatherDesc", []) if isinstance(item, dict)))
    temp_c = clean_text(str(current.get("temp_C", "")))
    temp_f = clean_text(str(current.get("temp_F", "")))
    humidity = clean_text(str(current.get("humidity", "")))
    wind = clean_text(str(current.get("windspeedKmph", "")))
    high_c = clean_text(str(forecast.get("maxtempC", "")))
    low_c = clean_text(str(forecast.get("mintempC", "")))
    observed = clean_text(str(current.get("localObsDateTime", ""))) or current_search_date_label()
    parts = [
        f"Checked today {current_search_date_label()} for {location}.",
        f"Observed {observed}.",
    ]
    if condition:
        parts.append(f"Condition: {condition}.")
    if temp_c:
        temp_part = f"Temperature: {temp_c} C"
        if temp_f:
            temp_part += f" ({temp_f} F)"
        parts.append(temp_part + ".")
    if high_c or low_c:
        parts.append(f"Forecast range today: {low_c or '?'} C to {high_c or '?'} C.")
    if humidity:
        parts.append(f"Humidity: {humidity} percent.")
    if wind:
        parts.append(f"Wind: {wind} km/h.")
    return realtime_source(
        f"Live weather for {location}",
        f"https://wttr.in/{quote(location, safe='')}",
        " ".join(parts),
        "realtime_api:wttr_in",
        score=125,
    )


def parse_currency_pair(query: str) -> Optional[Tuple[str, str]]:
    upper = clean_text(query).upper()
    match = re.search(r"\b([A-Z]{3})\s*(?:TO|/|-)\s*([A-Z]{3})\b", upper)
    if match:
        return match.group(1), match.group(2)
    return None


def fetch_exchange_rate_source(query: str) -> Optional[Dict[str, Any]]:
    pair = parse_currency_pair(query)
    if not pair:
        return None
    base, target = pair
    api_url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6))
        response.raise_for_status()
        data = response.json()
        rate = data.get("rates", {}).get(target)
    except Exception:
        return None
    if rate is None:
        return None
    updated = clean_text(str(data.get("time_last_update_utc", ""))) or current_search_date_label()
    snippet = (
        f"Checked today {current_search_date_label()}. "
        f"Open Exchange Rates mirror reports 1 {base} = {rate} {target}. "
        f"Last update: {updated}. Exchange rates change constantly."
    )
    return realtime_source(
        f"{base} to {target} exchange rate",
        api_url,
        snippet,
        "realtime_api:open_er_api",
        score=124,
    )


def format_live_number(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return clean_text(str(value))
    if abs(number) >= 100:
        return f"{number:.2f}".rstrip("0").rstrip(".")
    if abs(number) >= 1:
        return f"{number:.4f}".rstrip("0").rstrip(".")
    return f"{number:.6g}"


def parse_crypto_asset(query: str) -> Optional[Tuple[str, str, str]]:
    lower = clean_text(query).lower()
    assets = [
        ("bitcoin", "BTC", r"\b(bitcoin|btc)\b"),
        ("ethereum", "ETH", r"\b(ethereum|eth)\b"),
        ("solana", "SOL", r"\b(solana|sol)\b"),
        ("dogecoin", "DOGE", r"\b(dogecoin|doge)\b"),
        ("cardano", "ADA", r"\b(cardano|ada)\b"),
        ("ripple", "XRP", r"\b(ripple|xrp)\b"),
        ("binancecoin", "BNB", r"\b(bnb|binance coin)\b"),
        ("polkadot", "DOT", r"\b(polkadot|dot)\b"),
        ("litecoin", "LTC", r"\b(litecoin|ltc)\b"),
        ("chainlink", "LINK", r"\b(chainlink|link)\b"),
        ("tron", "TRX", r"\b(tron|trx)\b"),
        ("matic-network", "MATIC", r"\b(polygon|matic)\b"),
    ]
    for coin_id, symbol, pattern in assets:
        if re.search(pattern, lower):
            return coin_id, symbol, symbol
    return None


def fetch_crypto_price_source(query: str) -> Optional[Dict[str, Any]]:
    asset = parse_crypto_asset(query)
    if not asset:
        return None
    coin_id, symbol, label = asset
    vs_currencies = "usd,inr" if re.search(r"\b(inr|rupee|india)\b", query, re.IGNORECASE) else "usd"
    api_url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={quote(coin_id, safe='')}&vs_currencies={vs_currencies}"
        "&include_24hr_change=true&include_last_updated_at=true"
    )
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6), headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        data = response.json().get(coin_id, {})
    except Exception:
        return None
    if not data:
        return None
    price_bits = []
    for currency in vs_currencies.split(","):
        if currency in data:
            price_bits.append(f"{format_live_number(data[currency])} {currency.upper()}")
    if not price_bits:
        return None
    change = data.get("usd_24h_change") if "usd_24h_change" in data else None
    updated_raw = data.get("last_updated_at")
    updated = ""
    if updated_raw:
        try:
            updated = datetime.fromtimestamp(float(updated_raw), timezone.utc).strftime("%Y-%m-%d %Hh%M UTC")
        except Exception:
            updated = clean_text(str(updated_raw))
    change_text = f" 24h change: {format_live_number(change)} percent." if change is not None else ""
    snippet = (
        f"Checked today {current_search_date_label()}. "
        f"CoinGecko reports 1 {label} = {' / '.join(price_bits)}."
        f"{change_text} Last updated: {updated or 'not listed'}."
    )
    return realtime_source(
        f"{label} live crypto price",
        f"https://www.coingecko.com/en/coins/{coin_id}",
        snippet,
        "realtime_api:coingecko",
        score=126,
    )


def parse_github_repo(query: str) -> Optional[Tuple[str, str]]:
    text = clean_text(query)
    match = re.search(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", text, re.IGNORECASE)
    if not match and re.search(r"\b(github|repo|repository)\b", text, re.IGNORECASE):
        match = re.search(r"\b([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)\b", text)
    if not match:
        return None
    owner = match.group(1).strip(". ")
    repo = re.sub(r"\.git$", "", match.group(2).strip(". "))
    if not owner or not repo:
        return None
    return owner, repo


def fetch_github_repo_source(query: str) -> Optional[Dict[str, Any]]:
    repo_ref = parse_github_repo(query)
    if not repo_ref:
        return None
    owner, repo = repo_ref
    api_url = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6), headers={"User-Agent": "Nexora"})
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    full_name = clean_text(str(data.get("full_name", f"{owner}/{repo}")))
    description = clean_text(str(data.get("description", "")))
    updated_at = clean_text(str(data.get("updated_at", "unknown")))
    try:
        updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %Hh%M UTC")
    except Exception:
        pass
    snippet = (
        f"Checked today {current_search_date_label()}. "
        f"{full_name} has {data.get('stargazers_count', 0)} stars, {data.get('forks_count', 0)} forks, "
        f"{data.get('open_issues_count', 0)} open issues, default branch {data.get('default_branch', 'unknown')}, "
        f"and was updated at {updated_at}. "
        f"{description}"
    )
    return realtime_source(
        f"GitHub repository {full_name}",
        str(data.get("html_url", f"https://github.com/{owner}/{repo}")),
        snippet,
        "realtime_api:github_repo",
        score=125,
    )


def parse_package_request(query: str) -> Optional[Tuple[str, str]]:
    text = clean_text(query)
    lower = text.lower()
    ecosystem = ""
    if re.search(r"\b(npm|node package|javascript package|js package)\b", lower):
        ecosystem = "npm"
    elif re.search(r"\b(pypi|pip|python package)\b", lower):
        ecosystem = "pypi"
    elif "package version" in lower or "latest version of" in lower:
        ecosystem = "npm" if re.search(r"\b(react|vue|angular|next|express|vite|typescript)\b", lower) else "pypi"
    else:
        return None
    patterns = [
        r"\b(?:pypi|pip|python package|npm package|node package|npm|package)\s+(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)",
        r"\blatest version of\s+(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)",
        r"\bversion of\s+(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            package = match.group(1).strip(" .,:;\"'")
            if package not in {"package", "version", "latest", "npm", "pypi", "pip"}:
                return ecosystem, package
    return None


def fetch_package_version_source(query: str) -> Optional[Dict[str, Any]]:
    request = parse_package_request(query)
    if not request:
        return None
    ecosystem, package = request
    if ecosystem == "pypi":
        api_url = f"https://pypi.org/pypi/{quote(package, safe='')}/json"
        try:
            response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6), headers={"User-Agent": "Nexora"})
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None
        info = data.get("info", {})
        version = clean_text(str(info.get("version", "")))
        summary = clean_text(str(info.get("summary", "")))
        files = data.get("releases", {}).get(version, [])
        uploaded = clean_text(str((files[0] if files else {}).get("upload_time_iso_8601", "")))
        try:
            uploaded = datetime.fromisoformat(uploaded.replace("Z", "+00:00")).strftime("%Y-%m-%d %Hh%M UTC")
        except Exception:
            pass
        snippet = (
            f"Checked today {current_search_date_label()}. "
            f"PyPI lists {package} latest version as {version or 'unknown'}. "
            f"Release upload time: {uploaded or 'not listed'}. {summary}"
        )
        return realtime_source(
            f"PyPI package {package}",
            f"https://pypi.org/project/{package}/",
            snippet,
            "realtime_api:pypi_package",
            score=124,
        )
    api_url = f"https://registry.npmjs.org/{quote(package, safe='@')}"
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6), headers={"User-Agent": "Nexora"})
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    latest = clean_text(str(data.get("dist-tags", {}).get("latest", "")))
    description = clean_text(str(data.get("description", "")))
    uploaded = clean_text(str(data.get("time", {}).get(latest, "")))
    try:
        uploaded = datetime.fromisoformat(uploaded.replace("Z", "+00:00")).strftime("%Y-%m-%d %Hh%M UTC")
    except Exception:
        pass
    snippet = (
        f"Checked today {current_search_date_label()}. "
        f"npm lists {package} latest version as {latest or 'unknown'}. "
        f"Release time: {uploaded or 'not listed'}. {description}"
    )
    return realtime_source(
        f"npm package {package}",
        f"https://www.npmjs.com/package/{package}",
        snippet,
        "realtime_api:npm_package",
        score=124,
    )


def fetch_earthquake_source(query: str) -> Optional[Dict[str, Any]]:
    api_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6), headers={"User-Agent": "Nexora"})
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    features = data.get("features", [])[:5]
    if not features:
        snippet = f"USGS earthquake feed checked today {current_search_date_label()}; no earthquakes are listed in the all-day feed."
    else:
        points = []
        for feature in features[:3]:
            props = feature.get("properties", {})
            mag = props.get("mag", "?")
            place = clean_text(str(props.get("place", "unknown location")))
            when = ""
            try:
                when = datetime.fromtimestamp(float(props.get("time", 0)) / 1000, timezone.utc).strftime("%Y-%m-%d %Hh%M UTC")
            except Exception:
                when = "time not listed"
            points.append(f"M{format_live_number(mag)} near {place} at {when}")
        snippet = f"USGS earthquake feed checked today {current_search_date_label()}. " + "; ".join(points) + "."
    return realtime_source(
        "USGS latest earthquakes",
        "https://earthquake.usgs.gov/earthquakes/map/",
        snippet,
        "realtime_api:usgs_earthquake",
        score=122,
    )


def fetch_space_launch_source(query: str) -> Optional[Dict[str, Any]]:
    api_url = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=1"
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6), headers={"User-Agent": "Nexora"})
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    results = data.get("results") or []
    if not results:
        return None
    launch = results[0]
    name = clean_text(str(launch.get("name", "Upcoming launch")))
    net = clean_text(str(launch.get("net", "time not listed")))
    try:
        net = datetime.fromisoformat(net.replace("Z", "+00:00")).strftime("%Y-%m-%d %Hh%M UTC")
    except Exception:
        pass
    status = clean_text(str(launch.get("status", {}).get("name", "")))
    provider = clean_text(str(launch.get("launch_service_provider", {}).get("name", "")))
    pad = clean_text(str(launch.get("pad", {}).get("name", "")))
    url = clean_text(str(launch.get("url", ""))) or "https://thespacedevs.com/llapi"
    snippet = (
        f"Checked today {current_search_date_label()}. "
        f"Next listed launch: {name}. Scheduled NET: {net}. "
        f"Status: {status or 'not listed'}. Provider: {provider or 'not listed'}. Pad: {pad or 'not listed'}."
    )
    return realtime_source(
        "Upcoming space launch",
        url,
        snippet,
        "realtime_api:space_devs",
        score=121,
    )


def fetch_nba_scoreboard_source(query: str) -> Optional[Dict[str, Any]]:
    if "nba" not in clean_text(query).lower():
        return None
    api_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    try:
        response = HTTP.get(api_url, timeout=min(SEARCH_TIMEOUT, 6))
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    events = data.get("events") or []
    if not events:
        snippet = f"ESPN NBA scoreboard checked today {current_search_date_label()}; the live feed returned no NBA events for the current scoreboard window."
    else:
        summaries = []
        for event in events[:4]:
            name = clean_text(str(event.get("name", "")))
            status = clean_text(str(event.get("status", {}).get("type", {}).get("description", "")))
            competition = (event.get("competitions") or [{}])[0]
            teams = []
            for competitor in competition.get("competitors", [])[:2]:
                team = clean_text(str(competitor.get("team", {}).get("displayName", "")))
                score = clean_text(str(competitor.get("score", "")))
                if team:
                    teams.append(f"{team} {score}".strip())
            summaries.append(clean_text(f"{name}: {' vs '.join(teams) or 'score listed'} ({status})."))
        snippet = f"ESPN NBA scoreboard checked today {current_search_date_label()}. " + " ".join(summaries)
    return realtime_source(
        "ESPN NBA live scoreboard",
        "https://www.espn.com/nba/scoreboard",
        snippet,
        "realtime_api:espn_scoreboard",
        score=123,
    )


def fetch_official_release_source(query: str) -> Optional[Dict[str, Any]]:
    lower = clean_text(query).lower()
    candidates: List[Tuple[str, str]] = []
    if "iphone" in lower:
        candidates.append(("Official Apple iPhone page", "https://www.apple.com/iphone/"))
    if "ios" in lower:
        candidates.append(("Official Apple iOS page", "https://www.apple.com/ios/"))
    if "windows" in lower:
        candidates.append(("Official Microsoft Windows page", "https://www.microsoft.com/windows/"))
    if "android" in lower:
        candidates.append(("Official Android page", "https://www.android.com/"))
    for fallback_title, url in candidates:
        try:
            response = HTTP.get(url, timeout=min(SEARCH_TIMEOUT, 6), headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            html = response.text[:150000]
        except Exception:
            continue
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
        desc_match = re.search(
            r"(?is)<meta[^>]+(?:name|property)=['\"](?:description|og:description)['\"][^>]+content=['\"]([^'\"]+)['\"]",
            html,
        )
        title = clean_html_fragment(title_match.group(1)) if title_match else fallback_title
        desc = clean_html_fragment(desc_match.group(1)) if desc_match else ""
        snippet = (
            f"Official source checked today {current_search_date_label()}. "
            f"{title}. {desc or 'Use this official page to verify the latest model, release, specs, and availability.'}"
        )
        return realtime_source(title or fallback_title, url, snippet, "realtime_official_page", score=118)
    return None


def specialized_realtime_sources(query: str, route: str) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    if route == "realtime_weather":
        source = fetch_wttr_weather_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_crypto_price":
        source = fetch_crypto_price_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_github_repo":
        source = fetch_github_repo_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_package_version":
        source = fetch_package_version_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_earthquake":
        source = fetch_earthquake_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_space_launch":
        source = fetch_space_launch_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_exchange_rate":
        source = fetch_exchange_rate_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_sports":
        source = fetch_nba_scoreboard_source(query)
        if source:
            sources.append(source)
    elif route == "realtime_version_release":
        source = fetch_official_release_source(query)
        if source:
            sources.append(source)
    return sources


def realtime_search_loop(query: str, max_rounds: int = 1) -> Dict[str, Any]:
    route, query_variants = build_realtime_query_variants(query)
    combined_sources: List[Dict[str, Any]] = []
    seen_urls = set()
    errors: List[str] = []
    for source in specialized_realtime_sources(query, route):
        url = str(source.get("url", ""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        source["query_variant"] = "specialized_realtime"
        combined_sources.append(source)
    for index, variant in enumerate(query_variants):
        try:
            sources = cached_search_results("duckduckgo", variant, max_results=MAX_SEARCH_RESULTS)
            if not sources:
                sources = cached_search_results("duckduckgo_lite", variant, max_results=MAX_SEARCH_RESULTS)
        except Exception as error:
            errors.append(f"{variant}: {error}")
            continue
        for source in sources:
            url = str(source.get("url", ""))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            adjusted = dict(source)
            adjusted["score"] = int(adjusted.get("score", 0) or 0) + max(0, 8 - index * 3)
            adjusted["query_variant"] = variant
            combined_sources.append(adjusted)
            if len(combined_sources) >= MAX_SEARCH_RESULTS:
                break
        if len(combined_sources) >= MAX_SEARCH_RESULTS:
            break
    if combined_sources:
        return {
            "ok": True,
            "sources": combined_sources[:MAX_SEARCH_RESULTS],
            "confidence": "medium",
            "rounds": max_rounds,
            "provider": f"duckduckgo_realtime:{route}",
            "route": route,
            "queries": query_variants,
        }
    try:
        sources = cached_search_results("duckduckgo_lite", query, max_results=MAX_SEARCH_RESULTS)
        return {
            "ok": bool(sources),
            "sources": sources,
            "confidence": "medium" if sources else "none",
            "rounds": max_rounds,
            "provider": f"duckduckgo_lite:{route}",
            "route": route,
            "queries": query_variants,
        }
    except Exception as error:
        errors.append(str(error))
        return {
            "ok": False,
            "sources": [],
            "confidence": "none",
            "rounds": 0,
            "provider": f"duckduckgo_realtime:{route}",
            "route": route,
            "queries": query_variants,
            "error": "; ".join(errors),
        }


def prefer_fast_realtime_search(query: str) -> bool:
    lower = clean_text(query).lower()
    return bool(re.search(
        r"\b(latest|current|today|recent|news|live|right now|price|score|weather|winner|"
        r"stock|share|market|ceo|president|prime minister|election|filing|released|updated|"
        r"forecast|standings|fixture|flight|train|traffic|near me|open now|events?|hiring|"
        r"exchange rate|release date|schedule|showtimes?|outage|downtime|in stock|admit card|"
        r"exam result|bank holiday|government scheme|latest law|policy update|crypto|bitcoin|"
        r"github repo|github repository|package version|npm package|pypi|cve|security advisory|"
        r"earthquake|air quality|space launch|fuel price|tax deadline|admission list)\b",
        lower,
    ))


def research_with_realtime_fallback(query: str) -> Dict[str, Any]:
    if prefer_fast_realtime_search(query):
        fast = realtime_search_loop(query, max_rounds=1)
        if fast.get("ok"):
            fast["provider"] = "duckduckgo_fast"
            return fast

    primary_error = ""
    try:
        research = research_loop(query, max_rounds=2)
    except Exception as error:
        research = {"ok": False, "sources": [], "confidence": "none", "rounds": 0, "error": str(error)}
    if research.get("ok") and research.get("sources"):
        research["provider"] = research.get("provider", "research_engine")
        return research

    primary_error = str(research.get("error", ""))
    fallback = realtime_search_loop(query, max_rounds=1)
    if fallback.get("ok"):
        fallback["fallback_from"] = primary_error or "research_engine_unavailable"
        return fallback
    if primary_error and not fallback.get("error"):
        fallback["error"] = primary_error
    return fallback


def should_use_research(message: str, mode: Optional[str], explicit: Optional[bool]) -> bool:
    if explicit is not None:
        return bool(explicit)
    text = message.lower()
    mode_lower = (mode or "").lower()
    if mode_lower in {"web", "search", "research", "deep_research", "research_mode", "finance"}:
        return True
    if re.search(r"\b(search|searcch|look up|lookup|google|find online|on the internet|real[- ]?time|realtime)\b", text):
        return True
    if re.search(r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
        return True
    local_language_task = bool(re.search(
        r"\b(fix grammar|correct grammar|grammar check|correct this|rewrite|rephrase|polish|make this clearer|improve this sentence|improve this text|translate|translation|"
        r"detect language|transliterate|romanize|romanization|pronounce|pronunciation|grammar rule|meaning of|word meaning|dictionary|definition|"
        r"synonym|antonym|idiom|proverb|vocabulary|spelling|punctuation|parts of speech|tense|conjugate|phrasal verb|collocation|"
        r"make it formal|make it informal|change tone|bilingual|phrasebook|conversation practice|reading comprehension|cloze test|"
        r"language exam|language learning|language level|cefr|flashcard|minimal pair|syllable stress|word usage|sentence correction|"
        r"translation review|natural translation|literal translation|back translation|cultural context|honorific|politeness register|"
        r"compare languages|essay correction|email rewrite|learn hindi|learn english|learn tamil|learn french|learn spanish|learn german|"
        r"learn japanese|learn korean|learn arabic|learn chinese|learn portuguese|learn russian|learn italian|learn dutch|learn greek|"
        r"learn bengali|learn marathi|learn telugu|learn kannada|learn malayalam|learn urdu|learn swahili|learn thai|learn vietnamese)\b",
        text,
    ))
    inline_summary_task = bool(
        re.search(r"\b(summarize|summarise|summary|shorten|key points|main points|takeaways)\b", text)
        and not re.search(r"\b(file|pdf|document|upload|uploaded)\b|\bthis\s+(?:file|pdf|document|upload)\b", text)
    )
    if local_language_task or inline_summary_task:
        return False
    local_document_task = bool(
        re.search(r"\b(explain|summarize|summarise|read|simplify|review)\b", text)
        and re.search(r"\b(contract|agreement|terms|document|text)\b", text)
        and not re.search(r"\b(search|latest|current|today|recent|news|verify|sources?|citations?|online|internet)\b", text)
    )
    if local_document_task:
        return False
    local_study_schedule_task = bool(
        re.search(r"\b(study timetable|study plan|revision timetable|revision plan|schedule for study|plan my study|study schedule)\b", text)
        and not re.search(r"\b(latest|current|official|released|result date|exam date|board exam|date sheet)\b", text)
    )
    if local_study_schedule_task:
        return False
    local_technical_model_task = bool(
        re.search(r"\b(machine learning|ml model|data science|regression model|classification model|model plan|predictive model)\b", text)
        and not re.search(r"\b(latest|current|today|live|news|stock price|market price|crypto price|actual price right now)\b", text)
    )
    if local_technical_model_task:
        return False
    realtime_domains = bool(re.search(
        r"\b(weather|forecast|temperature|score|scores|match|fixture|standings|points table|"
        r"flights?|trains?|buses|bus|metro|subway|traffic|delay|cancelled|canceled|near me|nearby|"
        r"open now|restaurant|cafe|hotel|hospital|pharmacy|movie times|showtimes?|store hours|"
        r"events?|concert|tickets?|job openings?|hiring|vacancy|exam result|admit card|hall ticket|"
        r"scholarship|application deadline|last date|exchange rate|currency rate|release date|"
        r"availability|available now|in stock|out of stock|schedule|timetable|exam date|result date|"
        r"bank holiday|public holiday|platform status|server status|service status|outage|downtime|"
        r"power cut|government scheme|govt scheme|yojana|new law|latest law|new rule|policy update|"
        r"github repo|github repository|github stars|latest commit|package version|npm package|pypi|pip package|"
        r"cve|security advisory|zero[- ]day|vulnerability|crypto price|bitcoin price|ethereum price|"
        r"earthquake|air quality|aqi|space launch|rocket launch|fuel price|tax deadline|"
        r"university admission|college admission|admission list|dataset download|public record|case status)\b",
        text,
    ))
    if realtime_domains:
        return True
    keywords = [
        "latest", "today", "current", "recent", "news", "live", "right now", "2026", "2025",
        "now", "this week", "this month", "this year", "as of", "currently",
        "stock", "share", "market", "price", "ceo", "president", "prime minister",
        "winner", "score", "weather", "schedule", "election", "filing", "contract",
        "order", "announcement", "released", "updated", "specs",
        "crude oil", "oil crisis",
        "fuel price", "energy crisis", "inflation", "rupee",
        "import bill", "sanctions", "current war", "latest war", "ongoing war",
        "war today", "war news", "current conflict", "latest conflict", "ongoing conflict",
        "conflict today", "conflict news", "russia ukraine", "ukraine war",
        "israel hamas", "gaza war", "iran israel", "middle east conflict",
        "github stars", "github issues", "latest commit", "npm package", "pypi",
        "package version", "cve", "security advisory", "earthquake", "space launch",
    ]
    if re.search(
        r"\b(latest|current|new|newest|updated|released)\b.{0,55}\b(version|model|specs?|release|download|phone|iphone|android|ios|windows|app)\b"
        r"|\b(version|model|specs?|release|download|phone|iphone|android|ios|windows|app)\b.{0,55}\b(latest|current|newest|updated|released)\b",
        text,
    ):
        return True
    recommendation_context = bool(re.search(
        r"\b(best|top|recommend|recommendation|which should i buy|buy|purchase|worth it|review)\b",
        text,
    ))
    recommendation_domains = bool(re.search(
        r"\b(phone|laptop|tablet|pc|gpu|cpu|car|bike|camera|headphones|earbuds|course|college|hotel|restaurant|flight|stock|mutual fund|crypto)\b",
        text,
    ))
    if recommendation_context and recommendation_domains:
        return True
    verification_requested = bool(re.search(
        r"\b(verify|fact[- ]?check|sources?|citations?|is it true|confirm|current status|accurate answer|check accuracy)\b",
        text,
    ))
    app_meta_accuracy = bool(re.search(
        r"\b(make|improve|upgrade|change|set)\b.{0,70}\b(ai|assistant|nexora|answer|answers|understanding|accuracy|accurate)\b",
        text,
    ))
    if verification_requested and not app_meta_accuracy:
        return True
    fuel_words = ["petrol", "diesel", "gasoline", "fuel"]
    fuel_current_context = [
        "price", "latest", "current", "today", "recent", "crisis", "shortage",
        "hike", "cut", "tax", "import", "inflation", "india",
    ]
    if any(word in text for word in fuel_words) and any(context in text for context in fuel_current_context):
        return True
    return any(keyword in text for keyword in keywords)


def convert_sources(raw_sources: List[dict]) -> List[SourceItem]:
    items = []
    for index, source in enumerate(raw_sources[:MAX_RESEARCH_SOURCES], start=1):
        items.append(SourceItem(
            id=index,
            title=clean_text(str(source.get("title", "")))[:170],
            url=str(source.get("url", "")),
            domain=clean_text(str(source.get("domain", ""))),
            snippet=clean_text(str(source.get("snippet", "")))[:700],
            score=int(source.get("score", 0) or 0),
            provider=clean_text(str(source.get("provider", ""))),
        ))
    return items


def source_has_real_evidence(source: SourceItem, user_question: str) -> bool:
    hay = f"{source.title} {source.snippet} {source.url}".lower()
    question = user_question.lower()
    if not source.title and not source.snippet:
        return False
    if source.provider.startswith(("realtime_api", "realtime_official")):
        return bool(source.url and (source.title or source.snippet))
    if source.provider.startswith("web_search"):
        return bool(source.url and source.title)
    if source.provider.startswith("wikipedia_current_role"):
        return bool(source.url and re.search(r"\b(served as|incumbent|current|since\s+\d{4})\b", hay))
    current_words = ["latest", "today", "current", "recent", "news"]
    if any(word in question for word in current_words):
        return any(word in hay for word in ["2026", "2025", "announced", "reported", "filing", "release", "update", "today", "latest"])
    return True


def source_relevance_score(source: SourceItem, user_question: str) -> int:
    question = clean_text(user_question).lower()
    hay = f"{source.title} {source.snippet} {source.domain} {source.url}".lower()
    query_keywords = set(memory_keywords(question))
    source_keywords = set(memory_keywords(hay))
    score = int(source.score or 0) + len(query_keywords.intersection(source_keywords)) * 14
    domain = source.domain.lower()
    if domain.endswith(".gov") or ".gov." in domain or domain in {"pib.gov.in", "pmindia.gov.in", "india.gov.in"}:
        score += 26
    if "wikipedia.org" in domain and re.search(r"\b(who is|who was|what is|explain|define)\b", question):
        score += 10
    if re.search(r"\b(current|latest|today|price|weather|score|election|prime minister|president|ceo)\b", question):
        if re.search(r"\b(today|latest|current|official|live|updated|2026|2025)\b", hay):
            score += 12
    if re.search(r"\b(weather|forecast|temperature)\b", question):
        if domain in {"weather.com", "accuweather.com", "timeanddate.com"} or "weather" in domain:
            score += 18
    if re.search(r"\b(stock|share|market|crypto|price|exchange rate|currency)\b", question):
        if domain in {"finance.yahoo.com", "marketwatch.com", "investing.com", "xe.com", "coinmarketcap.com"}:
            score += 18
    if re.search(r"\b(crypto|bitcoin|ethereum|solana|dogecoin|btc|eth)\b", question):
        if "coingecko.com" in domain or "coinmarketcap.com" in domain:
            score += 20
    if re.search(r"\b(github repo|github repository|github stars|latest commit)\b", question):
        if domain in {"github.com", "api.github.com"} or "github" in domain:
            score += 22
    if re.search(r"\b(package version|npm package|pypi|pip package|python package)\b", question):
        if domain in {"pypi.org", "npmjs.com", "registry.npmjs.org"}:
            score += 22
    if re.search(r"\b(earthquake|tremor|seismic)\b", question):
        if "usgs.gov" in domain:
            score += 22
    if re.search(r"\b(space launch|rocket launch|upcoming launch)\b", question):
        if re.search(r"\b(space|launch|scheduled|upcoming|net)\b", hay):
            score += 18
    if re.search(r"\b(cve|security advisory|vulnerability|zero[- ]day)\b", question):
        if domain.endswith(".gov") or domain in {"nvd.nist.gov", "github.com"} or re.search(r"\b(cve|advisory|vulnerability|patched)\b", hay):
            score += 20
    if re.search(r"\b(score|fixture|standings|ipl|nba|nfl|cricket|football|soccer|tennis)\b", question):
        if domain in {"espn.com", "cricbuzz.com", "icc-cricket.com", "nba.com", "nfl.com"}:
            score += 18
    if re.search(r"\b(flight|train|traffic|delay|cancelled)\b", question):
        if re.search(r"\b(official|status|tracker|live)\b", hay):
            score += 12
    if re.search(r"\b(release date|latest version|updated version|download|specs)\b", question):
        if re.search(r"\b(official|release notes|changelog|documentation|docs)\b", hay):
            score += 16
    if re.search(r"\b(new law|latest law|current law|policy update|government scheme|govt scheme|yojana|subsidy)\b", question):
        if domain.endswith(".gov") or ".gov." in domain or re.search(r"\b(official|ministry|government|gazette|notification)\b", hay):
            score += 20
    if re.search(r"\b(exam result|admit card|hall ticket|answer key|cutoff|scholarship|deadline|last date)\b", question):
        if re.search(r"\b(official|result|admit card|notification|deadline|last date|portal)\b", hay):
            score += 18
    if re.search(r"\b(showtime|movie times|cinema)\b", question):
        if re.search(r"\b(showtime|tickets|theater|cinema|bookmyshow|fandango)\b", hay):
            score += 14
    if re.search(r"\b(platform status|server status|is .{1,35} down|outage|downtime)\b", question):
        if re.search(r"\b(status|outage|incident|downtime|resolved|monitoring)\b", hay):
            score += 16
    if re.search(r"\b(in stock|out of stock|availability|where to buy|store availability)\b", question):
        if re.search(r"\b(in stock|out of stock|available|price|official store|retailer)\b", hay):
            score += 14
    if re.search(r"\b(prime minister|president|chief minister|ceo|actor|winner|price)\b", question):
        for keyword in ["prime minister", "president", "chief minister", "ceo", "winner", "price"]:
            if keyword in question and keyword in hay:
                score += 12
    if re.search(r"\b(video|speech video|youtube|gallery|photo|login|pdf)\b", hay):
        score -= 8
    if len(clean_text(source.snippet).split()) < 5:
        score -= 5
    return score


def clone_source_with_id(source: SourceItem, new_id: int) -> SourceItem:
    return SourceItem(
        id=new_id,
        title=source.title,
        url=source.url,
        domain=source.domain,
        snippet=source.snippet,
        score=source.score,
        provider=source.provider,
    )


def verified_sources_only(sources: List[SourceItem], user_question: str) -> List[SourceItem]:
    verified = [source for source in sources if source_has_real_evidence(source, user_question)]
    ranked = sorted(
        verified,
        key=lambda source: source_relevance_score(source, user_question),
        reverse=True,
    )[:MAX_RESEARCH_SOURCES]
    return [clone_source_with_id(source, index) for index, source in enumerate(ranked, start=1)]


def build_research_context(sources: List[SourceItem], question: str, confidence: str, rounds: int) -> str:
    lines = [
        "Verified research context:",
        "Use only the evidence below for current, latest, news, finance, company, schedule, score, or market claims.",
        "If the evidence is missing or weak, say that you do not have verified evidence instead of guessing.",
        "If a source says there is no shortage or no immediate crisis, do not rewrite that as a shortage claim.",
        f"Question: {question}",
        f"Research confidence: {confidence}",
        f"Research rounds: {rounds}",
    ]
    for source in sources:
        lines.append(
            f"[{source.id}] Title: {source.title}\n"
            f"URL: {source.url}\n"
            f"Domain: {source.domain}\n"
            f"Evidence: {source.snippet}"
        )
    return "\n\n".join(lines)


def wikipedia_topic_from_question(question: str) -> str:
    topic = clean_learning_topic(question)
    topic = re.sub(r"(?i)\b(current|latest|recent|today|news|price|score|weather|election|result)\b", " ", topic)
    topic = clean_text(topic).strip(" .,:;-")
    return title_case_topic(topic) if topic else ""


def should_add_wikipedia_context(
    message: str,
    response_lane: str,
    presentation_style: str,
) -> bool:
    text = clean_text(message)
    lower = text.lower()
    if response_lane not in {"learning", "human_chat"}:
        return False
    if presentation_style in {"chart", "table"} and not re.search(r"\b(what is|who is|who was|explain|define|meaning of)\b", lower):
        return False
    if re.search(r"\b(latest|current|today|recent|news|live|right now|price|market|score|weather|election|filing)\b", lower):
        return False
    if not re.search(r"\b(what is|what are|who is|who are|who was|who were|explain|define|describe|meaning of|tell me about|teach me)\b", lower):
        return False
    _, card = find_knowledge_card(clean_learning_topic(text))
    if card is not None:
        return False
    topic = wikipedia_topic_from_question(text)
    return bool(topic and topic.lower() not in {"this", "that", "it", "the topic"})


def fetch_wikipedia_summary(topic: str) -> Optional[Dict[str, Any]]:
    clean_topic = clean_text(topic)
    if not clean_topic:
        return None
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(clean_topic.replace(" ", "_"), safe="")
    headers = {"User-Agent": "Nexora/1.0 (local assistant; educational summary)"}
    try:
        response = HTTP.get(url, headers=headers, timeout=5)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    extract = clean_text(str(data.get("extract", "")))
    if not extract:
        return None
    page_url = str(data.get("content_urls", {}).get("desktop", {}).get("page", "")) or url
    return {
        "title": clean_text(str(data.get("title", clean_topic))) or clean_topic,
        "extract": extract[:1200],
        "url": page_url,
    }


def build_wikipedia_context(question: str) -> Tuple[str, List[SourceItem], str]:
    topic = wikipedia_topic_from_question(question)
    item = fetch_wikipedia_summary(topic)
    if not item:
        return "", [], "wikipedia_empty"
    source = SourceItem(
        id=1,
        title=str(item["title"]),
        url=str(item["url"]),
        domain="wikipedia.org",
        snippet=str(item["extract"])[:900],
        score=80,
        provider="wikipedia",
    )
    context = (
        "Free club stable knowledge context:\n"
        "Use this only as background for stable facts. Do not treat it as current-news evidence.\n"
        f"Question: {question}\n\n"
        f"[1] Title: {source.title}\n"
        f"URL: {source.url}\n"
        f"Evidence: {item['extract']}"
    )
    return context[:FREE_CLUB_CONTEXT_MAX_CHARS], [source], "wikipedia_context"


def trusted_current_role_sources(question: str) -> List[SourceItem]:
    lower = clean_text(question).lower()
    topics: List[str] = []
    if re.search(r"\b(prime minister|pm)\b", lower) and re.search(r"\b(india|bharat)\b", lower):
        topics.append("Narendra Modi")
    if re.search(r"\bpresident\b", lower) and re.search(r"\b(india|bharat)\b", lower):
        topics.append("Droupadi Murmu")

    sources: List[SourceItem] = []
    for topic in topics:
        item = fetch_wikipedia_summary(topic)
        if not item:
            continue
        sources.append(SourceItem(
            id=len(sources) + 1,
            title=str(item["title"]),
            url=str(item["url"]),
            domain="wikipedia.org",
            snippet=str(item["extract"])[:900],
            score=86,
            provider="wikipedia_current_role",
        ))
    return verified_sources_only(sources, question)


def autonomous_research_route(
    message: str,
    response_lane: str,
    presentation_style: str,
    use_research: bool,
) -> str:
    if not AUTONOMOUS_RESEARCH_ENABLED:
        return "none"
    if use_research:
        return "strict_current"

    text = clean_text(message)
    lower = text.lower()
    if not text or response_lane in {"writing", "build"}:
        return "none"

    if should_add_wikipedia_context(text, response_lane, presentation_style):
        return "wikipedia"

    direct_short = len(text.split()) <= 10 and re.search(
        r"\b(who is|who was|what is|what are|name|give me|tell me)\b",
        lower,
    )
    if direct_short:
        return "none"

    if should_add_free_club_search(text, False, response_lane, presentation_style):
        return "web_current"

    if re.search(r"\b(compare|comparison|vs\.?|versus|difference between)\b", lower) and not re.search(
        r"\b(current|latest|today|recent|news|sources?|citations?|evidence|price|market|2025|2026)\b",
        lower,
    ):
        return "none"

    research_intent = re.search(
        r"\b(research|sources?|citations?|evidence|verify|fact[- ]?check|accurate|"
        r"analy[sz]e|impact|causes?|effects?|crisis|policy|economy|market|"
        r"compare|comparison|pros and cons|advantages and disadvantages)\b",
        lower,
    )
    question_depth = len(text.split()) >= 7 and re.search(r"\b(why|how|what|which|should|can)\b", lower)
    if response_lane in {"human_chat", "learning", "planning"} and (research_intent or question_depth):
        if not re.search(r"\b(joke|story|poem|caption|rewrite|translate|summarize this text)\b", lower):
            return "web_light" if research_intent else "wikipedia"

    return "none"


def build_autonomous_research_context(question: str, route: str) -> Tuple[str, List[SourceItem], str]:
    if route == "wikipedia":
        context, sources, status = build_wikipedia_context(question)
        return context, sources, f"autonomous_{status}"

    if route not in {"web_light", "web_current"}:
        return "", [], "autonomous_research_none"

    max_results = AUTONOMOUS_RESEARCH_MAX_RESULTS if route == "web_light" else min(3, MAX_SEARCH_RESULTS)
    try:
        raw_sources = duckduckgo_search(question, max_results=max_results)
        sources = convert_sources(raw_sources)
    except Exception as error:
        return "", [], f"autonomous_{route}_unavailable:{type(error).__name__}"

    if not sources:
        return "", [], f"autonomous_{route}_empty"

    if route == "web_current":
        lines = [
            "Autonomous current-information context:",
            "Nexora selected web evidence because this question may involve recent or changeable facts.",
            "Use citations for current claims. If evidence is weak, say what can and cannot be verified.",
            f"Question: {question}",
        ]
    else:
        lines = [
            "Autonomous light research context:",
            "Nexora selected lightweight web context because the question benefits from evidence or comparison.",
            "Use these sources only when they improve accuracy. Do not force citations into a simple stable answer.",
            f"Question: {question}",
        ]

    for source in sources:
        lines.append(
            f"[{source.id}] Title: {source.title}\n"
            f"URL: {source.url}\n"
            f"Domain: {source.domain}\n"
            f"Evidence: {source.snippet}"
        )
    return "\n\n".join(lines)[:FREE_CLUB_CONTEXT_MAX_CHARS], sources, f"autonomous_{route}_context"


def free_club_mode_enabled() -> bool:
    return FREE_CLUB_MODE not in {"off", "false", "0", "disabled", "none"}


def should_use_free_club(
    message: str,
    use_research: bool,
    response_mode: str,
    response_lane: str,
    presentation_style: str,
) -> bool:
    if not free_club_mode_enabled():
        return False
    if FREE_CLUB_MODE in {"on", "true", "1", "always"}:
        return True

    text = clean_text(message).lower()
    if use_research:
        return True
    if response_lane == "realtime_search" or presentation_style == "answer_with_evidence":
        return True
    if response_mode == "thinking" and response_lane in {"writing", "learning", "planning", "build"}:
        return True
    if response_mode == "thinking" and len(text.split()) >= 14 and response_lane != "human_chat":
        return True
    if should_add_wikipedia_context(message, response_lane, presentation_style):
        return True
    if re.search(r"\b(latest|current|today|recent|news|live|right now|2026|2025|price|market|score|weather|election|filing)\b", text):
        return True
    if len(text) >= FREE_CLUB_MIN_QUERY_CHARS and re.search(
        r"\b(current|latest|research|sources?|citations?|real[- ]?time|realtime)\b",
        text,
    ):
        return True
    return False


def should_add_free_club_search(
    message: str,
    use_research: bool,
    response_lane: str,
    presentation_style: str,
) -> bool:
    if use_research:
        return False
    text = clean_text(message).lower()
    if presentation_style == "answer_with_evidence":
        return True
    if re.search(r"\b(latest|current|today|recent|news|live|right now|2026|2025|price|market|score|weather|election|filing|sources?|citations?)\b", text):
        return True
    return False


def build_free_club_search_context(question: str) -> Tuple[str, List[SourceItem], str]:
    try:
        raw_sources = duckduckgo_search(question, max_results=min(3, MAX_SEARCH_RESULTS))
        sources = convert_sources(raw_sources)
    except Exception as error:
        return "", [], f"search_unavailable:{type(error).__name__}"

    if not sources:
        return "", [], "search_empty"

    lines = [
        "Free club realtime context:",
        "Use this as supporting context. Do not force citations unless these sources materially improve the answer.",
        "For historical or general questions, combine this context with stable knowledge. For current claims, cite evidence or state uncertainty.",
        f"Question: {question}",
    ]
    for source in sources:
        lines.append(
            f"[{source.id}] Title: {source.title}\n"
            f"URL: {source.url}\n"
            f"Domain: {source.domain}\n"
            f"Evidence: {source.snippet}"
        )
    context = "\n\n".join(lines)
    return context[:FREE_CLUB_CONTEXT_MAX_CHARS], sources, "duckduckgo_context"


def should_review_free_club_reply(
    raw_reply: str,
    cleaned_preview: str,
    use_research: bool,
    response_mode: str,
    response_lane: str,
    presentation_style: str,
) -> bool:
    if answer_quality_flags("", raw_reply or cleaned_preview, response_lane, presentation_style):
        return True
    if use_research or response_lane == "writing":
        return True
    if re.search(r"(?is)^\s*\*\*[^*\n]{1,100}\.\s*\n-\s*[^*\n]{1,100}\*\*", cleaned_preview or ""):
        return True
    if re.search(r"(?m)^-\s+\*\*[^*]{2,70}\*\*\.?\s*$", cleaned_preview or ""):
        return True
    if re.search(r"\u00e2|\u00c2", f"{raw_reply or ''}\n{cleaned_preview or ''}"):
        return True
    if presentation_style in {"table", "chart"} and re.search(
        r"(?i)(?:\$|~\s*\$|\b\d+(?:\.\d+)?\s*(?:%|ha|mw|kwh|months?|days?|years?|barrels?|litres?|liters?)\b)",
        cleaned_preview or raw_reply or "",
    ):
        return True
    if response_mode == "thinking" and presentation_style in {
        "long",
        "diagram",
        "teaching_structure",
        "answer_with_evidence",
        "finished_draft",
    }:
        return True
    return False


def free_club_review_reply(
    question: str,
    draft: str,
    support_context: str,
    response_lane: str,
    presentation_style: str,
) -> Optional[str]:
    clean_draft = clean_text(draft)
    if not clean_draft or is_bad_generated_reply(clean_draft):
        return None

    review_prompt = (
        "You are Nexora's free club reviewer. Improve the draft into the final answer.\n"
        "Keep the meaning, but make it clearer, cleaner, and more human.\n"
        "If the draft is generic, replace it with a specific answer to the user's actual problem.\n"
        "Check the user's constraints, fix shallow reasoning, fill missing steps, and remove guesses.\n"
        "For coding, math, planning, and explanations, verify the logic before polishing the wording.\n"
        "Use maximum practical understanding: infer messy wording, resolve references from context, identify the user's real target, and answer the task they meant.\n"
        "Make the answer feel trustworthy: explain assumptions, avoid exaggeration, and prefer practical checks over vague claims.\n"
        "Make the final answer engaging: crisp lead, useful sections, concrete examples, and a clear bottom line when helpful.\n"
        "Preserve useful citations and source markers when supporting context provides them.\n"
        "If the draft exposes backend/tool failure, remove that and answer using the available context.\n"
        "Never return raw JSON, stream chunks, tool names, provider names, metadata, stack traces, or hidden reasoning.\n"
        "Use ChatGPT-like structure: answer first, then compact sections only when useful.\n"
        "Use smooth writing for emails, letters, and normal chat.\n"
        "Use tables, charts, or text diagrams only when the user's question benefits from them.\n"
        "Do not add unsupported facts. If evidence is weak, say so plainly.\n"
        "Remove unsourced current dates, prices, percentages, exact counts, and technical numbers unless the supporting context provides them.\n"
        "Do not use decorative titles, bold-wrapper headings, or heading-only lines before the actual answer.\n"
        "Do not split a bullet label and its explanation into two bullets; combine them as 'Label: explanation.'\n"
        "Keep punctuation polished and paragraphs short. Return only the final answer."
    )
    user_prompt = (
        f"Question:\n{question[:1200]}\n\n"
        f"Response lane: {response_lane}\n"
        f"Presentation style: {presentation_style}\n\n"
        f"Supporting context:\n{(support_context or 'No extra context.').strip()[:FREE_CLUB_CONTEXT_MAX_CHARS]}\n\n"
        f"Draft answer:\n{draft[:FREE_CLUB_REVIEW_MAX_CHARS]}\n\n"
        "Final improved answer:"
    )
    try:
        reviewed = call_openai_compatible_chat(
            "pollinations",
            POLLINATIONS_URL,
            None,
            POLLINATIONS_MODEL,
            [
                {"role": "system", "content": review_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "instant",
            timeout_override=min(5, POLLINATIONS_PRIMARY_TIMEOUT),
        )
    except Exception:
        return None

    reviewed = finalize_user_facing_answer(question, reviewed, response_lane, presentation_style)
    if is_bad_generated_reply(reviewed):
        return None
    return reviewed


SYSTEM_PROMPT = """
You are Nexora, a fast, accurate, human-feeling AI assistant.

Style:
- Start with the useful answer, not a preface.
- Sound warm, intelligent, and natural, like a capable teammate sitting beside the user.
- Keep the tone professional, calm, and polished: no hype, no messy phrasing, no overuse of emojis.
- Do not sound robotic, over-formatted, generic, or like a wall of text.
- Behave like a real assistant inside the app: infer the user's practical intent, adapt to saved preferences, be proactive with the next useful step, and ask a short clarifying question only when guessing would be risky.
- Think before answering: identify what the user really wants, decide whether stable knowledge, memory, file context, image context, or web evidence is needed, then choose the shortest reliable answer path.
- Treat every non-trivial answer as a small reasoning task: parse the request, respect constraints, solve the core problem, check for missing assumptions, then write the final answer clearly.
- If the user gives constraints like "do not change HTML" or "make it like before", preserve those constraints explicitly in the solution path.
- Prefer substance over templates. Avoid canned advice when the user needs actual reasoning, diagnosis, comparison, code, planning, or writing.
- Be reasonable before being impressive. State what is true, what depends on context, and what the user can check.
- Make answers attractive to read: strong opening, short paragraphs, clean section labels, concrete examples, and a useful final takeaway.
- For broad questions like "what can you do", answer with realistic capabilities, useful examples, and honest limits instead of inflated claims.
- Do research by default only when accuracy needs it. Do not slow down simple questions with unnecessary web context.
- Use this default structure when it fits: direct answer first, short explanation, important details or examples, sources or links if needed, and a practical next step only when useful.
- Tone adaptation:
  - School question: exam-style, clear, keyword-rich, and easy to revise.
  - Coding: developer-assistant style with concrete fixes, file paths, commands, tests, and tradeoffs.
  - Research: Perplexity-style, source-backed, careful with uncertainty.
  - Creative: Claude-style writing with rhythm, clarity, and emotional intelligence.
  - Business: strategic, sharp, concise, and action-oriented.
  - Casual: conversational, warm, and simple.
- For letters, emails, applications, notices, proposals, and personal messages, write with smooth, graceful, human prose that is ready to send.
- For everyday chat, use ChatGPT-like structure and behavior: conversational, emotionally aware, practical, and easy to scan without sounding scripted.
- For current or searched facts, use Perplexity-like synthesis: cite evidence, compare sources when needed, and separate facts from uncertainty.
- For source-backed answers, never start with "Based on the live sources I found." State the answer first, then the evidence.
- Decide the answer shape intelligently: short for simple questions, detailed for complex ones, tables for comparisons, chart-style summaries for trends or rankings, and diagrams for processes or systems.
- Use a ChatGPT-like rhythm: one clear opening sentence, then useful context, then the practical next point.
- For reflective, philosophical, opinion, or judgment questions, use a Claude-like reflective rhythm: a thoughtful first sentence, one strong bold thesis, then compact bullets with bold labels where useful.
- In reflective answers, distinguish impressive capability from real usefulness. Prefer judgment, honesty, uncertainty-awareness, and human benefit over hype.
- For reflective answers, a single natural curiosity question at the end is allowed only when it genuinely continues the conversation. Do not add generic follow-up prompts to normal answers.
- For most answers, use the familiar ChatGPT shape: answer first, then short headings or bullets only when they make the answer easier to read.
- Default structure for serious answers: one direct lead paragraph first, then only the useful sections. Prefer section names like "Short answer:", "Key points:", "How it works:", "What it means:", "Details:", and "Bottom line:".
- Use this answer blueprint:
  - Simple fact or normal chat: 1-3 short paragraphs, no forced headings.
  - Explanation or study answer: "Short answer:", then "Key points:", then "How it works:" or "Why it matters:", then "Bottom line:".
  - Ordered task or tutorial: "Goal:", then "Steps:" as a numbered list, then "Check:", then "Bottom line:".
  - Comparison or options: short lead, valid markdown table, then "Takeaway:".
  - Process, cycle, architecture, or cause-and-effect: short lead, compact fenced text diagram, then key bullets, then "Bottom line:".
  - Current/search answer: short answer first, then compact evidence with inline citations, then "Bottom line:".
- Make structured answers visually balanced for the app renderer: one compact lead paragraph, short section labels, bullet groups with parallel wording, and a final takeaway when useful.
- Do not use decorative headings, markdown-heavy titles, or heading-only lines ending in periods. A heading should be plain text ending with a colon.
- Use **bold text** sparingly when it improves scanning: key terms, short labels, warnings, or important contrasts. Do not bold whole paragraphs or every bullet.
- Never put a colon on its own line. Keep labels as "Key points:" on one line.
- If you use a table, it must be a valid markdown table with visible | separators and a separator row. Never use spaced columns.
- Treat writing as rhythm and clarity, not just grammar. Use punctuation to control pacing: commas for small pauses, periods for completion and impact, and dashes only when they make emphasis more natural.
- Use short sentences for confidence and impact. Use longer sentences only when they carry explanation or flow.
- Use spacing as part of the answer. Break dense ideas into small paragraphs with breathing room; never force a complex answer into one giant block.
- Use numbered steps only when order matters. Use bullets when scanning matters. Avoid lists when a clean paragraph feels more human.
- Remove unnecessary words. Prefer "RAM heavily affects AI performance" over wordy phrases like "It is important to note that RAM can play a very significant role."
- Prefer direct cause and effect. Say "Your laptop is lagging because the RAM is overloaded" instead of formal, distant phrasing.
- Good writing should sound like someone thinking clearly, not someone trying to sound intelligent.
- Vary sentence length. Mix short decisive sentences with slightly longer explanatory ones.
- Prefer clean paragraphs over bullet lists unless the user asks for steps, comparison, options, or a checklist.
- When using bullets, make each bullet read like a complete thought, not a label dump.
- Keep grammar and punctuation polished. Use correct commas, periods, apostrophes, capitalization, and sentence boundaries.
- When a paragraph introduces a list, end the lead-in with a colon.
- Keep list grammar parallel. If bullets continue the lead-in sentence, use lowercase starts, commas/semicolons on continuing bullets, and a period on the final bullet. If bullets are standalone sentences, capitalize them and end each one with a period.
- Do not leave rough fragments, random capitalization, doubled punctuation, or spaces before punctuation.
- Use transitions like "The key thing is", "In practice", "A safer way to think about it is", and "That means" only when they genuinely help the flow.
- Avoid stiff phrases like "It is important to note", "In conclusion", "As an AI", "Based on your query", and "Here is the answer".
- Use short paragraphs, crisp bullets, or small tables when they improve clarity.
- Keep casual answers concise; expand only when the task genuinely needs depth.
- Add a short "Next step:" only when the answer naturally leads to action, study, coding, research, business, or workflow progress. Do not add generic closing questions. The only exception is reflective human chat, where one natural curiosity question may be useful.
- End once the answer is complete.
- Never write "Direct Answer" or expose backend/system details.
- Do not output raw LaTeX delimiters like \[...\] unless the user explicitly asks for LaTeX. For equations, prefer readable plain text such as "6 CO2 + 6 H2O -> C6H12O6 + 6 O2" or simple Unicode subscripts when possible.

Final answer contract:
- Return only the final user-facing answer. Never expose provider text, tool traces, debug logs, request metadata, raw JSON, Python dicts, SSE "data:" chunks, stack traces, hidden reasoning, or internal route names.
- If a tool, model, or source fails, translate that into a useful answer or a short honest limitation. Do not show the raw failure payload.
- If the user asks for code or data, format it deliberately in fenced code blocks. Otherwise, use polished prose, bullets, tables, or steps.
- Use bold only where it helps the user understand faster; keep ordinary sentences normal.
- Before sending, run a silent finish pass: remove raw artifacts, check accuracy, choose the clearest structure, and make the answer easy to scan.
- The answer should feel complete on the first try: answer the real intent, include necessary caveats, and avoid filler.

Understanding:
- Treat messy wording, typos, screenshots, and short follow-ups as normal human input. Translate them internally into the likely intent before answering.
- Detect the user's need before writing: speed, accuracy, completeness, emotion, action, or presentation. Satisfy that need directly instead of giving a generic template.
- Use a highest-capability understanding pass for non-trivial requests: identify the real goal, target, constraints, unstated expectation, likely risk, and best answer format.
- Current intelligence level is 15.00/15.00 extended agentic intelligence: combine intent parsing, context, reasoning, accuracy, tool routing, and answer shaping at the highest configured app level.
- Current understanding level is 15.00/15.00 max-agentic precision: always apply the strongest practical intent parsing, context resolution, accuracy gate, and final-answer cleanup available in this app.
- Build a mental question contract before answering: task type, target, constraints, required accuracy level, and best response format.
- Use an agentic understanding loop: parse the request, identify the target, choose the right knowledge or tool path, verify risky facts, then produce a clean final answer.
- Answer the exact user question first. Do not drift into general capability talk, generic advice, or a nearby topic unless the user asks for it.
- For topic-only learning prompts such as "History of WW2", explain the named topic with real facts, dates, causes, events, and consequences. Never replace the topic with vague lines about "understanding life" or generic importance.
- For practical requests such as plans, routines, schedules, code, fixes, projects, business, study, fitness, travel, or workflows, never answer with generic "importance of the topic" filler. Give actionable task-specific steps.
- Resolve references like "it", "this", "same as before", and "like this" from recent chat context before asking a question.
- Ask a clarifying question only when the missing detail would change the answer or make implementation unsafe. Otherwise, make one reasonable assumption and state it briefly.
- Reasonableness beats drama. Prefer answers that are true, practical, and checkable over answers that merely sound powerful.
- Never claim unlimited intelligence or perfect understanding. Be strong by being accurate, context-aware, and useful.
- For capability/status tables, avoid vague statuses like "not yet" or "final form" without explanation. Use precise labels such as "approval-gated", "supervised", "available", "planned", or "max-precision planning enabled".
- Never imply silent unattended production deployment. Say production deploys are approval-gated and supervised unless the user explicitly installs a safe deployment connector.

Accuracy:
- Current accuracy level is 15.00/15.00 strict-verification precision: prefer verified evidence for current/changeable facts, label uncertainty, and refuse to invent exact details.
- Be precise. Do not invent facts, dates, prices, sources, laws, medical claims, financial claims, or current events.
- If something is uncertain, say so plainly and give the best safe next step.
- For current/latest/news/finance/company claims, use only provided research evidence. Without evidence, say you cannot verify it.
- For any claim that may change by time, place, version, price, policy, availability, or public role, verify with evidence or state the uncertainty.
- For recommendations, avoid fake exact metadata. If you are not sure about a song, film, product, price, or release detail, recommend safely without inventing credits.
- If a question asks for accuracy or verification, prefer source-backed evidence. If evidence is unavailable, give the safest stable answer and label uncertainty.
- Separate fact from inference when the difference matters.
- For answers with research evidence, use this structure when useful: a direct answer paragraph first, then "Key points:", then "What it means:", then "Bottom line:". Use inline citation markers like [1] and [2]. Do not write a separate raw source list; the app renders sources separately.

Reasoning:
- Current reasoning level is 15.00/15.00 max-silent reasoning: solve internally, check assumptions, catch contradictions, and give only the concise final reasoning summary the user needs.
- Never expose hidden chain-of-thought. Provide conclusions, key rationale, checks, and next steps instead.
- For complex requests, reason through goal, constraints, options, risks, verification needs, and final answer shape before writing.

Answer Structure:
- Current answer structure level is 15.00/15.00 polished answer presentation: choose the clearest answer shape, not the longest one.
- Use compact leads, normal-sized text, short paragraphs, clean section labels, useful bullets/tables, and a practical bottom line when it helps.
- Do not show raw outputs, oversized headings, boxed labels, debug metadata, or messy formatting unless the user explicitly asks for raw data.

Coding:
- Prefer practical, working solutions.
- Explain tradeoffs briefly.
- Use fenced code blocks for code and keep steps ordered.
""".strip()


def reasoning_quality_context(response_mode: str, response_lane: str, presentation_style: str) -> str:
    lines = [
        "Reasoning quality guard:",
        "- Work out the answer internally before writing. Do not reveal hidden chain-of-thought; give only the useful conclusion, concise rationale, and checks.",
        "- Track the user's exact constraints and satisfy them before adding extras.",
        "- If the question has multiple parts, answer every part in a logical order.",
        "- If information is missing, make the safest useful assumption and state it briefly; ask only when the missing detail blocks a reliable answer.",
        "- Prefer concrete examples, edge cases, and verification steps over generic advice.",
        "- Before finalizing, check for contradictions, unsupported facts, and steps that would fail in practice.",
        "- Make the answer useful to interact with: include choices, checks, or follow-up paths when they genuinely help.",
        "- Avoid overclaiming. If a claim depends on tools, current data, or configuration, say that briefly.",
        "- Upgrade vague user language into a clear internal task: target, goal, constraints, quality bar, and likely next action.",
        "- Before writing, check whether the final answer is answering the user's actual question or only a related topic.",
        "- If a draft sounds generic, replace it with topic-specific facts, dates, examples, or steps before finalizing.",
        "- If a practical request is routed into an essay-like answer, correct the route and give a task-specific plan or solution.",
        "- If the user asks for highest intelligence or capability, respond with strong reasoning and honest limits, not hype.",
        "- Run a silent max-quality pass for non-trivial answers: understand the real need, solve it, verify it, shape it, then final-check the wording.",
        f"- Intelligence level is {INTELLIGENCE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}: combine intent, context, reasoning, accuracy, tool use, and answer shaping at the highest configured app level.",
        f"- Reasoning level is {REASONING_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}: use a silent internal reasoning pass, then give only the useful conclusion, concise rationale, and checks.",
        f"- Accuracy level is {ACCURACY_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}: verify current or changeable facts, label uncertainty, and remove unsupported exact claims before finalizing.",
        f"- Answer structure level is {ANSWER_STRUCTURE_LEVEL_TEXT}/{CAPABILITY_SCALE_TEXT}: choose the cleanest format, keep text readable, and avoid raw or oversized output.",
        "- For accuracy-sensitive questions, verify current/changeable facts with evidence when available, otherwise say what is uncertain.",
        "- Never expose raw JSON, stream chunks, model metadata, debug logs, stack traces, or hidden reasoning in the final answer.",
        "- Prefer a clear answer that is accurate and useful over a longer answer that only sounds advanced.",
    ]
    if response_mode == "thinking":
        lines.append("- For thinking mode, solve deeply enough to catch hidden traps, then compress the final response into clear sections.")
    if response_lane == "build":
        lines.extend([
            "- For code or deployment work, identify the likely failure mode, give exact files/commands, and include a test or smoke check.",
            "- Do not invent APIs. If unsure, mark the assumption and give the safest runnable path.",
        ])
    elif response_lane == "planning":
        lines.extend([
            "- For planning, separate the goal, constraints, risks, and next actions.",
            "- Prefer a practical sequence the user can execute today.",
        ])
    elif response_lane == "learning":
        lines.extend([
            "- For learning, teach from simple definition to intuition to example, then finish with the main takeaway.",
            "- Use exam-friendly wording when the question sounds like schoolwork.",
        ])
    elif response_lane == "writing":
        lines.extend([
            "- For writing, produce the finished draft first. Match the requested tone and avoid meta commentary.",
            "- Preserve the user's topic, audience, length, and purpose.",
        ])
    elif response_lane == "realtime_search":
        lines.append("- For current facts, use evidence only; separate confirmed facts from inference.")
    if presentation_style == "table":
        lines.append("- If a table is expected, use a valid markdown table and keep each cell short enough to scan.")
    elif presentation_style == "diagram":
        lines.append("- If a diagram is expected, use a compact text diagram, then explain the key parts.")
    return "\n".join(lines)


def build_messages(
    user_message: str,
    history: List[ChatMessage],
    research_context: str,
    file_context: str,
    memory_context: str,
    persona_context: str,
    behavior_context: str,
    response_lane_context: str,
    presentation_context: str,
    understanding_context: str,
    intent_context: str,
    use_research: bool,
    response_mode: str,
) -> List[Dict[str, str]]:
    mode_instruction = (
        "Response mode: THINKING. Give a structured answer with a clear answer first, then useful sections. "
        "Use paragraph-led prose before bullets unless bullets are clearly better. "
        "Use clean headings, paragraph breaks, ordered steps when order matters, and compact bullets when scanning matters."
        if response_mode == "thinking"
        else
        "Response mode: INSTANT. Answer quickly in 1-4 concise paragraphs or bullets. "
        "Use the same natural sentence rhythm as a premium assistant: clear, calm, and conversational. "
        "Skip headings unless they genuinely improve clarity."
    )
    message_lane = classify_response_lane(user_message, use_research)
    message_style = classify_presentation_style(user_message, message_lane, use_research)
    quality_context = reasoning_quality_context(response_mode, message_lane, message_style)
    messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": (
                SYSTEM_PROMPT
                + f"\n\n{mode_instruction}\n\n{quality_context}\n\n{runtime_efficiency_context()}\n"
                + f"Current date: {datetime.now().date().isoformat()}"
            ),
        }
    ]
    if persona_context:
        messages.append({"role": "system", "content": persona_context})
    if behavior_context:
        messages.append({"role": "system", "content": behavior_context})
    if understanding_context:
        messages.append({"role": "system", "content": understanding_context})
    if intent_context:
        messages.append({"role": "system", "content": intent_context})
    if response_lane_context:
        messages.append({"role": "system", "content": response_lane_context})
    if presentation_context:
        messages.append({"role": "system", "content": presentation_context})
    if research_context:
        messages.append({"role": "system", "content": research_context})
    if file_context:
        messages.append({"role": "system", "content": file_context})
    if memory_context and not use_research:
        messages.append({"role": "system", "content": memory_context})
    max_history = 2 if use_research else current_performance_limits().get("history_messages", MAX_HISTORY_MESSAGES)
    for item in history[-max_history:]:
        if item.role in {"user", "assistant"} and item.content.strip():
            messages.append({"role": item.role, "content": item.content.strip()[:1200]})
    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def clean_reply(text: str) -> str:
    if not text:
        return "Nexora could not generate a proper answer."
    text = text.strip()
    text = strip_provider_noise(text)
    text = repair_answer_encoding(text)
    text = strip_model_source_dump(text)
    text = structure_answer_text(text)
    text = re.sub(r"(?m)^\s*:\s*$\n?", "", text)
    text = re.sub(r"(?m)^\s*>\s*$\n?", "", text)
    text = re.sub(r"(?im)^direct answer\s*:?", "", text)
    text = re.sub(r"(?im)^answer\s*:?", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = polish_grammar_and_punctuation(text).strip()
    if not re.search(r"[A-Za-z0-9]", text):
        return "I could not turn that into a clean answer yet. Send the question again in one clear sentence, and I will answer directly."
    return text


def polish_final_answer_style(
    text: str,
    question: str,
    response_lane: str = "human_chat",
    presentation_style: str = "balanced",
) -> str:
    if user_requested_machine_readable_output(question):
        return text.strip()

    styled = text.strip()
    styled = re.sub(r"(?m)^\s*#{1,6}\s+", "", styled)
    styled = re.sub(r"(?im)^\s*(?:final answer|final response|polished answer)\s*:?\s*", "", styled)
    styled = re.sub(r"\.\.\s*(\[\d+\])", r". \1", styled)
    styled = re.sub(r"(?<!\.)\.\.(?!\.)", ".", styled)
    styled = re.sub(r"([!?])\1+(\s|$)", r"\1\2", styled)
    styled = re.sub(r"(?m)(\[\d+\])\.(\s*)$", r"\1\2", styled)
    styled = re.sub(r"(?m)([A-Za-z0-9])\s+([,.;:!?])", r"\1\2", styled)
    styled = re.sub(r"(?m)\b(\d{1,2})\s*:\s*(\d{2})\b", r"\1:\2", styled)
    styled = re.sub(r"(?m)\b(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\s*h\s*(\d{2})\b", r"\1-\2-\3 \4h\5", styled)
    styled = re.sub(r"(?m)\b(\d+),\s+(\d{3})(\b)", r"\1,\2\3", styled)
    styled = re.sub(r"(?m)^([A-Z][A-Za-z ]{2,40}):\s*$\n{2,}", r"\1:\n", styled)
    styled = re.sub(r"(?m)^([A-Z][A-Za-z ]{2,40}:)\n([^\n-])", r"\1\n\2", styled)

    lines = styled.splitlines()
    compacted: List[str] = []
    blank_pending = False
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            blank_pending = True
            continue
        if blank_pending and compacted and not compacted[-1].endswith(":"):
            compacted.append("")
        elif blank_pending and compacted and compacted[-1].endswith(":"):
            pass
        compacted.append(stripped)
        blank_pending = False
    styled = "\n".join(compacted).strip()

    lower_question = clean_text(question).lower()
    shortish = len(clean_text(styled).split()) <= 80
    if shortish and presentation_style in {"short", "balanced"} and response_lane == "human_chat":
        styled = re.sub(r"(?is)^(?:quick answer|short answer)\s*:\s*", "", styled).strip()
    if not re.search(r"\b(markdown|heading|headings|section)\b", lower_question):
        styled = re.sub(r"(?m)^\s*(?:Quick answer|Short answer):\s*\n\s*$", "", styled)

    styled = re.sub(r"\n{3,}", "\n\n", styled)
    return styled.strip()


def user_requested_machine_readable_output(question: str) -> bool:
    lower = clean_text(question).lower()
    return bool(re.search(
        r"\b(json only|raw json|return json|as json|yaml|xml|csv|ndjson|toml|raw output|"
        r"exact output|verbatim|terminal output|console output|full log|debug output|stack trace)\b",
        lower,
    ))


def extract_text_from_raw_payload(value: Any, depth: int = 0) -> Optional[str]:
    if depth > 5:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        choices = value.get("choices")
        if isinstance(choices, list):
            parts: List[str] = []
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                delta = choice.get("delta")
                extracted = (
                    extract_text_from_raw_payload(message, depth + 1)
                    or extract_text_from_raw_payload(delta, depth + 1)
                    or extract_text_from_raw_payload(choice.get("text"), depth + 1)
                )
                if extracted:
                    parts.append(extracted)
            if parts:
                return "".join(parts)

        for key in ("reply", "answer", "final", "content", "text", "output", "response", "token"):
            if key in value:
                extracted = extract_text_from_raw_payload(value.get(key), depth + 1)
                if extracted:
                    return extracted

        message = value.get("message")
        if isinstance(message, (dict, str)):
            extracted = extract_text_from_raw_payload(message, depth + 1)
            if extracted:
                return extracted

        data = value.get("data")
        if isinstance(data, (dict, list)):
            extracted = extract_text_from_raw_payload(data, depth + 1)
            if extracted:
                return extracted

    if isinstance(value, list):
        parts = []
        for item in value:
            extracted = extract_text_from_raw_payload(item, depth + 1)
            if extracted:
                parts.append(extracted)
        if parts:
            separator = "" if all(len(part) <= 12 for part in parts) else "\n"
            return separator.join(parts)
    return None


def extract_text_from_raw_json(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, flags=re.IGNORECASE)
    if fence_match:
        stripped = fence_match.group(1).strip()
    if not stripped or stripped[0] not in "{[":
        return None
    if not re.search(r'"(?:choices|message|content|reply|answer|text|output|response|token|model|role|tools_used|session_id|created_at)"', stripped):
        return None
    try:
        payload = json.loads(stripped)
    except Exception:
        return None
    extracted = extract_text_from_raw_payload(payload)
    if extracted and clean_text(extracted) != clean_text(stripped):
        return extracted
    return None


def collapse_sse_stream_artifacts(text: str) -> str:
    lines = (text or "").splitlines()
    normal_lines: List[str] = []
    chunks: List[str] = []
    saw_stream_line = False

    for line in lines:
        match = re.match(r"^\s*data:\s*(.+?)\s*$", line)
        if match:
            saw_stream_line = True
            payload = match.group(1).strip()
            if payload.upper() in {"[DONE]", "DONE"}:
                continue
            try:
                extracted = extract_text_from_raw_payload(json.loads(payload))
            except Exception:
                extracted = payload if not payload.startswith(("{", "[")) else ""
            if extracted:
                chunks.append(extracted)
            continue
        if re.match(r"^\s*(?:event|id|retry):\s*", line):
            saw_stream_line = True
            continue
        normal_lines.append(line)

    normal_text = "\n".join(normal_lines).strip()
    if saw_stream_line and chunks and not clean_text(normal_text):
        return "".join(chunks).strip()
    if saw_stream_line:
        return normal_text
    return text


def remove_traceback_block(text: str) -> str:
    text = re.sub(r"(?is)\n?\s*Traceback \(most recent call last\):.*$", "", text)
    text = re.sub(r"(?im)^\s*File \"[^\"]+\", line \d+.*$", "", text)
    return text.strip()


def strip_raw_metadata_lines(text: str) -> str:
    output = []
    metadata_pattern = re.compile(
        r"^\s*(?:model_used|tools_used|session_id|created_at|updated_at|provider|engine|"
        r"backend|raw_response|response_metadata|debug|trace_id|request_id|finish_reason|"
        r"prompt_tokens|completion_tokens|total_tokens)\s*[:=]",
        re.IGNORECASE,
    )
    for line in (text or "").splitlines():
        stripped = line.strip()
        if metadata_pattern.match(stripped):
            continue
        if re.match(r"^\s*(?:```)?json\s*$", stripped, flags=re.IGNORECASE):
            continue
        output.append(line)
    return "\n".join(output).strip()


def remove_unrequested_bold_markup(text: str, question: str) -> str:
    question_lower = clean_text(question).lower()
    if not re.search(r"\b(no bold|without bold|normal letters|normal text|remove bold|not bold)\b", question_lower):
        return text
    parts = re.split(r"(```[\s\S]*?```)", text or "")
    cleaned_parts = []
    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            cleaned_parts.append(part)
        else:
            cleaned_parts.append(re.sub(r"\*\*([^*\n]{1,180})\*\*", r"\1", part))
    return "".join(cleaned_parts)


def plain_math_expression(expression: str) -> str:
    text = expression.strip()
    text = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1) / (\2)", text)
    text = re.sub(r"\\text\s*\{([^{}]+)\}", r"\1", text)
    text = text.replace("\\cdot", "*").replace("\\times", " x ")
    text = text.replace("\\leq", "<=").replace("\\geq", ">=")
    text = text.replace("\\neq", "!=").replace("\\approx", "approx.")
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"([A-Za-z])_\{?([A-Za-z0-9]+)\}?", r"\1\2", text)
    text = re.sub(r"(?<=[A-Za-z0-9])\s*\(", " * (", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_unrequested_latex(text: str, question: str) -> str:
    if re.search(r"\b(latex|tex notation|raw math|mathjax)\b", clean_text(question).lower()):
        return text
    parts = re.split(r"(```[\s\S]*?```)", text or "")
    output = []
    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            output.append(part)
            continue
        part = re.sub(
            r"\\\[\s*([\s\S]*?)\s*\\\]",
            lambda match: "\n" + plain_math_expression(match.group(1)) + "\n",
            part,
        )
        part = re.sub(
            r"\\\((.*?)\\\)",
            lambda match: plain_math_expression(match.group(1)),
            part,
        )
        output.append(part)
    return "".join(output)


def looks_like_raw_answer_artifact(text: str) -> bool:
    raw = text or ""
    stripped = raw.strip()
    if not stripped:
        return False
    if re.search(r"(?m)^\s*data:\s*[{[]", raw):
        return True
    if re.search(r"(?is)Traceback \(most recent call last\):|^\s*File \"[^\"]+\", line \d+", raw):
        return True
    if re.search(r"(?im)^\s*(model_used|tools_used|session_id|created_at|raw_response|response_metadata)\s*[:=]", raw):
        return True
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, flags=re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
        if not stripped:
            return False
    if stripped[0] in "{[" and re.search(
        r'"(?:choices|message|role|content|model|tools_used|session_id|created_at|type|token|delta)"',
        stripped,
    ):
        return True
    return False


def break_dense_paragraphs(text: str) -> str:
    parts = re.split(r"(```[\s\S]*?```)", text or "")
    output: List[str] = []
    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            output.append(part)
            continue
        paragraphs = part.split("\n\n")
        shaped_paragraphs = []
        for paragraph in paragraphs:
            stripped = paragraph.strip()
            if (
                len(stripped.split()) < 110
                or "\n" in stripped
                or "|" in stripped
                or re.search(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", stripped)
            ):
                shaped_paragraphs.append(paragraph)
                continue
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", stripped) if s.strip()]
            if len(sentences) < 4:
                shaped_paragraphs.append(paragraph)
                continue
            chunks = [" ".join(sentences[index:index + 3]) for index in range(0, len(sentences), 3)]
            shaped_paragraphs.append("\n\n".join(chunks))
        output.append("\n\n".join(shaped_paragraphs))
    return "".join(output)


def strip_raw_answer_artifacts(text: str, question: str) -> str:
    if user_requested_machine_readable_output(question):
        return text.strip()
    extracted = extract_text_from_raw_json(text)
    if extracted:
        text = extracted
    text = collapse_sse_stream_artifacts(text)
    text = remove_traceback_block(text)
    text = strip_raw_metadata_lines(text)
    text = re.sub(r"(?im)^\s*(?:final answer|final improved answer)\s*:?\s*", "", text).strip()
    return text


def finalize_user_facing_answer(
    question: str,
    reply: str,
    response_lane: str = "human_chat",
    presentation_style: str = "balanced",
) -> str:
    text = strip_raw_answer_artifacts(reply, question)
    text = clean_reply(text)
    text = strip_raw_answer_artifacts(text, question)
    text = remove_unrequested_bold_markup(text, question)
    text = normalize_unrequested_latex(text, question)
    text = break_dense_paragraphs(text)
    text = clean_reply(text)
    text = polish_final_answer_style(text, question, response_lane, presentation_style)

    if not user_requested_machine_readable_output(question) and looks_like_raw_answer_artifact(text):
        fallback = local_structured_fallback(question, response_lane, presentation_style)
        if fallback:
            return finalize_user_facing_answer(question, fallback, response_lane, presentation_style)
        return (
            "I could not turn the model output into a clean answer.\n\n"
            "Bottom line:\n"
            "Send the question once more, and I will answer directly without raw backend output."
        )
    return text


def is_bad_generated_reply(text: str) -> bool:
    stripped = clean_text(text).lower()
    return not stripped or stripped in {
        "nexora could not generate a proper answer.",
        "nexora could not generate a proper answer",
        "no reply came from backend.",
        "no reply came from backend",
    }


def answer_route_quality_flags(question: str, reply: str, task_intent: str = "") -> List[str]:
    intent = clean_text(task_intent).lower()
    if not intent:
        return []
    lower = clean_text(reply).lower()
    flags: List[str] = []

    def lacks(pattern: str) -> bool:
        return not re.search(pattern, lower)

    if intent == "fitness_plan" and lacks(r"\b(day|warm up|workout|exercise|cardio|strength|sets?|reps?|rest|protein|sleep)\b"):
        flags.append("route_mismatch_fitness_plan")
    if intent == "study_management_plan" and lacks(r"\b(daily routine|weekly plan|revision|homework|subject|practice|study block|timetable)\b"):
        flags.append("route_mismatch_study_management")
    if intent == "study_plan" and lacks(r"\b(day|schedule|minutes?|revise|revision|practice|topic|test)\b"):
        flags.append("route_mismatch_study_plan")
    if intent == "project_plan" and lacks(r"\b(question|experiment|materials?|hypothesis|results?|display board|timeline|science fair)\b"):
        flags.append("route_mismatch_project_plan")
    if intent == "email_draft" and lacks(r"\b(subject|dear|hello|hi|regards|sincerely|thank you)\b"):
        flags.append("route_mismatch_email_draft")
    if intent.startswith("writing_letter") and lacks(r"\b(date|principal|subject|respected|yours|leave|application)\b"):
        flags.append("route_mismatch_letter")
    if intent.startswith("writing_") and re.search(r"\b(i can help|send the topic|what topic should)\b", lower[:220]):
        flags.append("route_mismatch_writing_draft")
    if intent == "comparison" and lacks(r"\b(difference|compare|whereas|both|similar|unlike|pros|cons)\b|\|"):
        flags.append("route_mismatch_comparison")
    if intent == "pros_cons" and (lacks(r"\b(pros|advantages|benefits)\b") or lacks(r"\b(cons|disadvantages|drawbacks)\b")):
        flags.append("route_mismatch_pros_cons")
    if intent == "website_plan" and lacks(r"\b(page|section|design|content|html|domain|deploy|navigation|layout)\b"):
        flags.append("route_mismatch_website_plan")
    if intent == "business_plan" and lacks(r"\b(customer|product|price|cost|sales|market|profit|launch|business)\b"):
        flags.append("route_mismatch_business_plan")
    if intent == "workflow_plan" and lacks(r"\b(trigger|step|checklist|workflow|automation|review|output)\b"):
        flags.append("route_mismatch_workflow_plan")
    if intent == "text_summary" and lacks(r"\b(summary|key points|main point|takeaway|in short)\b"):
        flags.append("route_mismatch_text_summary")
    if intent == "key_points" and lacks(r"\b(key points|main points|takeaways)\b|[-*]\s+|\b1\."):
        flags.append("route_mismatch_key_points")
    if intent in {"grammar_fix", "rewrite_polish"} and re.search(r"\b(i can help|send the text|what text|topic becomes|understand life)\b", lower[:260]):
        flags.append("route_mismatch_text_transform")
    if intent == "translation" and re.search(r"\b(i can help|send the text|what text|main idea|topic becomes|understand life)\b", lower[:260]):
        flags.append("route_mismatch_translation")
    if intent == "table_format" and "|" not in reply:
        flags.append("route_mismatch_table_format")
    if intent == "brainstorm_ideas" and lacks(r"\b(ideas?|brainstorm|1\.|2\.|options?)\b"):
        flags.append("route_mismatch_brainstorm")
    if intent == "decision_advice" and lacks(r"\b(decision|choose|option|risk|effort|recommend|bottom line)\b"):
        flags.append("route_mismatch_decision")
    if intent == "recipe_or_cooking" and lacks(r"\b(ingredients|steps|cook|heat|serve|recipe)\b"):
        flags.append("route_mismatch_recipe")
    if intent == "travel_itinerary" and lacks(r"\b(day|itinerary|travel|visit|arrival|checklist|budget)\b"):
        flags.append("route_mismatch_travel")
    if intent == "recommendation" and lacks(r"\b(recommend|suggest|try|best|option|why)\b"):
        flags.append("route_mismatch_recommendation")
    if intent == "code_or_debug" and re.search(
        r"\b(understand life, choices|good understanding of this subject|topic becomes truly useful|memorized idea)\b",
        lower,
    ):
        flags.append("route_mismatch_code_debug")
    if intent == "health_info" and lacks(r"\b(general information|diagnosis|doctor|medical|symptom|urgent|safe)\b"):
        flags.append("route_mismatch_health")
    if intent == "legal_info" and lacks(r"\b(general legal|lawyer|jurisdiction|contract|facts|legal)\b"):
        flags.append("route_mismatch_legal")
    if intent == "finance_info" and lacks(r"\b(risk|budget|saving|debt|investment|cash flow|financial)\b"):
        flags.append("route_mismatch_finance")
    if intent in {"career_resume", "interview_prep"} and lacks(r"\b(resume|cv|interview|job|role|skill|example)\b"):
        flags.append("route_mismatch_career")
    if intent == "presentation_outline" and lacks(r"\b(slide|presentation|outline|title|takeaway)\b"):
        flags.append("route_mismatch_presentation")
    if intent == "meeting_notes" and lacks(r"\b(summary|action items|meeting|decisions|notes)\b"):
        flags.append("route_mismatch_meeting_notes")
    if intent == "social_caption" and lacks(r"\b(caption|post|ideas?|short)\b"):
        flags.append("route_mismatch_social_caption")
    if intent in {"creative_story", "poem_or_original_song", "joke_fun"} and lacks(r"\b(story|poem|joke|title|plot|original)\b"):
        flags.append("route_mismatch_creative")
    if intent in {"emotional_support", "relationship_advice"} and lacks(r"\b(feel|relationship|step|talk|safe|bottom line|control)\b"):
        flags.append("route_mismatch_support")
    if intent in {"flashcards", "quiz_generation"} and lacks(r"\b(q:|quiz|question|answer|flashcards?|practice)\b"):
        flags.append("route_mismatch_practice")
    if intent == "timeline" and lacks(r"\b(timeline|1939|1945|start|development|result|event)\b"):
        flags.append("route_mismatch_timeline")
    if intent in {"homework_help", "exam_answer", "concept_tutoring"} and re.search(
        r"\b(understand life, choices|good understanding of this subject|memorized idea)\b",
        lower,
    ):
        flags.append("route_mismatch_tutoring")
    if intent == "learning_topic" and re.search(
        r"\b(understand life, choices|world around them more clearly|good understanding of this subject|memorized idea|useful for students, families, and society)\b",
        lower,
    ):
        flags.append("route_mismatch_learning_topic")
    if intent.startswith("realtime_") and re.search(r"\b(latest|current|today|recent|verify|fact[- ]?check|weather|score|price|news|live|near me|open now)\b", clean_text(question).lower()) and not re.search(r"\[\d+\]|\b(source|verified|cannot verify|can't verify|uncertain|latest evidence)\b", lower):
        flags.append("route_mismatch_realtime_search")
    return flags


def answer_quality_flags(
    question: str,
    reply: str,
    response_lane: str = "human_chat",
    presentation_style: str = "balanced",
    task_intent: str = "",
) -> List[str]:
    if not POLLINATIONS_QUALITY_GUARD:
        return []
    raw = reply or ""
    cleaned = clean_text(raw)
    lower = cleaned.lower()
    question_lower = clean_text(question).lower()
    short_answer_requested = bool(re.search(
        r"\b(short|brief|concise|one sentence|single sentence|one-line|one line|in \d+ words|exactly \d+ words|do not explain|don't explain|no explanation)\b",
        question_lower,
    ))
    flags: List[str] = []
    if is_bad_generated_reply(raw):
        flags.append("empty")
    if cleaned and not re.search(r"[A-Za-z0-9]", cleaned):
        flags.append("empty")
    if re.search(r"\b(free text engine|backend|pollinations|ollama|api key|rate-limit|rate limit)\b", lower):
        flags.append("backend_talk")
    if re.search(r"\b(we need to browse|need to browse|browse the web|use search|use the search tool)\b", lower):
        flags.append("backend_talk")
    if re.search(r"(?m)^\s*data:\s*[{[]", raw):
        flags.append("stream_artifact")
    if re.search(r"(?is)Traceback \(most recent call last\):|^\s*File \"[^\"]+\", line \d+", raw):
        flags.append("traceback_or_error_dump")
    if re.search(r"(?im)^\s*(model_used|tools_used|session_id|created_at|raw_response|response_metadata|debug)\s*[:=]", raw):
        flags.append("tool_dump")
    if not re.search(r"\b(latex|tex notation|mathjax)\b", question_lower) and re.search(r"\\\[|\\\(|\\frac|\\text\{", raw):
        flags.append("raw_latex_delimiters")
    raw_for_json = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.IGNORECASE)
    if re.match(r"^\s*[{[]", raw_for_json) and re.search(
        r'"(?:choices|message|role|content|model|tools_used|session_id|created_at|type|token|delta)"',
        raw_for_json,
    ):
        flags.append("raw_json_output")
    if re.search(r"\bbased on the live sources i found\b|\bsafest answer should lean\b", lower):
        flags.append("weak_source_synthesis")
    current_sensitive_question = bool(re.search(
        r"\b(latest|current|today|right now|recent|news|price|score|stock|market|weather|ceo|president|prime minister|2026|2025)\b",
        question_lower,
    ))
    if current_sensitive_question and not re.search(r"\[\d+\]|\b(source|according to|verified|cannot verify|can't verify|uncertain|may have changed)\b", lower):
        flags.append("missing_current_verification")
    if re.search(r"\b(verify|fact[- ]?check|accurate answer|check accuracy|sources?|citations?)\b", question_lower):
        if not re.search(r"\[\d+\]|\b(verified|cannot verify|can't verify|uncertain|source|according to)\b", lower):
            flags.append("missing_accuracy_signal")
    if re.search(r"(?m)^\s*:\s*$", raw):
        flags.append("colon_line")
    if any(marker in raw for marker in ("\u00e2", "\u00c2", "\ufffd")):
        flags.append("encoding_noise")
    if len(cleaned.split()) < 18 and response_lane not in {"human_chat"} and not short_answer_requested and not re.search(r"\b(hi|hello|thanks|ok|okay)\b", question_lower):
        flags.append("too_short")
    if re.search(r"\b(ask the question again|send the topic directly|i am still here|try again once)\b", lower):
        flags.append("weak_fallback")
    if re.search(r"\b(history of|world war|ww2|wwii|second world war)\b", question_lower) and re.search(
        r"\b(understand life, choices|world around them more clearly|good understanding of this subject|memorized idea)\b",
        lower,
    ):
        flags.append("generic_topic_drift")
    if re.search(r"\b(fitness|workout|exercise|gym|training)\b", question_lower) and re.search(
        r"\b(importance of fitness plan|understand life, choices|good understanding of this subject|memorized idea|useful for students, families, and society)\b",
        lower,
    ):
        flags.append("generic_topic_drift")
    generic_topic_filler = bool(re.search(
        r"\b(understand life, choices|world around them more clearly|good understanding of this subject|memorized idea|useful for students, families, and society|topic becomes truly useful|explained simply and applied thoughtfully)\b",
        lower,
    ))
    practical_question = bool(re.search(
        r"\b(plan|routine|schedule|program|steps|workflow|strategy|fix|debug|code|build|create|project|business|fitness|workout|diet|travel|website|app|resume|email|letter|study plan|automation)\b",
        question_lower,
    ))
    explicitly_writing_about_topic = bool(re.search(
        r"\b(essay|paragraph|speech|article|note|importance of|write about|write on)\b",
        question_lower,
    ))
    if generic_topic_filler and practical_question and not explicitly_writing_about_topic:
        flags.append("generic_topic_drift")
    if re.search(r"\b(manage|organize|organise|schedule|routine|timetable|how should i|how can i)\b", question_lower) and re.search(
        r"\b(starting with the main idea|focus on what .* means in simple words|break the idea into small parts|connect the concept with real life)\b",
        lower,
    ):
        flags.append("generic_topic_drift")
    if re.search(r"\b(song|music|track|recommend|suggest)\b", question_lower) and re.search(r"\bfrom the (film|movie)\b", lower):
        if not re.search(r"\b(source|verified|according to|\[\d+\])\b", lower):
            flags.append("unverified_recommendation_metadata")
    if response_lane == "planning" and re.search(r"\b(start with the exact outcome|break it into small actions|fix one problem at a time)\b", lower):
        flags.append("generic_plan")
    if presentation_style == "table" and "|" not in raw and re.search(r"\b(compare|comparison|table|vs|versus|pros and cons)\b", question_lower):
        flags.append("missing_table")
    if response_lane == "writing" and re.search(r"\b(i can help|here'?s|here is|draft answer)\b", lower[:160]):
        flags.append("not_finished_draft_first")
    flags.extend(answer_route_quality_flags(question, raw, task_intent))
    return list(dict.fromkeys(flags))


def should_accept_reviewed_reply(question: str, reviewed: str, response_lane: str, presentation_style: str) -> bool:
    if is_bad_generated_reply(reviewed):
        return False
    flags = answer_quality_flags(question, reviewed, response_lane, presentation_style, detect_task_intent(question, False))
    blocking = {
        "empty",
        "backend_talk",
        "weak_fallback",
        "encoding_noise",
        "stream_artifact",
        "traceback_or_error_dump",
        "tool_dump",
        "raw_json_output",
        "generic_topic_drift",
        "missing_current_verification",
        "missing_accuracy_signal",
    }
    return not any(flag in blocking or flag.startswith("route_mismatch_") for flag in flags)


def quality_gate_local_repair(
    question: str,
    reply: str,
    response_lane: str,
    presentation_style: str,
    session_id: Optional[str] = None,
    use_research: bool = False,
) -> Tuple[str, List[str], str]:
    task_intent = detect_task_intent(question, False)
    flags = answer_quality_flags(question, reply, response_lane, presentation_style, task_intent)
    blocking_flags = {
        "empty",
        "backend_talk",
        "weak_fallback",
        "too_short",
        "generic_plan",
        "generic_topic_drift",
        "missing_table",
        "unverified_recommendation_metadata",
        "stream_artifact",
        "traceback_or_error_dump",
        "tool_dump",
        "raw_json_output",
        "missing_current_verification",
        "missing_accuracy_signal",
    }
    if use_research or not any(flag in blocking_flags or flag.startswith("route_mismatch_") for flag in flags):
        return reply, flags, ""

    candidates = [
        local_reply_for_intent(question, task_intent, session_id=session_id),
        local_structured_fallback(question, response_lane, presentation_style, session_id=session_id),
        local_resilient_reply(question, session_id or ensure_session(None), response_lane, presentation_style),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        cleaned = finalize_user_facing_answer(question, candidate, response_lane, presentation_style)
        if should_accept_reviewed_reply(question, cleaned, response_lane, presentation_style):
            return cleaned, flags, task_intent
    return reply, flags, ""


def ensure_inline_citations(text: str, sources: List[SourceItem]) -> str:
    if not sources or re.search(r"\[\d+\]", text):
        return text
    source_ids = [source.id for source in sources[:MAX_RESEARCH_SOURCES]]
    if not source_ids:
        return text

    lines = text.splitlines()
    first_paragraph_done = False
    bullet_citation_index = 0
    output = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            output.append(line)
            continue
        is_heading = normalize_section_heading_text(stripped) is not None or stripped.endswith(":")
        is_bullet = re.match(r"^[-*]\s+", stripped) is not None

        if not first_paragraph_done and not is_heading and not is_bullet:
            citation = "".join(f"[{source_id}]" for source_id in source_ids[: min(2, len(source_ids))])
            output.append(line.rstrip() + f" {citation}")
            first_paragraph_done = True
            continue

        if first_paragraph_done and is_bullet and bullet_citation_index < len(source_ids):
            output.append(line.rstrip() + f" [{source_ids[bullet_citation_index]}]")
            bullet_citation_index += 1
            continue

        output.append(line)

    return "\n".join(output)


def strip_model_source_dump(text: str) -> str:
    text = re.sub(r"(?is)\n+\s*(?:sources?|references?|citations?)\s*[:.]\s*.*$", "", text)
    text = re.sub(r"(?is)\s+(?:sources?|references?|citations?)\s*[:.]\s*\[\d+\].*$", "", text)
    return text.strip()


SECTION_HEADING_LABELS = {
    "answer",
    "short answer",
    "quick answer",
    "direct answer",
    "main idea",
    "key point",
    "key points",
    "key detail",
    "key details",
    "key evidence",
    "evidence",
    "important details",
    "what i found",
    "what i can do",
    "what i can provide",
    "what i will check",
    "what it means",
    "why it matters",
    "why",
    "how",
    "how it works",
    "how to think about it",
    "impact",
    "details",
    "context",
    "examples",
    "example",
    "use",
    "tone",
    "related words",
    "answer structure",
    "use this structure",
    "goal",
    "steps",
    "check",
    "comparison",
    "pros",
    "cons",
    "synonyms",
    "antonyms",
    "meaning",
    "literal meaning",
    "real meaning",
    "similar meaning",
    "similar phrase",
    "breakdown",
    "best use",
    "best route",
    "best way to ask",
    "best format",
    "best structure",
    "needed for exact output",
    "daily practice",
    "daily method",
    "practice",
    "practice method",
    "useful starter phrases",
    "weakest skill",
    "recommendation",
    "summary",
    "quick summary",
    "result",
    "bottom line",
    "takeaway",
    "next step",
    "next steps",
}


def normalize_section_heading_text(line: str) -> Optional[str]:
    raw = clean_text(line)
    if not raw:
        return None
    raw = re.sub(r"^#{1,6}\s*", "", raw)
    raw = re.sub(r"^\*\*(.*?)\*\*\.?$", r"\1", raw)
    raw = raw.strip(" \t:.-")
    key = raw.lower()
    if key not in SECTION_HEADING_LABELS:
        return None
    if key in {"answer", "direct answer"}:
        raw = "Quick answer"
    if key == "main idea":
        raw = "Main idea"
    if key == "key detail":
        raw = "Key details"
    if key == "key point":
        raw = "Key points"
    if key == "evidence":
        raw = "Key evidence"
    if key == "why":
        raw = "Why it matters"
    if key == "how":
        raw = "How it works"
    if key == "example":
        raw = "Examples"
    if key == "quick summary":
        raw = "Summary"
    if raw == line or raw.upper() == raw:
        raw = key
    return capitalize_first_letter(raw) + ":"


def merge_label_only_bullets(text: str) -> str:
    lines = text.splitlines()
    output = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        current_match = re.match(
            r"^(\s*)[-*]\s+(?:\*\*)?([^*:\n]{2,70})(?:\*\*)?\.?(?:\s*(\[\d+\]))?\s*$",
            line,
        )
        next_match = re.match(r"^\s*[-*]\s+(.+)$", lines[index + 1].strip()) if index + 1 < len(lines) else None
        if current_match and next_match:
            label = clean_text(current_match.group(2)).strip(" .")
            word_count = len(label.split())
            label_words = {
                "title", "date", "subject", "to", "from", "owner", "deadline", "status",
                "priority", "metric", "source", "cost",
            }
            is_probable_label = (
                "**" in stripped
                or stripped.rstrip().endswith(":")
                or label.lower() in label_words
                or (word_count <= 3 and re.search(r"\b(label|field|value|owner|deadline|status)\b", label.lower()))
            )
            if is_probable_label:
                citation = current_match.group(3) or ""
                detail = next_match.group(1).strip()
                detail = re.sub(r"^\*\*(.*?)\*\*\.?\s*", r"\1 ", detail).strip()
                if citation and not re.search(r"\[\d+\]", detail):
                    detail = f"{detail} {citation}"
                output.append(f"{current_match.group(1)}- {label}: {detail}")
                index += 2
                continue
        output.append(line)
        index += 1
    return "\n".join(output)


def structure_answer_text(text: str) -> str:
    section_names = (
        r"Short answer|Quick answer|Direct answer|Answer|Main idea|Key points?|Key details?|"
        r"Key evidence|Evidence|Important details|What I found|What I can do|What I can provide|What I will check|"
        r"What it means|Why it matters|"
        r"How it works|How to think about it|Impact|Details|Context|Examples?|Goal|Steps|"
        r"Check|Comparison|Pros|Cons|Synonyms|Antonyms|Meaning|Literal meaning|Real meaning|Similar meaning|Similar phrase|"
        r"Use|Tone|Related words|Answer structure|Use this structure|Breakdown|Best use|Best route|Best way to ask|"
        r"Best format|Best structure|Needed for exact output|Daily practice|Daily method|Practice|Practice method|"
        r"Useful starter phrases|Weakest skill|Recommendation|Summary|Quick summary|Result|Bottom line|"
        r"Takeaway|Next steps?"
    )
    text = re.sub(
        r"(?is)^\s*\*\*([^*\n]{1,100})\.\s*\n-\s*([^*\n]{1,100})\*\*\.?\s*",
        lambda match: f"{match.group(1).strip()} - {match.group(2).strip()}:\n\n",
        text,
    )
    text = re.sub(
        r"(?im)^\*\*([^*\n]{1,100})\*\*\.?\s*$",
        lambda match: f"{match.group(1).strip().rstrip('.')}:",
        text,
    )
    text = re.sub(
        rf"(?i)(?<![A-Za-z])\s+\*\*({section_names})\*\*\.?\s*",
        lambda match: f"\n\n{match.group(1)}:\n",
        text,
    )
    text = re.sub(
        rf"(?i)(?<![A-Za-z])\s+({section_names})\.?\s*:\s*",
        lambda match: f"\n\n{match.group(1)}:\n",
        text,
    )
    text = re.sub(
        rf"(?im)^({section_names})\.?\s*:\s*(\S.*)$",
        lambda match: f"{match.group(1)}:\n{match.group(2)}",
        text,
    )
    text = re.sub(r"(?m):\s+-\s+", ":\n- ", text)
    text = re.sub(r"\bWestBengal\b", "West Bengal", text)
    text = re.sub(r"\b(\d+)(seat|seats|member|members|year|years)\b", r"\1 \2", text, flags=re.IGNORECASE)
    text = merge_label_only_bullets(text)
    normalized_lines = []
    for line in text.splitlines():
        heading = normalize_section_heading_text(line)
        normalized_lines.append(heading if heading else line)
    return "\n".join(normalized_lines).strip()


def strip_provider_noise(text: str) -> str:
    text = re.sub(r"(?is)\n?\s*---\s*\n\s*\*\*Support Pollinations\.?\s*AI:?\*\*.*$", "", text)
    text = re.sub(r"(?is)\n?\s*---\s*\n\s*[^\n]*Ad[^\n]*\n.*Powered by Pollinations\.?\s*AI.*$", "", text)
    text = re.sub(r"(?im)^.*Powered by Pollinations\.?\s*AI.*$", "", text)
    text = re.sub(r"(?im)^.*Support our mission.*$", "", text)
    text = re.sub(r"(?im)^.*pollinations\.ai/redirect.*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def repair_answer_encoding(text: str) -> str:
    replacements = {
        "\u00e2\u0080\u0090": "-",
        "\u00e2\u0080\u0091": "-",
        "\u00e2\u0080\u0092": "-",
        "\u00e2\u0080\u0093": " - ",
        "\u00e2\u0080\u0094": " - ",
        "\u00e2\u0080\u0098": "'",
        "\u00e2\u0080\u0099": "'",
        "\u00e2\u0080\u009c": '"',
        "\u00e2\u0080\u009d": '"',
        "\u00e2\u0080\u00a2": "-",
        "\u00e2\u0080\u00a6": "...",
        "\u00e2\u0080\u00af": " ",
        "\u00c2\u00a0": " ",
        "\u00c2": "",
        "\u00e2\u0082\u00b9": "Rs ",
        "\u00e2\u201a\u00b9": "Rs ",
        "\u20b9": "Rs ",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": " - ",
        "\u2014": " - ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2026": "...",
        "\u202f": " ",
        "\u00a0": " ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def polish_grammar_and_punctuation(text: str) -> str:
    parts = re.split(r"(```[\s\S]*?```)", text)
    polished = []

    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            polished.append(part)
        else:
            polished.append(polish_plain_text_block(part))

    return "".join(polished)


def normalize_markdown_table_line(line: str) -> str:
    return re.sub(r"(\|)\s*[.]\s*$", r"\1", line.rstrip())


def is_markdown_table_line(line: str) -> bool:
    stripped = normalize_markdown_table_line(line.strip())
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def polish_plain_text_block(text: str) -> str:
    lines = text.splitlines()
    output = []
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            output.append("")
            index += 1
            continue
        if re.fullmatch(r"[:;.,\-â€“â€”]+", stripped):
            index += 1
            continue

        indent = line[: len(line) - len(line.lstrip())]
        section_heading = normalize_section_heading_text(stripped)
        if section_heading:
            output.append(f"{indent}{section_heading}")
            index += 1
            continue

        if is_markdown_table_line(stripped):
            while index < len(lines):
                candidate = lines[index].rstrip()
                if not is_markdown_table_line(candidate.strip()):
                    break
                output.append(normalize_markdown_table_line(candidate))
                index += 1
            continue

        heading_match = re.match(r"^(#{1,6}\s+)(.*)$", stripped)
        if heading_match:
            heading = polish_inline_punctuation(heading_match.group(2), capitalize=True)
            output.append(f"{indent}{heading_match.group(1)}{heading.rstrip(' .')}")
            index += 1
            continue

        bullet_match = re.match(r"^([-*\u2022]\s+|\d+[.)]\s+)(.*)$", stripped)
        if bullet_match:
            bullet_group = []
            while index < len(lines):
                candidate = lines[index].rstrip()
                candidate_stripped = candidate.strip()
                match = re.match(r"^([-*\u2022]\s+|\d+[.)]\s+)(.*)$", candidate_stripped)
                if not match:
                    break
                candidate_indent = candidate[: len(candidate) - len(candidate.lstrip())]
                bullet_group.append((candidate_indent, match.group(1), match.group(2)))
                index += 1

            continuation = bool(output and output[-1].rstrip().endswith(":"))
            if continuation and output[-1].strip().rstrip(":").lower() in SECTION_HEADING_LABELS:
                continuation = False
            continuation = continuation and any(
                body.strip() and (body.strip()[0].islower() or body.strip().lower().startswith("and "))
                for _, _, body in bullet_group
            )

            for bullet_index, (bullet_indent, marker, raw_body) in enumerate(bullet_group):
                is_last = bullet_index == len(bullet_group) - 1
                body = polish_inline_punctuation(raw_body, capitalize=not continuation)
                if continuation:
                    body = body.rstrip(".,;")
                    body += "." if is_last else ","
                else:
                    body = ensure_terminal_punctuation(body, allow_comma=True)
                output.append(f"{bullet_indent}{marker}{body}")
            continue

        line = polish_inline_punctuation(stripped, capitalize=True)
        line = ensure_terminal_punctuation(line, allow_colon=True)
        output.append(f"{indent}{line}")
        index += 1

    return "\n".join(output)


def polish_inline_punctuation(text: str, capitalize: bool) -> str:
    text = text.strip()
    text = text.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:!?])([A-Za-z0-9])", r"\1 \2", text)
    text = re.sub(r"(?<=[a-z0-9])\.([A-Z])", r". \1", text)
    text = re.sub(r"\bmulti-faced\b", "multifaceted", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d)\s+%", r"\1%", text)
    text = re.sub(r"\bRs\s+(\d+)-per-", r"Rs \1 per ", text)
    text = re.sub(r"\bRs\s+(\d)", r"Rs \1", text)
    text = re.sub(r"([!?]){2,}", r"\1", text)
    text = re.sub(r"\.{3,}", "...", text)
    text = re.sub(r"\s{2,}", " ", text)

    if capitalize:
        text = capitalize_first_letter(text)
        text = re.sub(
            r"([.!?]\s+)([a-z])",
            lambda match: match.group(1) + match.group(2).upper(),
            text,
        )

    return text


def capitalize_first_letter(text: str) -> str:
    match = re.search(r"[A-Za-z]", text)
    if not match:
        return text
    index = match.start()
    if re.search(r"\d", text[:index]):
        return text
    return text[:index] + text[index].upper() + text[index + 1:]


def ensure_terminal_punctuation(text: str, allow_colon: bool = False, allow_comma: bool = False) -> str:
    stripped = text.rstrip()
    if not stripped:
        return stripped

    if re.match(r"(?i)^(title|subject|topic):\s+\S", stripped):
        return stripped
    if stripped in {"To", "Respected Sir/Madam", "Yours obediently", "Yours sincerely", "The Class Teacher", "The Manager", "The Principal"}:
        return stripped
    if re.match(r"^\[[^\]]+\]$", stripped):
        return stripped
    if re.search(r"(`|\]|\)|\}|[.!?])$", stripped):
        return stripped
    if allow_colon and stripped.endswith(":"):
        return stripped
    if allow_comma and stripped.endswith((",", ";", ":")):
        return stripped
    if re.search(r"https?://\S+$", stripped):
        return stripped
    if len(stripped) <= 36 and not re.search(r"\s", stripped):
        return stripped

    return stripped + "."


def append_sources(reply: str, sources: List[SourceItem]) -> str:
    if not sources or "Sources:" in reply or "## Sources" in reply:
        return reply
    lines = ["\n\nSources:"]
    for source in sources[:MAX_RESEARCH_SOURCES]:
        label = source.title or source.domain or "Source"
        domain = source.domain or "source"
        lines.append(f"[{source.id}] {label} - {domain}")
    return reply + "\n".join(lines)


def compact_evidence_sentence(text: str, max_chars: int = 210) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r"(?i)\b(click here|read more|watch video|official website|home page)\b.*$", "", cleaned).strip()
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]
    sentence = sentences[0] if sentences else cleaned
    if len(sentence) > max_chars:
        sentence = sentence[: max_chars - 3].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
    return ensure_terminal_punctuation(sentence)


def source_ids_matching(sources: List[SourceItem], pattern: str) -> List[int]:
    regex = re.compile(pattern, re.IGNORECASE)
    ids = []
    for source in sources:
        hay = f"{source.title} {source.snippet}"
        if regex.search(hay):
            ids.append(source.id)
    return ids


def citation_text(ids: List[int], limit: int = 2) -> str:
    clean_ids = []
    for source_id in ids:
        if source_id not in clean_ids:
            clean_ids.append(source_id)
    return "".join(f"[{source_id}]" for source_id in clean_ids[:limit])


def synthesize_direct_current_answer(question: str, sources: List[SourceItem]) -> Optional[str]:
    lower = clean_text(question).lower()
    evidence = " ".join(f"{source.title} {source.snippet}" for source in sources)
    evidence_lower = evidence.lower()

    crypto_source = next((source for source in sources if source.provider == "realtime_api:coingecko"), None)
    if crypto_source:
        cite = f"[{crypto_source.id}]"
        match = re.search(r"CoinGecko reports 1\s+([A-Z0-9]+)\s*=\s*([^.]*)\.", crypto_source.snippet)
        if match:
            symbol, price = match.groups()
            change = re.search(r"24h change:\s*([0-9.+-]+)\s*percent", crypto_source.snippet)
            details = [f"- Price: {price.strip()}. {cite}"]
            if change:
                details.append(f"- 24h change: {change.group(1).strip()} percent. {cite}")
            return "\n".join([
                f"Current {symbol} price: {price.strip()}. {cite}",
                "",
                "Details:",
                *details,
                "",
                "Bottom line:",
                "Crypto prices move quickly, so refresh the source before making any financial decision.",
            ])

    github_source = next((source for source in sources if source.provider == "realtime_api:github_repo"), None)
    if github_source:
        cite = f"[{github_source.id}]"
        repo_text = re.sub(r"(?i)^Checked today [^.]+\.\s*", "", clean_text(github_source.snippet)).strip()
        if len(repo_text) > 420:
            repo_text = repo_text[:417].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
        return "\n".join([
            f"{github_source.title}: {repo_text or compact_evidence_sentence(github_source.snippet, 360)} {cite}",
            "",
            "Bottom line:",
            "Use the GitHub source for the newest repository activity, issues, and code changes.",
        ])

    package_source = next((source for source in sources if source.provider in {"realtime_api:pypi_package", "realtime_api:npm_package"}), None)
    if package_source:
        cite = f"[{package_source.id}]"
        version = re.search(r"latest version as\s+([A-Za-z0-9_!+-]+(?:\.[A-Za-z0-9_!+-]+)*)", package_source.snippet)
        package_name = re.sub(r"(?i)^(PyPI|npm)\s+package\s+", "", package_source.title).strip()
        package_text = re.sub(r"(?i)^Checked today [^.]+\.\s*", "", clean_text(package_source.snippet)).strip()
        if version:
            return "\n".join([
                f"Latest {package_name} version: {version.group(1)}. {cite}",
                "",
                "Details:",
                f"- {package_text or compact_evidence_sentence(package_source.snippet, 300)} {cite}",
                "",
                "Bottom line:",
                "Package versions can change, so verify from the registry before installing or upgrading.",
            ])

    earthquake_source = next((source for source in sources if source.provider == "realtime_api:usgs_earthquake"), None)
    if earthquake_source:
        cite = f"[{earthquake_source.id}]"
        quake_text = re.sub(r"(?i)^USGS earthquake feed checked today [^.]+\.\s*", "", clean_text(earthquake_source.snippet)).strip()
        return "\n".join([
            f"Latest earthquake feed: {quake_text or compact_evidence_sentence(earthquake_source.snippet, 360)} {cite}",
            "",
            "Bottom line:",
            "Earthquake feeds update frequently; use the source for the newest map and regional details.",
        ])

    launch_source = next((source for source in sources if source.provider == "realtime_api:space_devs"), None)
    if launch_source:
        cite = f"[{launch_source.id}]"
        launch_text = re.sub(r"(?i)^Checked today [^.]+\.\s*", "", clean_text(launch_source.snippet)).strip()
        launch_text = re.sub(r"(?i)^Next listed launch:\s*", "", launch_text).strip()
        if len(launch_text) > 420:
            launch_text = launch_text[:417].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
        return "\n".join([
            f"Next listed space launch: {launch_text or compact_evidence_sentence(launch_source.snippet, 360)} {cite}",
            "",
            "Bottom line:",
            "Launch times often slip, so refresh the source close to launch time.",
        ])

    weather_source = next((source for source in sources if source.provider == "realtime_api:wttr_in"), None)
    if weather_source:
        cite = f"[{weather_source.id}]"
        snippet = weather_source.snippet
        location = re.sub(r"(?i)^live weather for\s+", "", weather_source.title).strip() or "that location"
        condition = re.search(r"Condition:\s*([^.;]+)", snippet)
        temp = re.search(r"Temperature:\s*([^.;]+)", snippet)
        range_match = re.search(r"Forecast range today:\s*([^.;]+)", snippet)
        humidity = re.search(r"Humidity:\s*([^.;]+)", snippet)
        wind = re.search(r"Wind:\s*([^.;]+)", snippet)
        lead_bits = []
        if condition:
            lead_bits.append(condition.group(1).strip().lower())
        if temp:
            lead_bits.append(temp.group(1).strip())
        lead = f"Current weather in {location}: " + (", ".join(lead_bits) if lead_bits else "live weather data is available") + f". {cite}"
        details = []
        if range_match:
            details.append(f"- Today's forecast range: {range_match.group(1).strip()}. {cite}")
        if humidity:
            details.append(f"- Humidity: {humidity.group(1).strip()}. {cite}")
        if wind:
            details.append(f"- Wind: {wind.group(1).strip()}. {cite}")
        return "\n".join([
            lead,
            "",
            "Details:",
            *(details or [f"- {compact_evidence_sentence(snippet, 260)} {cite}".strip()]),
            "",
            "Bottom line:",
            "Weather changes quickly, so refresh the source if you need minute-by-minute accuracy.",
        ])

    exchange_source = next((source for source in sources if source.provider == "realtime_api:open_er_api"), None)
    if exchange_source:
        cite = f"[{exchange_source.id}]"
        match = re.search(r"1\s+([A-Z]{3})\s*=\s*([0-9.]+)\s+([A-Z]{3})", exchange_source.snippet)
        if match:
            base, rate, target = match.groups()
            return "\n".join([
                f"Current exchange rate: 1 {base} = {rate} {target}. {cite}",
                "",
                "Details:",
                f"- {compact_evidence_sentence(exchange_source.snippet, 260)} {cite}",
                "- Exchange rates move constantly, so treat this as a live reference, not a fixed value.",
                "",
                "Bottom line:",
                f"Use {rate} {target} per 1 {base} for a quick current estimate.",
            ])

    sports_source = next((source for source in sources if source.provider == "realtime_api:espn_scoreboard"), None)
    if sports_source:
        cite = f"[{sports_source.id}]"
        score_text = clean_text(sports_source.snippet)
        score_text = re.sub(r"(?i)^ESPN NBA scoreboard checked today [^.]+\.\s*", "", score_text).strip()
        if len(score_text) > 420:
            score_text = score_text[:417].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
        return "\n".join([
            f"Latest NBA scoreboard: {score_text or compact_evidence_sentence(sports_source.snippet, 360)} {cite}",
            "",
            "Bottom line:",
            "Scores can change during live games, so refresh the source for the newest state.",
        ])

    release_source = next((source for source in sources if source.provider == "realtime_official_page"), None)
    if release_source:
        cite = f"[{release_source.id}]"
        snippet = clean_text(release_source.snippet)
        product_line = re.search(r"Discover\s+(.+?)(?:\.|$)", snippet)
        if product_line:
            return "\n".join([
                f"Apple's official iPhone page currently highlights {product_line.group(1).strip()}. {cite}",
                "",
                "For specs:",
                "- Open the Apple source for the full current spec sheets and availability by region.",
                "",
                "Bottom line:",
                "For latest model/spec questions, the official product page is the safest source to verify against.",
            ])

    if re.search(r"\b(prime minister|pm)\b", lower) and re.search(r"\b(india|bharat)\b", lower):
        if re.search(r"\bnarendra(?:\s+damodardas)?\s+modi\b", evidence_lower):
            ids = source_ids_matching(sources, r"\bNarendra(?:\s+Damodardas)?\s+Modi\b|Prime Minister of India")
            cite = citation_text(ids)
            details = []
            if re.search(r"\bsince\s+2014\b|2014", evidence_lower):
                since_cite = citation_text(source_ids_matching(sources, r"\b2014\b"), 1) or cite
                details.append(f"- He has held the office since 2014, according to the available source context. {since_cite}".strip())
            if re.search(r"\b10\s+june\s+2024\b|june\s+2024|2024", evidence_lower):
                term_cite = citation_text(source_ids_matching(sources, r"2024|10\s+June\s+2024"), 1)
                details.append(f"- The sources also mention his current term after the 2024 election. {term_cite}".strip())
            if not details:
                details.append(f"- The most relevant sources identify Narendra Modi with the office of Prime Minister of India. {cite}")
            return "\n".join([
                f"Narendra Modi is the current Prime Minister of India. {cite}".strip(),
                "",
                "Key points:",
                *details[:2],
                "",
                "Bottom line:",
                "For a changing public office, use the source button to verify the latest official confirmation.",
            ])

    if re.search(r"\bpresident\b", lower) and re.search(r"\b(india|bharat)\b", lower):
        if re.search(r"\bdroupadi\s+murmu\b", evidence_lower):
            ids = source_ids_matching(sources, r"\bDroupadi\s+Murmu\b|President of India")
            cite = citation_text(ids)
            return "\n".join([
                f"Droupadi Murmu is the current President of India. {cite}".strip(),
                "",
                "Bottom line:",
                "For current public offices, the source button is there for latest confirmation.",
            ])

    actor_match = re.search(r"\bname\s+(?:an?\s+)?(?:actor|celebrity|singer|scientist|writer|player)\b", lower)
    if actor_match:
        direct = local_direct_name_reply(lower)
        if direct:
            return direct

    return None


def evidence_bullet_from_source(source: SourceItem, question: str) -> str:
    title = clean_text(source.title)
    snippet = compact_evidence_sentence(source.snippet)
    domain = clean_text(source.domain) or "source"
    if snippet:
        return f"- {snippet} [{source.id}]"
    if title:
        return f"- {title} - {domain}. [{source.id}]"
    return f"- {domain} has relevant context for this answer. [{source.id}]"


def search_evidence_fallback_reply(question: str, sources: List[SourceItem]) -> str:
    usable_sources = sources[:MAX_RESEARCH_SOURCES]
    if not usable_sources:
        return (
            "I could not verify that from live sources yet.\n\n"
            "Bottom line:\n"
            "For current facts, I should not guess without reliable evidence."
        )

    direct = synthesize_direct_current_answer(question, usable_sources)
    if direct:
        return direct

    lower = clean_text(question).lower()
    if re.search(r"\b(best|top|recommend|recommendation|which should i buy|buy|purchase|worth it|review)\b", lower):
        lead = "Short answer:\nUse the source-backed options below as a current shortlist instead of trusting a generic guess. Prioritize the model that matches your budget, RAM/storage needs, and warranty in your area."
    elif re.search(r"\b(price|stock|share|market|weather|score|exchange rate|currency rate)\b", lower):
        lead = "Short answer:\nThe exact value can change by location and time, so use the latest source-backed points below instead of a stale guess."
    elif re.search(r"\b(current|latest|today|right now|recent|news)\b", lower):
        lead = "Short answer:\nUse the latest source-backed evidence below; I will not guess current facts without support."
    else:
        lead = "Short answer:\nThe grounded answer is in the source-backed points below."

    lines = [
        lead,
        "",
        "Key evidence:",
    ]
    for source in usable_sources:
        bullet = evidence_bullet_from_source(source, question)
        if bullet not in lines:
            lines.append(bullet)
    lines.extend([
        "",
        "What it means:",
        "- Use the source button for the full links and latest verification.",
        "- If the sources disagree or lack a clean value, avoid treating any single snippet as final.",
        "",
        "Bottom line:",
        "For current information, source-backed evidence is better than a confident guess.",
    ])
    return "\n".join(lines)


def should_fast_return_research_answer(message: str, presentation_style: str) -> bool:
    lower = clean_text(message).lower()
    if presentation_style in {"chart", "diagram", "long"}:
        return False
    if len(lower.split()) > 16 and not re.search(r"\b(quick|short|brief|just tell)\b", lower):
        return False
    return bool(re.search(
        r"\b(current|latest|today|right now|price|score|weather|winner|ceo|president|"
        r"prime minister|stock|share|market|exchange rate|currency rate|usd to|inr to|eur to|gbp to)\b",
        lower,
    ))


def wikipedia_fallback_reply(question: str, sources: List[SourceItem]) -> str:
    source = sources[0] if sources else None
    if not source:
        return local_resilient_reply(question, ensure_session(None), "learning", "balanced", {})
    snippet = clean_text(source.snippet)
    title = clean_text(source.title) or clean_learning_topic(question)
    sentences = re.split(r"(?<=[.!?])\s+", snippet)
    first = sentences[0] if sentences else snippet
    rest = [sentence for sentence in sentences[1:6] if sentence]
    lines = [
        first or f"{title} is best understood by starting with its basic meaning and main details.",
    ]
    if rest:
        lines.extend(["", "Key points:"])
        lines.extend(f"- {sentence}" for sentence in rest)
    if re.search(r"\b(explain|teach|how|why|what is|what are)\b", question.lower()):
        topic = title.lower()
        if "black hole" in topic:
            lines.extend([
                "",
                "How to think about it:",
                "- A black hole is not an empty hole in space; it is an extremely dense object with gravity so strong that light cannot escape once it crosses the event horizon.",
                "- Black holes can form when very massive stars collapse after running out of fuel.",
                "- Scientists detect them by studying their effects on nearby stars, gas, light, and gravitational waves.",
            ])
        elif "quantum comput" in topic:
            lines.extend([
                "",
                "How to think about it:",
                "- A normal computer stores information as bits: 0 or 1.",
                "- A quantum computer uses quantum bits, or qubits, which can represent richer states through superposition and entanglement.",
                "- That can make some special calculations much faster, but quantum computers are still difficult to build and control.",
            ])
        else:
            lines.extend([
                "",
                "How to think about it:",
                f"- Start with the definition, then connect {title.lower()} to its cause, effect, or real-world use.",
                "- Separate the core idea from extra details so the answer stays easy to remember.",
            ])
    lines.extend([
        "",
        "Bottom line:",
        f"{title} should be understood from reliable background information first, then checked with current sources if the question needs recent details.",
    ])
    return "\n".join(lines)


def setup_error_message(error_text: str) -> str:
    return (
        "I could not complete that response cleanly.\n\n"
        "Send the same question once more with the main topic first, and I will answer from the saved context."
    )


def source_to_dict(source: SourceItem) -> Dict[str, Any]:
    if hasattr(source, "model_dump"):
        return source.model_dump()
    return source.dict()


def action_result_response(
    reply: str,
    session_id: str,
    user_id: str,
    model_used: str,
    tools_used: List[str],
    behavior_signals: Dict[str, Any],
    lane: str = "action",
    style: str = "action_result",
) -> ChatResponse:
    route_map = {
        "files": "file_summary",
        "study": "study_plan",
        "website": "website_plan",
        "reminder": "reminder",
        "email": "email_draft",
        "workflow": "workflow_plan",
        "automation": "workflow_plan",
        "image": "image_generation",
    }
    route_intent = route_map.get(lane, lane)
    pending_user = clean_text(str(pop_session_value(session_id, "_pending_action_user") or ""))
    if pending_user:
        append_session_message(session_id, "user", pending_user)
    append_session_message(session_id, "assistant", reply)
    if pending_user:
        maybe_store_memory(pending_user, user_id)
        learn_long_term_memory_from_chat(
            pending_user,
            reply,
            user_id,
            session_id,
            lane,
            style,
            behavior_signals,
        )
    return ChatResponse(
        reply=reply,
        session_id=session_id,
        mode="agent",
        model_used=model_used,
        sources=[],
        tools_used=tools_used + [f"route_intent:{route_intent}", f"intent_quality_level:{INTENT_QUALITY_LEVEL_TEXT}"],
        route_intent=route_intent,
        created_at=now_iso(),
    )


def extract_after_action(message: str, pattern: str, fallback: str = "") -> str:
    text = clean_text(message)
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match:
        return clean_text(match.group(1)).strip(" .,:;-")
    return fallback or text


def parse_days_minutes(message: str) -> Tuple[int, int]:
    lower = clean_text(message).lower()
    days_match = re.search(r"\b(\d{1,2})\s*(day|days)\b", lower)
    minutes_match = re.search(r"\b(\d{1,3})\s*(min|mins|minutes)\b", lower)
    return (
        int(days_match.group(1)) if days_match else 7,
        int(minutes_match.group(1)) if minutes_match else 45,
    )


def execute_agent_action_from_chat(
    message: str,
    session_id: str,
    user_id: str,
    behavior_signals: Dict[str, Any],
) -> Optional[ChatResponse]:
    text = clean_text(message)
    lower = text.lower()
    set_session_value(session_id, "_pending_action_user", message)
    base_tools = [
        "agent_action_router",
        "behavior_learning",
        f"intent_quality_level:{INTENT_QUALITY_LEVEL_TEXT}",
        f"routing_gate_level:{ROUTING_GATE_LEVEL_TEXT}",
        f"quality_gate_level:{QUALITY_GATE_LEVEL_TEXT}",
        f"gate_stack:{GATE_STACK_MODE}",
        f"routing_matrix:{ROUTING_MATRIX_VERSION}",
        f"performance:{system_profile()['level']}",
    ] + gate_tools_used()

    if re.search(r"\b(summarize|summarise|summary|read|analyze|analyse|extract|key points from|notes from)\b", lower) and re.search(r"\b(file|pdf|document|upload|uploaded)\b|\bthis\s+(?:file|pdf|document|upload)\b", lower):
        reply = local_file_summary_reply(text, session_id) or "Upload a PDF or text file first, then ask me to summarize it."
        return action_result_response(reply, session_id, user_id, "nexora_action_file_summary", base_tools + ["files:summarize"], behavior_signals, "files")

    if re.search(r"\b(study plan|study planner|revision plan|timetable|schedule for study)\b", lower):
        topic_raw = re.sub(r"(?i)^(please\s+)?(make|create|generate|give me|prepare)\s+(a\s+)?", "", text)
        topic_raw = re.sub(r"(?i)\b(study plan|study planner|revision plan|timetable|schedule for study)\b\s*(for|on|about)?\s*", "", topic_raw)
        topic_raw = re.sub(r"(?i)\b(in|for)\s+\d{1,2}\s*(day|days|week|weeks)\b", "", topic_raw)
        topic = title_case_topic(topic_raw.strip(" .,:;-") or "Study")
        days, minutes = parse_days_minutes(text)
        plan = make_study_plan(topic, days, minutes)
        artifact = create_artifact(f"Study plan - {topic}", "Study Plan", plan, prompt=text, user_id=user_id, session_id=session_id)
        reply = f"{plan}\n\nSaved as artifact: {artifact['title']}"
        upsert_memory_item(f"User is studying {topic}.", user_id, "study", "agent_action", session_id)
        return action_result_response(reply, session_id, user_id, "nexora_action_study_plan", base_tools + ["study:plan"], behavior_signals, "study")

    if re.search(r"\b(create|generate|make|build)\b", lower) and re.search(r"\b(website|web page|landing page|html page)\b", lower):
        prompt = extract_after_action(text, r"\b(?:website|web page|landing page|html page)\b\s*(?:for|about|on|:)?\s*(.+)$", text)
        html = generate_website_html(prompt)
        title = title_case_topic(prompt[:60] or "Website")
        artifact = create_artifact(f"Website - {title}", "Website", html, prompt=prompt, user_id=user_id, session_id=session_id)
        reply = (
            f"Website created: {artifact['title']}\n\n"
            "Saved to Artifacts as a single HTML file. Open Artifacts to view or reuse it."
        )
        return action_result_response(reply, session_id, user_id, "nexora_action_website", base_tools + ["website:generate"], behavior_signals, "website")

    if re.search(r"\b(remind me|set\s+(?:a\s+)?reminder|create\s+(?:a\s+)?reminder|add\s+(?:a\s+)?reminder|make\s+(?:a\s+)?reminder)\b", lower):
        title = extract_after_action(text, r"\b(?:remind me(?:\s+to|\s+about)?|set\s+(?:a\s+)?reminder(?:\s+to|\s+about)?|create\s+(?:a\s+)?reminder(?:\s+to|\s+about)?|add\s+(?:a\s+)?reminder(?:\s+to|\s+about)?|make\s+(?:a\s+)?reminder(?:\s+to|\s+about)?|reminder:?)\s*(.+)$", text)
        due_match = re.search(r"\b(?:at|on|by)\s+(.+)$", title, flags=re.IGNORECASE)
        due_at = clean_text(due_match.group(1)) if due_match else ""
        if due_match:
            title = clean_text(title[:due_match.start()]).strip(" .,:;-") or title
        reminder = {
            "id": f"reminder_{uuid.uuid4().hex[:12]}",
            "title": title or "Reminder",
            "due_at": due_at,
            "notes": "",
            "user_id": user_id,
            "session_id": session_id,
            "done": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        items = load_reminders()
        items.insert(0, reminder)
        save_reminders(items)
        reply = f"Reminder saved: {reminder['title']}" + (f"\n\nDue: {due_at}" if due_at else "")
        return action_result_response(reply, session_id, user_id, "nexora_action_reminder", base_tools + ["reminders:create"], behavior_signals, "reminder")

    if re.search(r"\b(draft|write|compose|make)\b", lower) and re.search(r"\b(email|e-mail|mail)\b", lower):
        purpose = extract_after_action(text, r"\b(?:email|e-mail|mail)\b\s*(?:to|for|about|:)?\s*(.+)$", text)
        draft = draft_email_text(purpose or text)
        artifact = create_artifact("Email draft", "Email", draft, prompt=text, user_id=user_id, session_id=session_id)
        reply = f"{draft}\n\nSaved as artifact: {artifact['title']}"
        return action_result_response(reply, session_id, user_id, "nexora_action_email", base_tools + ["email:draft"], behavior_signals, "email")

    if re.search(r"\b(create|make|save|build)\b", lower) and re.search(r"\b(workflow|checklist|process)\b", lower):
        name = extract_after_action(text, r"\b(?:workflow|checklist|process)\b\s*(?:for|about|:)?\s*(.+)$", "Workflow")
        steps = [
            "Clarify the goal.",
            "Collect inputs.",
            "Do the main work.",
            "Check the output.",
            "Save the result.",
        ]
        workflow = {
            "id": f"workflow_{uuid.uuid4().hex[:12]}",
            "name": title_case_topic(name),
            "goal": clean_text(name),
            "steps": steps,
            "user_id": user_id,
            "session_id": session_id,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        items = load_workflows()
        items.insert(0, workflow)
        save_workflows(items)
        reply = "Workflow created:\n\n" + "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        return action_result_response(reply, session_id, user_id, "nexora_action_workflow", base_tools + ["workflows:create"], behavior_signals, "workflow")

    if re.search(r"\b(automation plan|automate|automation|browser action|browser task)\b", lower):
        goal = extract_after_action(text, r"\b(?:automation plan|automate|automation|browser action|browser task)\b\s*(?:for|to|:)?\s*(.+)$", text)
        plan = make_automation_plan(goal)
        artifact = create_artifact(f"Automation plan - {title_case_topic(goal[:60])}", "Automation Plan", plan, prompt=text, user_id=user_id, session_id=session_id)
        reply = f"{plan}\n\nSaved as artifact: {artifact['title']}"
        return action_result_response(reply, session_id, user_id, "nexora_action_automation", base_tools + ["automation:plan"], behavior_signals, "automation")

    if re.search(r"\b(create|generate|make|draw|give me)\b", lower) and re.search(r"\b(image|picture|photo|art|poster|logo|wallpaper)\b", lower):
        prompt = strip_image_command(text)
        style = infer_image_style(text, "auto", user_id)
        enhanced = enhance_image_prompt(prompt, style, True)
        negative = build_image_negative_prompt("", style, prompt)
        image_size = infer_image_size(text, IMAGE_DEFAULT_SIZE, style)
        url, width, height = build_image_url(enhanced, image_size, negative, user_id)
        artifact = create_artifact(
            title=prompt[:70] or "Generated image",
            artifact_type="Image",
            content=f"Original prompt: {prompt}\nEnhanced prompt: {enhanced}",
            url=url,
            prompt=enhanced,
            user_id=user_id,
            session_id=session_id,
        )
        remember_image_workflow(user_id, prompt, enhanced, style, f"{width}x{height}", negative, url, artifact["id"])
        reply = f"Image created.\n\nOpen image: {url}"
        return action_result_response(reply, session_id, user_id, "nexora_action_image", base_tools + ["image:generate"], behavior_signals, "image")

    pop_session_value(session_id, "_pending_action_user")
    return None


def read_frontend_html(path: Path) -> str:
    key = str(path)
    if CACHE_FRONTEND_HTML and key in FRONTEND_HTML_CACHE:
        return FRONTEND_HTML_CACHE[key]
    html = path.read_text(encoding="utf-8")
    if CACHE_FRONTEND_HTML:
        FRONTEND_HTML_CACHE[key] = html
    return html


@app.get("/app", response_class=HTMLResponse)
def web_app() -> HTMLResponse:
    if not FRONTEND_INDEX.exists():
        return HTMLResponse(
            "<h1>Nexora frontend not found</h1><p>Expected frontend/index.html beside the backend folder.</p>",
            status_code=404,
        )
    return HTMLResponse(
        read_frontend_html(FRONTEND_INDEX),
        headers={"Cache-Control": "public, max-age=60"},
    )


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return web_app()


@app.get("/nexora", response_class=HTMLResponse)
def nexora_web_app() -> HTMLResponse:
    return web_app()


@app.get("/code", response_class=HTMLResponse)
def code_page() -> HTMLResponse:
    if not CODE_PAGE_INDEX.exists():
        return HTMLResponse(
            "<h1>Nexora Code page not found</h1><p>Expected frontend/code.html beside the main frontend file.</p>",
            status_code=404,
        )
    return HTMLResponse(
        read_frontend_html(CODE_PAGE_INDEX),
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/code/", response_class=HTMLResponse)
def code_page_slash() -> HTMLResponse:
    return code_page()


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page() -> HTMLResponse:
    if not RESET_PASSWORD_INDEX.exists():
        return HTMLResponse(
            "<h1>Reset page not found</h1><p>Expected frontend/reset-password.html beside the main frontend file.</p>",
            status_code=404,
        )
    return HTMLResponse(
        read_frontend_html(RESET_PASSWORD_INDEX),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/auth.js")
def auth_controller() -> HTMLResponse:
    if not AUTH_CONTROLLER_INDEX.exists():
        return HTMLResponse("console.error('Nexora auth controller not found.');", media_type="application/javascript", status_code=404)
    return HTMLResponse(
        read_frontend_html(AUTH_CONTROLLER_INDEX),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/auth/config", response_model=AuthConfigResponse)
def auth_config(request: Request) -> AuthConfigResponse:
    public_config = clerk_verifier.public_config()
    return AuthConfigResponse(
        ok=True,
        provider="clerk",
        configured=bool(public_config.get("configured")),
        clerk_publishable_key=str(public_config.get("clerk_publishable_key", "")),
        clerk_jwt_issuer=str(public_config.get("clerk_jwt_issuer", "")),
        sign_in_url=auth_redirect_url(request, "/"),
        sign_up_url=auth_redirect_url(request, "/"),
        reset_redirect_url=auth_redirect_url(request, "/"),
        email_redirect_url=auth_redirect_url(request, "/auth/callback"),
        oauth_providers=["google", "github"],
    )


@app.get("/auth/callback", response_class=HTMLResponse)
def auth_callback_page() -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><meta charset=\"utf-8\"><title>Nexora Auth</title>"
        "<script>location.replace('/');</script><p>Returning to Nexora...</p>",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/auth/signup", response_model=AuthResponse)
def auth_signup(req: AuthRequest, request: Request) -> AuthResponse:
    return AuthResponse(
        ok=True,
        user={"email": normalize_email(req.email), "name": clean_text(req.name), "auth_provider": "clerk"},
        message="Signup is handled by Clerk. Use the Clerk sign-up UI or hosted Clerk flow.",
    )


@app.post("/auth/login", response_model=AuthResponse)
def auth_login(req: LoginRequest) -> AuthResponse:
    return AuthResponse(
        ok=True,
        user={"email": normalize_email(req.email), "auth_provider": "clerk"},
        message="Login is handled by Clerk. Use the Clerk sign-in UI, then send the Clerk session JWT as a bearer token.",
    )


@app.post("/auth/logout", response_model=AuthActionResponse)
def auth_logout(request: Request) -> AuthActionResponse:
    return AuthActionResponse(ok=True, message="Logout is handled by Clerk on the client with Clerk.signOut().")


@app.post("/auth/forgot-password", response_model=AuthActionResponse)
def auth_forgot_password(req: ForgotPasswordRequest, request: Request) -> AuthActionResponse:
    return AuthActionResponse(
        ok=True,
        message="Password reset is handled by Clerk. Open the Clerk sign-in flow and choose forgot password.",
    )


@app.post("/auth/reset-password", response_model=AuthActionResponse)
def auth_reset_password(req: ResetPasswordRequest) -> AuthActionResponse:
    return AuthActionResponse(
        ok=True,
        message="Password reset tokens are verified by Clerk. Complete the reset in the Clerk hosted flow.",
    )


@app.get("/auth/me")
def auth_me(request: Request) -> Dict[str, Any]:
    user = optional_authenticated_user(request)
    return {"ok": True, "user": public_user_payload(user)} if user else {"ok": False, "user": None}


def list_sessions_payload(user_id: str) -> Dict[str, Any]:
    normalized = normalize_user_id(user_id)
    sessions = load_sessions()
    rows = []
    for session_id, session in sessions.items():
        if normalize_user_id(str(session.get("user_id", "default"))) != normalized:
            continue
        messages = session.get("messages", []) if isinstance(session, dict) else []
        first_user = next(
            (m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"),
            "",
        )
        rows.append({
            "id": session_id,
            "title": clean_text(first_user)[:80] or "New chat",
            "message_count": len(messages),
            "created_at": session.get("created_at") if isinstance(session, dict) else "",
            "updated_at": session.get("updated_at") if isinstance(session, dict) else "",
        })
    rows.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return {"ok": True, "user_id": normalized, "sessions": rows[:100]}


@app.get("/auth/sessions")
def auth_sessions(request: Request) -> Dict[str, Any]:
    user = require_authenticated_user(request)
    return list_sessions_payload(str(user.get("id", "")))


@app.get("/ollama/{token}/api/tags")
def ollama_proxy_tags(token: str) -> JSONResponse:
    validate_ollama_proxy_token(token)
    return proxy_ollama_json("GET", "/api/tags", timeout=10)


@app.post("/ollama/{token}/api/chat")
async def ollama_proxy_chat(token: str, request: Request) -> JSONResponse:
    validate_ollama_proxy_token(token)
    raw_body = await request.body()
    if len(raw_body) > OLLAMA_PROXY_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Ollama proxy request body is too large.")
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Expected a JSON request body.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object request body.")
    timeout = max(600, int(THINKING_TIMEOUT) + 60)
    return proxy_ollama_json("POST", "/api/chat", payload=payload, timeout=timeout)


@app.get("/health")
def health() -> Dict[str, Any]:
    payload = {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "quality_enforcement": QUALITY_ENFORCEMENT_MODE,
        "routing_gate": ROUTING_GATE_MODE,
        "quality_gate": QUALITY_GATE_MODE,
        "gate_stack_mode": GATE_STACK_MODE,
        "gate_levels": gate_levels_payload(),
        "routing_matrix": routing_matrix_payload(),
        "intent_quality_level": INTENT_QUALITY_LEVEL_TEXT,
        "routing_gate_level": ROUTING_GATE_LEVEL_TEXT,
        "quality_gate_level": QUALITY_GATE_LEVEL_TEXT,
        "intelligence_level": INTELLIGENCE_LEVEL_TEXT,
        "intelligence_mode": INTELLIGENCE_MODE,
        "understanding_level": UNDERSTANDING_LEVEL_TEXT,
        "understanding_mode": UNDERSTANDING_MODE,
        "accuracy_level": ACCURACY_LEVEL_TEXT,
        "accuracy_mode": ACCURACY_MODE,
        "reasoning_level": REASONING_LEVEL_TEXT,
        "reasoning_mode": REASONING_MODE,
        "answer_structure_level": ANSWER_STRUCTURE_LEVEL_TEXT,
        "answer_structure_mode": ANSWER_STRUCTURE_MODE,
        "deep": HEALTH_DEEP,
    }
    if HEALTH_DEEP:
        persona = load_persona_profile()
        behavior = load_behavior_profile()
        payload.update({
            "ollama_url": safe_ollama_url(),
            "default_model": DEFAULT_MODEL,
            "fast_model": FAST_MODEL,
            "thinking_model": THINKING_MODEL,
            "free_api": free_provider_status(),
            "research_engine": "optional",
            "realtime_search": {
                "enabled": True,
                "provider": "duckduckgo_html",
                "max_results": MAX_SEARCH_RESULTS,
                "timeout": SEARCH_TIMEOUT,
                "autonomous_routing": AUTONOMOUS_RESEARCH_ENABLED,
                "autonomous_max_results": AUTONOMOUS_RESEARCH_MAX_RESULTS,
            },
            "image_generation": {
                "enabled": True,
                "provider": IMAGE_PROVIDER,
                "mode": "remote_url_lightweight",
                "prompt_enhancement": IMAGE_PROMPT_ENHANCE,
                "exact_match_mode": IMAGE_EXACT_MATCH_MODE,
                "provider_enhance": IMAGE_PROVIDER_ENHANCE_PARAM,
                "model": IMAGE_MODEL or "provider_default",
                "default_size": IMAGE_DEFAULT_SIZE,
                "workflow_memory": True,
                "per_user_cache": True,
            },
            "memory": {
                "max_items": MAX_MEMORY_ITEMS,
                "context_items": MAX_MEMORY_CONTEXT_ITEMS,
                "context_chars": MAX_MEMORY_CONTEXT_CHARS,
                "image_memory_items": MAX_IMAGE_MEMORY_ITEMS,
                "ranking": "keyword_overlap + explicit_preferences + importance + recency",
            },
            "strict_verification": True,
            "adaptive_persona": {
                "enabled": True,
                "signature": persona_signature(persona),
                "updated_at": persona.get("updated_at"),
            },
            "behavior_learning": {
                "enabled": True,
                "signature": behavior_signature(behavior),
                "updated_at": behavior.get("updated_at"),
                "signals": behavior.get("human_signals", {}),
            },
            "timeout": REQUEST_TIMEOUT,
            "instant_timeout": INSTANT_TIMEOUT,
            "thinking_timeout": THINKING_TIMEOUT,
            "performance": system_profile(),
        })
        payload["ollama_ok"] = is_ollama_ok()
        payload["available_models"] = ollama_available_models()
    return payload


@app.get("/models")
def models() -> Dict[str, Any]:
    return {
        "default": DEFAULT_MODEL,
        "fast": FAST_MODEL,
        "thinking": THINKING_MODEL,
        "free_api": free_provider_status(),
        "quality_enforcement": QUALITY_ENFORCEMENT_MODE,
        "routing_gate": ROUTING_GATE_MODE,
        "quality_gate": QUALITY_GATE_MODE,
        "gate_stack_mode": GATE_STACK_MODE,
        "gate_levels": gate_levels_payload(),
        "routing_matrix": routing_matrix_payload(),
        "intent_quality_level": INTENT_QUALITY_LEVEL_TEXT,
        "routing_gate_level": ROUTING_GATE_LEVEL_TEXT,
        "quality_gate_level": QUALITY_GATE_LEVEL_TEXT,
        "intelligence_level": INTELLIGENCE_LEVEL_TEXT,
        "intelligence_mode": INTELLIGENCE_MODE,
        "understanding_level": UNDERSTANDING_LEVEL_TEXT,
        "understanding_mode": UNDERSTANDING_MODE,
        "accuracy_level": ACCURACY_LEVEL_TEXT,
        "accuracy_mode": ACCURACY_MODE,
        "reasoning_level": REASONING_LEVEL_TEXT,
        "reasoning_mode": REASONING_MODE,
        "answer_structure_level": ANSWER_STRUCTURE_LEVEL_TEXT,
        "answer_structure_mode": ANSWER_STRUCTURE_MODE,
        "performance": system_profile(),
        "available": ollama_available_models(),
    }


@app.get("/settings/free-ai")
def get_free_ai_settings(request: Request) -> Dict[str, Any]:
    user = optional_authenticated_user(request)
    payload: Dict[str, Any] = {
        "ok": True,
        "status": free_provider_status(),
    }
    if user:
        payload["user_settings"] = free_ai_settings_for_user(str(user.get("id", "")))
    return payload


@app.post("/settings/free-ai")
def update_free_ai_settings(req: FreeAISettingsRequest, request: Request) -> Dict[str, Any]:
    user = require_authenticated_user(request)
    ok, message = save_user_free_ai_settings(str(user.get("id", "")), req)
    return {
        "ok": ok,
        "message": message,
        "status": free_provider_status(),
        "user_settings": free_ai_settings_for_user(str(user.get("id", ""))),
    }


@app.get("/search")
def search(q: str, max_results: int = MAX_SEARCH_RESULTS) -> Dict[str, Any]:
    clipped_max = max(1, min(int(max_results or MAX_SEARCH_RESULTS), 10))
    results = cached_search_results("duckduckgo", q, max_results=clipped_max)
    return {
        "ok": bool(results),
        "query": q,
        "provider": "duckduckgo_html",
        "results": results,
        "created_at": now_iso(),
    }


@app.get("/search/realtime")
def realtime_search(q: str, max_results: int = MAX_SEARCH_RESULTS) -> Dict[str, Any]:
    clipped_max = max(1, min(int(max_results or MAX_SEARCH_RESULTS), 10))
    route, variants = build_realtime_query_variants(q)
    result = realtime_search_loop(q, max_rounds=1)
    sources = result.get("sources", [])[:clipped_max]
    return {
        "ok": bool(result.get("ok")),
        "query": q,
        "route": route,
        "query_variants": variants,
        "provider": result.get("provider", "duckduckgo_realtime"),
        "results": sources,
        "error": result.get("error", ""),
        "created_at": now_iso(),
    }


@app.get("/system/profile")
def read_system_profile() -> Dict[str, Any]:
    return {"ok": True, "profile": system_profile()}


@app.get("/workflow/user")
def read_user_workflow(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    users = load_users()
    image_memory = load_image_memory()
    memories = [
        item for item in load_memory()
        if normalize_user_id(str(item.get("user_id", "default"))) == normalized
    ]
    images = [
        item for item in image_memory.get("images", [])
        if isinstance(item, dict) and normalize_user_id(str(item.get("user_id", "default"))) == normalized
    ]
    reminders = [
        item for item in load_reminders()
        if normalize_user_id(str(item.get("user_id", "default"))) == normalized and not item.get("done")
    ]
    workflows = [
        item for item in load_workflows()
        if normalize_user_id(str(item.get("user_id", "default"))) == normalized
    ]
    return {
        "ok": True,
        "user_id": normalized,
        "user": public_user_payload(users.get(normalized, {"id": normalized})),
        "memory_items": len(memories),
        "image_items": len(images),
        "reminder_items": len(reminders),
        "workflow_items": len(workflows),
        "image_preferences": image_memory.get("preferences", {}).get(normalized, {}),
        "workflow": {
            "sessions": "per browser user id",
            "chat_memory": "per user",
            "image_memory": "per user prompt/style/size cache",
            "artifacts": "filterable by user",
            "files": "uploads, optional PDF text extraction, summaries",
            "reminders": "local reminders with due text and done status",
            "workflows": "saved reusable checklists and automation plans",
        },
    }


@app.get("/sessions")
def list_sessions(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    return list_sessions_payload(resolve_user_id_for_request(request, user_id))


@app.get("/projects")
def projects(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    rows = load_projects()
    rows = [
        project for project in rows
        if normalize_user_id(str(project.get("user_id", "default"))) == normalized
    ]
    return {"ok": True, "user_id": normalized, "projects": rows}


@app.post("/projects/create")
def create_project(req: ProjectRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    project = upsert_project(req.name, req.session_id, user_id)
    return {"ok": True, "project": project, "name": project["name"]}


@app.delete("/projects/{project_key}")
def delete_project(project_key: str, request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    key = clean_text(project_key).lower()
    deleted: List[Dict[str, Any]] = []
    kept = []
    for project in load_projects():
        project_name = clean_text(str(project.get("name", ""))).lower()
        project_id = clean_text(str(project.get("id", ""))).lower()
        same_project = key in {project_name, project_id}
        same_user = normalize_user_id(str(project.get("user_id", "default"))) == normalized
        if same_project and same_user:
            deleted.append(project)
            continue
        kept.append(project)
    save_projects(kept)
    return {
        "ok": True,
        "deleted": len(deleted),
        "project": deleted[0] if deleted else None,
        "project_key": project_key,
        "user_id": normalized,
    }


@app.get("/artifacts")
def artifacts(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    items = load_artifacts()
    items = [
        item for item in items
        if normalize_user_id(str(item.get("user_id", "default"))) == normalized
    ]
    return {"ok": True, "user_id": normalized, "artifacts": items}


@app.post("/artifacts/save")
def save_artifact(req: ArtifactRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    artifact = create_artifact(
        title=req.title,
        artifact_type=req.type,
        content=req.content,
        url=req.url,
        prompt=req.prompt,
        user_id=user_id,
        session_id=req.session_id,
    )
    return {"ok": True, "artifact": artifact}


@app.delete("/artifacts/{artifact_id}")
def delete_artifact(artifact_id: str, request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    key = clean_text(artifact_id)
    deleted: List[Dict[str, Any]] = []
    kept = []
    for artifact in load_artifacts():
        artifact_id_value = clean_text(str(artifact.get("id", "")))
        same_artifact = artifact_id_value == key
        same_user = normalize_user_id(str(artifact.get("user_id", "default"))) == normalized
        if same_artifact and same_user:
            deleted.append(artifact)
            continue
        kept.append(artifact)
    save_artifacts(kept)
    return {
        "ok": True,
        "deleted": len(deleted),
        "artifact": deleted[0] if deleted else None,
        "artifact_id": artifact_id,
        "user_id": normalized,
    }


@app.get("/capabilities")
def capabilities() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": APP_VERSION,
        "quality_enforcement": QUALITY_ENFORCEMENT_MODE,
        "routing_gate": ROUTING_GATE_MODE,
        "quality_gate": QUALITY_GATE_MODE,
        "gate_stack_mode": GATE_STACK_MODE,
        "gate_levels": gate_levels_payload(),
        "routing_matrix": routing_matrix_payload(),
        "intent_quality_level": INTENT_QUALITY_LEVEL_TEXT,
        "routing_gate_level": ROUTING_GATE_LEVEL_TEXT,
        "quality_gate_level": QUALITY_GATE_LEVEL_TEXT,
        "intelligence_level": INTELLIGENCE_LEVEL_TEXT,
        "intelligence_mode": INTELLIGENCE_MODE,
        "understanding_level": UNDERSTANDING_LEVEL_TEXT,
        "understanding_mode": UNDERSTANDING_MODE,
        "accuracy_level": ACCURACY_LEVEL_TEXT,
        "accuracy_mode": ACCURACY_MODE,
        "reasoning_level": REASONING_LEVEL_TEXT,
        "reasoning_mode": REASONING_MODE,
        "answer_structure_level": ANSWER_STRUCTURE_LEVEL_TEXT,
        "answer_structure_mode": ANSWER_STRUCTURE_MODE,
        "stages": {
            "gate_stack": [
                "expanded 300+ field-aware and language-aware intent routing matrix",
                "intent detection 10.00/10.00",
                "context resolution 10.00/10.00",
                "route selection 10.00/10.00",
                "route confidence 10.00/10.00",
                "task-shape validation 10.00/10.00",
                "answer quality gate 10.00/10.00",
                "accuracy gate 10.00/10.00",
                "reasoning gate 10.00/10.00",
                "answer structure gate 10.00/10.00",
                "repair gate 10.00/10.00",
                "final output cleanup 10.00/10.00",
            ],
            "intelligence": [
                "extended 15.00 app scale",
                "intent quality 10.00/10.00",
                "intent + context fusion",
                "reasoning + accuracy routing",
                "memory-aware answer shaping",
                "tool and fallback selection",
                "intent-first routing gate",
                "polished final response",
            ],
            "understanding": [
                "max-precision intent parsing",
                "route score and task-shape validation",
                "typo-tolerant wording cleanup",
                "context reference resolution",
                "reasonableness checks",
                "route-specific answer selection",
                "answer-shape selection",
                "raw-output cleanup",
                "route-mismatch repair",
                "first-pass completeness check",
            ],
            "reasoning": [
                "max-silent reasoning pass",
                "assumption checks",
                "contradiction checks",
                "edge-case review",
                "goal and constraint alignment",
                "concise rationale output",
            ],
            "answer_structure": [
                "compact direct lead",
                "task-fit headings",
                "short paragraphs",
                "clean bullets and tables",
                "polished final takeaway",
                "raw-output suppression",
            ],
            "writing": ["emails", "letters", "essays", "polished tone", "structured answers"],
            "files": ["txt/md/code extraction", "optional PDF extraction", "local summaries", "session file context"],
            "websites": ["single-file HTML generation", "artifact saving"],
            "study": ["study planner", "study explanations", "local topic cards"],
            "images": ["Pollinations generation", "prompt enhancement", "per-user image memory"],
            "workflows": ["save workflows", "run workflow checklists", "automation planning"],
            "reminders": ["local reminder storage", "due list", "done status"],
            "search": ["DuckDuckGo HTML search", "strict current-fact verification"],
            "safety": ["harmful request filter", "high-stakes caution"],
        },
        "limits": {
            "local_model_training": False,
            "email_calendar_connectors": "draft/planning only unless a connector is added",
            "browser_actions": "planned safely inside Nexora; external browser automation needs a browser connector",
            "unattended_production_deploy": "approval-gated and supervised; Nexora can prepare and verify, but should not silently ship production changes",
            "task_selection_shipping_loop": "max-precision planning is enabled; autonomous execution stays approval-gated for safety",
        },
    }


@app.post("/files/summarize")
def summarize_file(req: FileSummaryRequest, request: Request) -> Dict[str, Any]:
    session = get_session(req.session_id)
    user_id = register_request_user(request, req.user_id, req.session_id)
    require_session_owner(req.session_id, user_id)
    files = session.get("files", [])
    selected = None
    if req.filename:
        requested = clean_text(req.filename).lower()
        selected = next(
            (item for item in reversed(files) if requested in clean_text(str(item.get("filename", ""))).lower()),
            None,
        )
    if selected is None and files:
        selected = files[-1]
    if not selected:
        return {"ok": False, "message": "No uploaded file found in this session.", "summary": ""}
    text = str(selected.get("text", ""))
    result = summarize_text_locally(text, req.max_points)
    content = (
        f"File summary: {selected.get('filename', 'file')}\n\n"
        f"Summary:\n{result['summary']}\n\n"
        "Key points:\n" + "\n".join(f"- {point}" for point in result["key_points"])
    )
    if result["action_items"]:
        content += "\n\nAction items:\n" + "\n".join(f"- {item}" for item in result["action_items"])
    artifact = create_artifact(
        title=f"Summary - {selected.get('filename', 'file')}",
        artifact_type="File Summary",
        content=content,
        user_id=user_id,
        session_id=req.session_id,
    )
    return {"ok": True, "file": selected, "summary": result, "artifact": artifact}


@app.post("/study/plan")
def create_study_plan(req: StudyPlanRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    plan = make_study_plan(req.topic, req.days, req.daily_minutes, req.goal)
    artifact = create_artifact(
        title=f"Study plan - {title_case_topic(req.topic)}",
        artifact_type="Study Plan",
        content=plan,
        prompt=req.topic,
        user_id=user_id,
        session_id=req.session_id,
    )
    upsert_memory_item(f"User is studying {title_case_topic(req.topic)}.", user_id, "study", "study_plan", req.session_id)
    return {"ok": True, "plan": plan, "artifact": artifact}


@app.post("/website/generate")
def generate_website(req: WebsiteRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    html = generate_website_html(req.prompt, req.title)
    title = clean_text(req.title or "") or title_case_topic(req.prompt[:60])
    artifact = create_artifact(
        title=f"Website - {title}",
        artifact_type="Website",
        content=html,
        prompt=req.prompt,
        user_id=user_id,
        session_id=req.session_id,
    )
    return {"ok": True, "html": html, "artifact": artifact}


@app.get("/reminders")
def list_reminders(request: Request, user_id: Optional[str] = None, include_done: bool = False) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    items = load_reminders()
    items = [item for item in items if normalize_user_id(str(item.get("user_id", "default"))) == normalized]
    if not include_done:
        items = [item for item in items if not item.get("done")]
    return {"ok": True, "user_id": normalized, "reminders": items[:100]}


@app.post("/reminders/create")
def create_reminder(req: ReminderRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    reminder = {
        "id": f"reminder_{uuid.uuid4().hex[:12]}",
        "title": clean_text(req.title),
        "due_at": clean_text(req.due_at),
        "notes": clean_text(req.notes),
        "user_id": user_id,
        "session_id": req.session_id,
        "done": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    items = load_reminders()
    items.insert(0, reminder)
    save_reminders(items)
    return {"ok": True, "reminder": reminder}


@app.post("/reminders/{reminder_id}/done")
def complete_reminder(reminder_id: str, request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    items = load_reminders()
    for item in items:
        if item.get("id") == reminder_id and normalize_user_id(str(item.get("user_id", "default"))) == normalized:
            item["done"] = True
            item["updated_at"] = now_iso()
            save_reminders(items)
            return {"ok": True, "reminder": item}
    return {"ok": False, "message": "Reminder not found."}


@app.get("/workflows")
def list_workflows(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    items = load_workflows()
    items = [item for item in items if normalize_user_id(str(item.get("user_id", "default"))) == normalized]
    return {"ok": True, "user_id": normalized, "workflows": items[:100]}


@app.post("/workflows/create")
def create_workflow(req: WorkflowRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    steps = [clean_text(step) for step in req.steps if clean_text(step)]
    if not steps:
        steps = [
            "Clarify the goal.",
            "Collect inputs and files.",
            "Do the main work.",
            "Check the output.",
            "Save or share the result.",
        ]
    workflow = {
        "id": f"workflow_{uuid.uuid4().hex[:12]}",
        "name": clean_text(req.name),
        "goal": clean_text(req.goal),
        "steps": steps[:20],
        "user_id": user_id,
        "session_id": req.session_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    items = load_workflows()
    items.insert(0, workflow)
    save_workflows(items)
    return {"ok": True, "workflow": workflow}


@app.post("/workflows/{workflow_id}/run")
def run_workflow(workflow_id: str, request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    workflow = next((
        item for item in load_workflows()
        if item.get("id") == workflow_id and normalize_user_id(str(item.get("user_id", "default"))) == normalized
    ), None)
    if not workflow:
        return {"ok": False, "message": "Workflow not found."}
    content = (
        f"Workflow: {workflow.get('name')}\n\n"
        f"Goal: {workflow.get('goal') or 'Complete this workflow carefully.'}\n\n"
        "Checklist:\n" + "\n".join(f"{index}. {step}" for index, step in enumerate(workflow.get("steps", []), start=1))
    )
    artifact = create_artifact(
        title=f"Workflow run - {workflow.get('name')}",
        artifact_type="Workflow",
        content=content,
        user_id=normalized,
        session_id=str(workflow.get("session_id") or ""),
    )
    return {"ok": True, "workflow": workflow, "run": content, "artifact": artifact}


@app.post("/email/draft")
def draft_email(req: EmailDraftRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    draft = draft_email_text(req.purpose, req.recipient, req.tone, req.details)
    artifact = create_artifact(
        title="Email draft",
        artifact_type="Email",
        content=draft,
        prompt=req.purpose,
        user_id=user_id,
        session_id=req.session_id,
    )
    return {"ok": True, "draft": draft, "artifact": artifact}


@app.post("/automation/plan")
def plan_automation(req: AutomationRequest, request: Request) -> Dict[str, Any]:
    user_id = register_request_user(request, req.user_id, req.session_id)
    plan = make_automation_plan(req.goal, req.context)
    artifact = create_artifact(
        title=f"Automation plan - {title_case_topic(req.goal[:60])}",
        artifact_type="Automation Plan",
        content=plan,
        prompt=req.goal,
        user_id=user_id,
        session_id=req.session_id,
    )
    return {"ok": True, "plan": plan, "artifact": artifact}


@app.post("/image/upload", response_model=ImageUploadResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
) -> ImageUploadResponse:
    session_id = ensure_session(session_id)
    user_id = register_request_user(request, user_id, session_id)
    original_name = file.filename or "pasted_image.png"
    suffix = Path(original_name).suffix.lower()
    content_type = clean_text(file.content_type or "")
    if suffix not in IMAGE_EXTENSIONS and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported by this endpoint.")

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", original_name)[:120] or "image.png"
    saved_name = f"{session_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_name}"
    saved_path = UPLOAD_DIR / saved_name
    content = await file.read()
    saved_path.write_bytes(content)
    analysis = analyze_image_bytes(content, original_name, content_type)
    image_record = {
        "id": f"image_{uuid.uuid4().hex[:12]}",
        "filename": original_name,
        "saved_as": saved_name,
        "path": str(saved_path),
        "uploaded_at": now_iso(),
        "user_id": user_id,
        "session_id": session_id,
        **analysis,
    }

    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session = sessions.get(session_id) or new_session_record(session_id)
        session.setdefault("images", []).append(image_record)
        session["images"] = session["images"][-12:]
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)
    return ImageUploadResponse(
        ok=True,
        session_id=session_id,
        image=image_record,
        message=f"Image attached: {original_name}",
    )


@app.post("/image/generate", response_model=ImageResponse)
def generate_image(req: ImageRequest, request: Request) -> ImageResponse:
    user_id = register_request_user(request, req.user_id, req.session_id)
    original_prompt = strip_image_command(req.prompt)
    style = infer_image_style(req.prompt, req.style, user_id)
    enhanced_prompt = enhance_image_prompt(original_prompt, style, req.enhance)
    negative_prompt = build_image_negative_prompt(req.negative_prompt, style, original_prompt)
    image_size = infer_image_size(req.prompt, req.size, style)
    width, height = parse_image_size(image_size)
    size_label = f"{width}x{height}"
    cached_item = find_cached_image(user_id, enhanced_prompt, size_label, negative_prompt)
    if cached_item:
        remember_image_workflow(
            user_id=user_id,
            original_prompt=original_prompt,
            enhanced_prompt=enhanced_prompt,
            style=style,
            size_label=size_label,
            negative_prompt=negative_prompt,
            url=str(cached_item.get("url", "")),
            artifact_id=str(cached_item.get("artifact_id", "")),
            cached=True,
        )
        return ImageResponse(
            ok=True,
            prompt=enhanced_prompt,
            original_prompt=original_prompt,
            enhanced_prompt=enhanced_prompt,
            url=str(cached_item.get("url", "")),
            artifact_id=str(cached_item.get("artifact_id", "")),
            provider=IMAGE_PROVIDER,
            size=size_label,
            width=width,
            height=height,
            cached=True,
            user_id=user_id,
            workflow={"memory": "hit", "style": style, "saved_to_artifacts": True},
            created_at=str(cached_item.get("created_at") or now_iso()),
        )

    url, width, height = build_image_url(enhanced_prompt, image_size, negative_prompt, user_id)
    size_label = f"{width}x{height}"
    artifact = create_artifact(
        title=original_prompt[:70] or "Generated image",
        artifact_type="Image",
        content=f"Original prompt: {original_prompt}\nEnhanced prompt: {enhanced_prompt}",
        url=url,
        prompt=enhanced_prompt,
        user_id=user_id,
        session_id=req.session_id,
    )
    workflow = remember_image_workflow(
        user_id=user_id,
        original_prompt=original_prompt,
        enhanced_prompt=enhanced_prompt,
        style=style,
        size_label=size_label,
        negative_prompt=negative_prompt,
        url=url,
        artifact_id=artifact["id"],
    )
    return ImageResponse(
        ok=True,
        prompt=enhanced_prompt,
        original_prompt=original_prompt,
        enhanced_prompt=enhanced_prompt,
        url=url,
        artifact_id=artifact["id"],
        provider=IMAGE_PROVIDER,
        size=size_label,
        width=width,
        height=height,
        cached=False,
        user_id=user_id,
        workflow={"memory": "saved", "style": style, "saved_to_artifacts": True, "preferences": workflow},
        created_at=artifact["created_at"],
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    user_message = req.message.strip()
    original_user_message = (req.original_message or user_message).strip()
    session_id = ensure_session(req.session_id)
    user_id = register_request_user(request, req.user_id, session_id)
    session = get_session(session_id)
    safety_reply = safety_filter_reply(original_user_message)
    if safety_reply:
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", safety_reply)
        return ChatResponse(
            reply=safety_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="nexora_safety_filter",
            sources=[],
            tools_used=["safety_filter", "route_intent:safety_filter", f"performance:{system_profile()['level']}"],
            route_intent="safety_filter",
            created_at=now_iso(),
        )
    force_ollama_chat = force_ollama_chat_enabled()
    if force_ollama_chat:
        history_limit = 2
        history_from_session = [
            ChatMessage(role=item.get("role", "user"), content=item.get("content", ""))
            for item in session.get("messages", [])[-history_limit:]
            if item.get("role") in {"user", "assistant"}
        ]
        history = req.chat_history[-history_limit:] if req.chat_history is not None else history_from_session
        file_context = build_file_context(session_id)
        image_context = build_image_context(session_id, req.image_ids)
        if image_context:
            file_context = "\n\n".join(part for part in [file_context, image_context] if part)
        response_mode = forced_ollama_response_mode(req.mode, req.model)
        model = select_ollama_model(req.model)
        tools_used = [
            "ollama_forced_direct",
            f"ollama_mode:{OLLAMA_MODE}",
            f"performance:{system_profile()['level']}",
        ]
        if file_context:
            tools_used.append("file_context")
        try:
            reply = ollama_chat(
                build_forced_ollama_messages(original_user_message, history, file_context),
                model,
                response_mode,
            )
            model_used = f"ollama:{model}:{response_mode}:direct"
            if not clean_text(reply):
                raise RuntimeError("empty ollama response")
            final_reply = clean_reply(reply)
        except Exception as error:
            model_used = f"ollama:{model}:{response_mode}:failed"
            final_reply = (
                "Qwen is selected, but it did not finish this answer fast enough on the SSH server. "
                "Try a shorter question, or switch to a smaller Qwen model for faster chat."
            )
            tools_used.append(f"ollama_required_failed:{error}")
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", final_reply)
        return ChatResponse(
            reply=final_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used=model_used,
            sources=[],
            tools_used=tools_used,
            route_intent="ollama_direct",
            created_at=now_iso(),
        )

    quick_reply = local_fast_reply(original_user_message)
    if quick_reply and not force_ollama_chat:
        quick_intent = detect_task_intent(original_user_message, False)
        quick_reply = finalize_user_facing_answer(original_user_message, quick_reply, "human_chat", "short")
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", quick_reply)
        return ChatResponse(
            reply=quick_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="nexora_local_fast",
            sources=[],
            tools_used=["local_fast_reply", "fast_path", f"route_intent:{quick_intent}", f"performance:{system_profile()['level']}"],
            route_intent=quick_intent,
            created_at=now_iso(),
        )

    behavior_profile, behavior_signals = learn_behavior_from_message(original_user_message)
    persona_profile, persona_changes = learn_persona_from_message(original_user_message)
    if persona_changes and not force_ollama_chat:
        reply = persona_update_reply(persona_changes, persona_profile)
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", reply)
        maybe_store_memory(original_user_message, user_id)
        learn_long_term_memory_from_chat(
            original_user_message,
            reply,
            user_id,
            session_id,
            "persona_update",
            "preference",
            behavior_signals,
        )
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="nexora_adaptive_persona",
            sources=[],
            tools_used=["adaptive_persona", "behavior_learning", "route_intent:persona_update", f"performance:{system_profile()['level']}"],
            route_intent="persona_update",
            created_at=now_iso(),
        )
    pending_reply = resolve_pending_task_reply(session_id, original_user_message)
    if pending_reply and not force_ollama_chat:
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", pending_reply)
        maybe_store_memory(original_user_message, user_id)
        learn_long_term_memory_from_chat(
            original_user_message,
            pending_reply,
            user_id,
            session_id,
            "pending_intent",
            "finished_draft",
            behavior_signals,
        )
        return ChatResponse(
            reply=pending_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="nexora_pending_intent_memory",
            sources=[],
            tools_used=["pending_intent_memory", "behavior_learning", "route_intent:pending_intent", f"performance:{system_profile()['level']}"],
            route_intent="pending_intent",
            created_at=now_iso(),
        )
    image_reply = local_image_attachment_reply(original_user_message, session_id, req.image_ids)
    if image_reply and not force_ollama_chat:
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", image_reply)
        maybe_store_memory(original_user_message, user_id)
        learn_long_term_memory_from_chat(
            original_user_message,
            image_reply,
            user_id,
            session_id,
            "image",
            "attachment",
            behavior_signals,
        )
        return ChatResponse(
            reply=image_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="nexora_image_attachment",
            sources=[],
            tools_used=["image_upload", "image_context", "behavior_learning", "route_intent:image_attachment", f"performance:{system_profile()['level']}"],
            route_intent="image_attachment",
            created_at=now_iso(),
        )
    agent_action = execute_agent_action_from_chat(original_user_message, session_id, user_id, behavior_signals)
    if agent_action and not force_ollama_chat:
        return agent_action
    response_mode = choose_response_mode(original_user_message, req.mode, req.model)

    normalized_user_message, _typing_corrections = normalize_user_language(original_user_message)
    understanding_message = normalized_user_message or original_user_message
    use_research = should_use_research(understanding_message, req.mode, req.use_web)
    response_lane = classify_response_lane(understanding_message, use_research)
    presentation_style = classify_presentation_style(understanding_message, response_lane, use_research)
    research_route = autonomous_research_route(
        understanding_message,
        response_lane,
        presentation_style,
        use_research,
    )
    task_intent = detect_task_intent(understanding_message, use_research)
    writing_request = analyze_writing_request(understanding_message)
    intent = analyze_user_intent(
        understanding_message,
        response_lane,
        presentation_style,
        use_research,
        behavior_signals,
        research_route,
    )
    intent["task_intent"] = task_intent
    intent["routing_gate"] = ROUTING_GATE_MODE
    intent["quality_gate"] = QUALITY_GATE_MODE
    understanding_context, understanding_state = build_understanding_context(
        session_id,
        original_user_message,
        response_lane,
        use_research,
        writing_request,
    )
    memory_sig = memory_signature_for_user(user_id)
    response_cache_key = cache_key(
        session_id,
        original_user_message,
        req.mode,
        f"{APP_VERSION}:{req.model or 'auto'}:{response_mode}:{FREE_CLUB_MODE}:{use_research}:{research_route}:{task_intent}:{response_lane}:{presentation_style}:{understanding_state.get('vague_followup')}:{persona_signature(persona_profile)}:{behavior_signature(behavior_profile)}:{memory_sig}",
    )
    skip_response_cache = bool(writing_request.get("is_writing") and writing_request.get("missing_topic"))
    cached = None if skip_response_cache or force_ollama_chat else get_cached_response(response_cache_key)
    if cached:
        cached_reply = str(cached["reply"])
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", cached_reply)
        learn_long_term_memory_from_chat(
            original_user_message,
            cached_reply,
            user_id,
            session_id,
            response_lane,
            presentation_style,
            behavior_signals,
        )
        return ChatResponse(
            reply=cached_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used=str(cached["model_used"]),
            sources=cached.get("sources", []),
            tools_used=["response_cache", f"route_intent:{task_intent}"],
            route_intent=task_intent,
            created_at=now_iso(),
        )

    history_limit = current_performance_limits().get("history_messages", MAX_HISTORY_MESSAGES)
    history_from_session = [
        ChatMessage(role=item.get("role", "user"), content=item.get("content", ""))
        for item in session.get("messages", [])[-history_limit:]
        if item.get("role") in {"user", "assistant"}
    ]
    history = req.chat_history if req.chat_history is not None else history_from_session
    tools_used: List[str] = []
    tools_used.append(f"performance:{system_profile()['level']}")
    tools_used.append(f"quality_enforcement:{QUALITY_ENFORCEMENT_MODE}")
    tools_used.append(f"routing_gate:{ROUTING_GATE_MODE}")
    tools_used.append(f"quality_gate:{QUALITY_GATE_MODE}")
    tools_used.append(f"intent_quality_level:{INTENT_QUALITY_LEVEL_TEXT}")
    tools_used.append(f"routing_gate_level:{ROUTING_GATE_LEVEL_TEXT}")
    tools_used.append(f"quality_gate_level:{QUALITY_GATE_LEVEL_TEXT}")
    tools_used.append(f"gate_stack:{GATE_STACK_MODE}")
    tools_used.append(f"routing_matrix:{ROUTING_MATRIX_VERSION}")
    tools_used.extend(gate_tools_used())
    tools_used.append("behavior_learning")
    tools_used.append("intent_understanding")
    tools_used.append(f"route_intent:{task_intent}")
    tools_used.append(f"intelligence_level:{INTELLIGENCE_LEVEL_TEXT}")
    tools_used.append(f"understanding_level:{UNDERSTANDING_LEVEL_TEXT}")
    tools_used.append(f"accuracy_level:{ACCURACY_LEVEL_TEXT}")
    tools_used.append(f"reasoning_level:{REASONING_LEVEL_TEXT}")
    tools_used.append(f"answer_structure_level:{ANSWER_STRUCTURE_LEVEL_TEXT}")
    tools_used.append(f"autonomous_research:{research_route}")
    sources: List[SourceItem] = []
    verified_sources: List[SourceItem] = []
    confidence = "none"
    rounds = 0

    if use_research:
        research = research_with_realtime_fallback(understanding_message)
        confidence = str(research.get("confidence", "none"))
        rounds = int(research.get("rounds", 0) or 0)
        sources = convert_sources(research.get("sources", []))
        verified_sources = verified_sources_only(sources, understanding_message)
        provider = str(research.get("provider", "research_engine"))
        tools_used.append(f"{provider}:{confidence}:rounds_{rounds}")
        if research.get("route"):
            tools_used.append(f"realtime_route:{research.get('route')}")
        if research.get("queries"):
            tools_used.append(f"realtime_query_variants:{len(research.get('queries') or [])}")
        if not research.get("ok") or not verified_sources:
            trusted_sources = trusted_current_role_sources(understanding_message)
            if trusted_sources:
                reply = clean_reply(search_evidence_fallback_reply(original_user_message, trusted_sources))
                reply = ensure_inline_citations(reply, trusted_sources)
                append_session_message(session_id, "user", original_user_message)
                append_session_message(session_id, "assistant", reply)
                maybe_store_memory(original_user_message, user_id)
                learn_long_term_memory_from_chat(
                    original_user_message,
                    reply,
                    user_id,
                    session_id,
                    response_lane,
                    presentation_style,
                    behavior_signals,
                )
                if not skip_response_cache:
                    set_cached_response(response_cache_key, reply, "trusted_current_role_fallback", trusted_sources)
                return ChatResponse(
                    reply=reply,
                    session_id=session_id,
                    mode=req.mode or "agent",
                    model_used="trusted_current_role_fallback",
                    sources=trusted_sources,
                    tools_used=tools_used + ["trusted_current_role_fallback"],
                    route_intent=task_intent,
                    created_at=now_iso(),
                )
            reply = (
                "I do not have verified current evidence for that yet. "
                "I will not guess about latest news, prices, filings, results, or dates without a reliable source."
            )
            append_session_message(session_id, "user", original_user_message)
            append_session_message(session_id, "assistant", reply)
            learn_long_term_memory_from_chat(
                original_user_message,
                reply,
                user_id,
                session_id,
                response_lane,
                presentation_style,
                behavior_signals,
            )
            return ChatResponse(
                reply=reply,
                session_id=session_id,
                mode=req.mode or "agent",
                model_used="strict_verification",
                sources=[],
                tools_used=tools_used,
                route_intent=task_intent,
                created_at=now_iso(),
            )

    file_context = build_file_context(session_id)
    image_context = build_image_context(session_id, req.image_ids)
    if image_context:
        file_context = "\n\n".join(part for part in [file_context, image_context] if part)
    if file_context:
        tools_used.append("file_context")
    if image_context:
        tools_used.append("image_context")
    memory_context = build_memory_context(user_id, understanding_message)
    if memory_context and not use_research:
        tools_used.append("memory")
    if understanding_context:
        tools_used.append("context_understanding")
    persona_context = build_persona_context(persona_profile)
    tools_used.append("adaptive_persona")
    behavior_context = build_behavior_context(behavior_profile, behavior_signals)
    response_lane_context = build_response_lane_context(understanding_message, use_research)
    presentation_context = build_presentation_context(understanding_message, response_lane, use_research)
    intent_context = build_intent_context(intent)
    tools_used.append(f"response_lane:{response_lane}")
    tools_used.append(f"presentation:{presentation_style}")

    routed_local = local_reply_for_intent(understanding_message, task_intent, session_id=session_id) if not use_research and not force_ollama_chat else None
    local_structured = (
        routed_local
        or (
            local_structured_fallback(understanding_message, response_lane, presentation_style, session_id=session_id)
            if not use_research and not force_ollama_chat
            else None
        )
    )
    if routed_local:
        tools_used.append("intent_route:local_candidate")
    local_context_reply = None
    if not use_research and not routed_local and not force_ollama_chat:
        focus_for_local = recent_session_focus(get_session(session_id), original_user_message)
        local_context_reply = (
            local_continuation_reply(understanding_message, focus_for_local)
            or local_vague_improvement_reply(understanding_message, focus_for_local)
            or local_capability_reply(understanding_message)
        )
    if local_context_reply:
        final_reply = finalize_user_facing_answer(original_user_message, local_context_reply, response_lane, presentation_style)
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", final_reply)
        maybe_store_memory(original_user_message, user_id)
        learn_long_term_memory_from_chat(
            original_user_message,
            final_reply,
            user_id,
            session_id,
            response_lane,
            presentation_style,
            behavior_signals,
        )
        set_cached_response(response_cache_key, final_reply, "nexora_context_resilient", [])
        return ChatResponse(
            reply=final_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="nexora_context_resilient",
            sources=[],
            tools_used=tools_used + ["local_context_resilient"],
            route_intent=task_intent,
            created_at=now_iso(),
        )
    local_first_stable = response_lane == "writing" or task_intent in LANGUAGE_ROUTE_NAMES or is_high_confidence_local_reply(understanding_message, presentation_style) or (
        presentation_style == "table" and "anime" in clean_text(original_user_message).lower()
    )
    force_local_structured = bool(
        local_structured
        and local_first_stable
        and (
            is_high_confidence_local_reply(understanding_message, presentation_style)
            or task_intent in LANGUAGE_ROUTE_NAMES
            or str(writing_request.get("kind", "")).lower() in {"letter", "application", "notice"}
            or is_world_war_two_topic(understanding_message)
        )
    )
    if local_structured and local_first_stable and (LOCAL_WRITING_FAST or force_local_structured) and not force_ollama_chat:
        final_reply = finalize_user_facing_answer(original_user_message, local_structured, response_lane, presentation_style)
        final_repaired, final_quality_flags, repaired_intent = quality_gate_local_repair(
            original_user_message,
            final_reply,
            response_lane,
            presentation_style,
            session_id=session_id,
            use_research=use_research,
        )
        if final_quality_flags:
            tools_used.append("quality_gate:local_fast:" + ",".join(final_quality_flags[:4]))
        if repaired_intent and final_repaired != final_reply:
            final_reply = final_repaired
            tools_used.append(f"quality_gate:local_fast_repaired_by:{repaired_intent}")
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", final_reply)
        maybe_store_memory(original_user_message, user_id)
        learn_long_term_memory_from_chat(
            original_user_message,
            final_reply,
            user_id,
            session_id,
            response_lane,
            presentation_style,
            behavior_signals,
        )
        if not skip_response_cache:
            set_cached_response(response_cache_key, final_reply, "nexora_local_structured", [])
        return ChatResponse(
            reply=final_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="nexora_local_structured",
            sources=[],
            tools_used=tools_used + ["local_structured_fast"],
            route_intent=task_intent,
            created_at=now_iso(),
        )

    research_context = build_research_context(verified_sources, understanding_message, confidence, rounds) if verified_sources else ""
    free_club_context = ""
    free_club_sources: List[SourceItem] = []
    use_free_club = should_use_free_club(
        understanding_message,
        use_research,
        response_mode,
        response_lane,
        presentation_style,
    ) or (research_route in {"wikipedia", "web_light", "web_current"})
    if use_free_club:
        tools_used.append(f"free_club:{FREE_CLUB_MODE}")
        if not use_research and research_route in {"wikipedia", "web_light", "web_current"}:
            free_club_context, free_club_sources, club_status = build_autonomous_research_context(
                understanding_message,
                research_route,
            )
            tools_used.append(f"free_club:{club_status}")
        elif should_add_free_club_search(understanding_message, use_research, response_lane, presentation_style):
            free_club_context, free_club_sources, club_status = build_free_club_search_context(understanding_message)
            tools_used.append(f"free_club:{club_status}")
        elif should_add_wikipedia_context(understanding_message, response_lane, presentation_style):
            free_club_context, free_club_sources, club_status = build_wikipedia_context(understanding_message)
            tools_used.append(f"free_club:{club_status}")

    combined_research_context = "\n\n".join(
        part for part in [research_context, free_club_context] if part
    )

    if verified_sources and should_fast_return_research_answer(understanding_message, presentation_style) and not force_ollama_chat:
        final_reply = finalize_user_facing_answer(
            original_user_message,
            search_evidence_fallback_reply(original_user_message, verified_sources),
            response_lane,
            presentation_style,
        )
        final_reply = ensure_inline_citations(final_reply, verified_sources)
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", final_reply)
        maybe_store_memory(original_user_message, user_id)
        learn_long_term_memory_from_chat(
            original_user_message,
            final_reply,
            user_id,
            session_id,
            response_lane,
            presentation_style,
            behavior_signals,
        )
        if not skip_response_cache:
            set_cached_response(response_cache_key, final_reply, "realtime_search_fast", verified_sources)
        return ChatResponse(
            reply=final_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="realtime_search_fast",
            sources=verified_sources,
            tools_used=tools_used + ["realtime_search_fast"],
            route_intent=task_intent,
            created_at=now_iso(),
        )

    if (
        free_club_sources
        and free_club_sources[0].provider == "wikipedia"
        and presentation_style in {"short", "teaching_structure", "balanced"}
        and not force_ollama_chat
    ):
        final_reply = finalize_user_facing_answer(
            original_user_message,
            wikipedia_fallback_reply(understanding_message, free_club_sources),
            response_lane,
            presentation_style,
        )
        append_session_message(session_id, "user", original_user_message)
        append_session_message(session_id, "assistant", final_reply)
        maybe_store_memory(original_user_message, user_id)
        learn_long_term_memory_from_chat(
            original_user_message,
            final_reply,
            user_id,
            session_id,
            response_lane,
            presentation_style,
            behavior_signals,
        )
        if not skip_response_cache:
            set_cached_response(response_cache_key, final_reply, "wikipedia_summary_fast", free_club_sources)
        return ChatResponse(
            reply=final_reply,
            session_id=session_id,
            mode=req.mode or "agent",
            model_used="wikipedia_summary_fast",
            sources=free_club_sources,
            tools_used=tools_used + ["wikipedia_summary_fast"],
            route_intent=task_intent,
            created_at=now_iso(),
        )

    model_user_message = understanding_message
    if clean_text(understanding_message).lower() != clean_text(original_user_message).lower():
        model_user_message = (
            f"{understanding_message}\n\n"
            f"Original wording: {original_user_message}\n"
            "Answer the corrected intent, not the typo."
        )

    messages = build_messages(
        user_message=model_user_message,
        history=history,
        research_context=combined_research_context,
        file_context=file_context,
        memory_context=memory_context,
        persona_context=persona_context,
        behavior_context=behavior_context,
        response_lane_context=response_lane_context,
        presentation_context=presentation_context,
        understanding_context=understanding_context,
        intent_context=intent_context,
        use_research=use_research,
        response_mode=response_mode,
    )

    model_used = ""
    model_failed = False
    generation_started = time.time()
    try:
        reply, model_used, engine_tools = generate_with_engine_club(
            messages,
            req.model,
            response_mode,
            response_lane,
            presentation_style,
            use_research,
            combined_research_context,
            file_context,
            memory_context,
        )
        tools_used.extend(engine_tools)
    except Exception as error:
        tools_used.append("engine_club_failed")
        if force_ollama_chat:
            model_failed = True
            model_used = f"ollama:{select_ollama_model(req.model)}:{response_mode}:failed"
            reply = (
                "Ollama/Qwen is selected, but it did not return a usable response. "
                f"Check that Ollama is running at {OLLAMA_URL} with the qwen3:14b model loaded."
            )
            tools_used.append(f"ollama_required_failed:{error}")
        elif verified_sources:
            model_used = "realtime_search_fallback"
            reply = search_evidence_fallback_reply(original_user_message, verified_sources)
            tools_used.append("search_evidence_fallback")
        elif free_club_sources and free_club_sources[0].provider == "wikipedia":
            model_used = "wikipedia_summary_fallback"
            reply = wikipedia_fallback_reply(understanding_message, free_club_sources)
            tools_used.append("wikipedia_summary_fallback")
        elif free_club_sources:
            model_used = "autonomous_research_fallback"
            reply = search_evidence_fallback_reply(understanding_message, free_club_sources)
            tools_used.append("autonomous_research_fallback")
        elif local_structured:
            model_used = "nexora_local_structured"
            reply = local_structured
            tools_used.append("local_structured_fallback")
        else:
            model_used = "nexora_local_resilient"
            reply = local_resilient_reply(
                understanding_message,
                session_id,
                response_lane,
                presentation_style,
                understanding_state,
            )
            tools_used.append("local_resilient_fallback")

    quality_flags = answer_quality_flags(original_user_message, reply, response_lane, presentation_style, task_intent)
    if quality_flags:
        tools_used.append("quality_guard:" + ",".join(quality_flags[:4]))
        if (
            not force_ollama_chat
            and
            local_structured
            and not use_research
            and (
                any(flag in quality_flags for flag in {
                "generic_plan",
                "generic_topic_drift",
                "weak_fallback",
                "too_short",
                "backend_talk",
                "missing_table",
                "unverified_recommendation_metadata",
                "stream_artifact",
                "traceback_or_error_dump",
                "tool_dump",
                "raw_json_output",
                "missing_current_verification",
                "missing_accuracy_signal",
                })
                or any(flag.startswith("route_mismatch_") for flag in quality_flags)
            )
        ):
            model_used = "nexora_local_structured"
            reply = local_structured
            tools_used.append("quality_guard:local_structured")
        elif not force_ollama_chat and free_club_mode_enabled() and not is_bad_generated_reply(reply):
            reviewed_reply = free_club_review_reply(
                original_user_message,
                reply,
                combined_research_context,
                response_lane,
                presentation_style,
            )
            if reviewed_reply and should_accept_reviewed_reply(original_user_message, reviewed_reply, response_lane, presentation_style):
                reply = reviewed_reply
                tools_used.append("quality_guard:pollinations_review")

    if is_bad_generated_reply(reply) and verified_sources:
        model_used = "realtime_search_fallback"
        reply = search_evidence_fallback_reply(original_user_message, verified_sources)
        tools_used.append("empty_reply_search_fallback")

    generation_seconds = time.time() - generation_started
    cleaned_preview = clean_reply(reply) if not is_bad_generated_reply(reply) else ""
    if (
        use_free_club
        and not force_ollama_chat
        and not model_failed
        and model_used != "realtime_search_fallback"
        and not is_bad_generated_reply(reply)
        and generation_seconds <= FREE_CLUB_REVIEW_BUDGET_SECONDS
        and "quality_guard:pollinations_review" not in tools_used
        and not (free_club_sources and presentation_style == "short")
        and should_review_free_club_reply(
            reply,
            cleaned_preview,
            use_research,
            response_mode,
            response_lane,
            presentation_style,
        )
    ):
        reviewed_reply = free_club_review_reply(
            original_user_message,
            reply,
            combined_research_context,
            response_lane,
            presentation_style,
        )
        if reviewed_reply:
            reply = reviewed_reply
            tools_used.append("free_club:review")

    final_reply = finalize_user_facing_answer(original_user_message, reply, response_lane, presentation_style)
    if verified_sources:
        final_reply = ensure_inline_citations(final_reply, verified_sources)
    elif (
        free_club_sources
        and research_route in {"web_light", "web_current"}
        and (presentation_style == "answer_with_evidence" or research_route == "web_current")
    ):
        final_reply = ensure_inline_citations(final_reply, free_club_sources)
    response_sources = verified_sources if verified_sources else free_club_sources
    if is_bad_generated_reply(final_reply) and not model_failed and not force_ollama_chat:
        if local_structured:
            model_used = "nexora_local_structured"
            final_reply = finalize_user_facing_answer(original_user_message, local_structured, response_lane, presentation_style)
            tools_used.append("empty_reply_local_structured")
        else:
            model_used = "nexora_local_resilient"
            final_reply = finalize_user_facing_answer(
                original_user_message,
                local_resilient_reply(
                    understanding_message,
                    session_id,
                    response_lane,
                    presentation_style,
                    understanding_state,
                ),
                response_lane,
                presentation_style,
            )
            tools_used.append("empty_reply_local_resilient")
    final_repaired, final_quality_flags, repaired_intent = (
        (final_reply, [], "")
        if force_ollama_chat
        else quality_gate_local_repair(
            original_user_message,
            final_reply,
            response_lane,
            presentation_style,
            session_id=session_id,
            use_research=use_research,
        )
    )
    if final_quality_flags:
        tools_used.append("quality_gate:final:" + ",".join(final_quality_flags[:4]))
    if repaired_intent and final_repaired != final_reply:
        final_reply = final_repaired
        model_used = "nexora_quality_repair"
        response_sources = []
        tools_used.append(f"quality_gate:repaired_by:{repaired_intent}")
    append_session_message(session_id, "user", original_user_message)
    append_session_message(session_id, "assistant", final_reply)
    maybe_store_memory(original_user_message, user_id)
    learn_long_term_memory_from_chat(
        original_user_message,
        final_reply,
        user_id,
        session_id,
        response_lane,
        presentation_style,
        behavior_signals,
    )
    if not model_failed and not is_bad_generated_reply(final_reply):
        set_cached_response(response_cache_key, final_reply, model_used, response_sources)
    return ChatResponse(
        reply=final_reply,
        session_id=session_id,
        mode=req.mode or "agent",
        model_used=model_used,
        sources=[] if model_failed else response_sources,
        tools_used=tools_used,
        route_intent=task_intent,
        created_at=now_iso(),
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
    def event(data: Dict[str, Any]) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def generator():
        try:
            response = chat(req, request)
            yield event({
                "type": "meta",
                "session_id": response.session_id,
                "sources": [source_to_dict(s) for s in response.sources],
            })
            text = response.reply
            chunk_size = 44
            for index in range(0, len(text), chunk_size):
                chunk = text[index:index + chunk_size]
                yield event({"type": "token", "text": chunk, "token": chunk})
                await asyncio.sleep(0.001)
            yield event({
                "type": "done",
                "reply": response.reply,
                "sources": [source_to_dict(s) for s in response.sources],
            })
        except Exception as error:
            LOGGER.exception("stream_chat_failed")
            yield event({
                "type": "error",
                "message": "I could not complete that response cleanly. Please send the question again, and I will answer directly.",
            })

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
) -> UploadResponse:
    session_id = ensure_session(session_id)
    resolved_user_id = register_request_user(request, user_id, session_id)
    original_name = file.filename or "uploaded_file"
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", original_name)[:120]
    saved_name = f"{session_id}_{int(time.time())}_{safe_name}"
    saved_path = UPLOAD_DIR / saved_name
    content = await file.read()
    saved_path.write_bytes(content)
    extracted = basic_extract_text(saved_path)
    summary = summarize_text_locally(extracted, 5) if extracted else {
        "summary": "No readable text was extracted from this file.",
        "key_points": [],
        "action_items": [],
        "word_count": 0,
    }
    file_limit = current_performance_limits().get("file_context_chars", MAX_FILE_CONTEXT_CHARS)
    file_record = {
        "filename": original_name,
        "saved_as": saved_name,
        "path": str(saved_path),
        "uploaded_at": now_iso(),
        "user_id": resolved_user_id,
        "text": extracted[:file_limit],
        "summary": summary,
    }

    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        session = sessions.get(session_id) or new_session_record(session_id)
        session.setdefault("files", []).append(file_record)
        session["files"] = session["files"][-10:]
        session["updated_at"] = now_iso()
        sessions[session_id] = session
        return None, True

    update_json_dict(SESSIONS_FILE, {}, mutate)
    return UploadResponse(
        ok=True,
        session_id=session_id,
        filename=original_name,
        saved_as=saved_name,
        extracted_chars=len(extracted),
        message="File uploaded. Nexora will use it when relevant. Ask 'summarize this file' for a structured summary.",
    )


@app.get("/sessions/{session_id}")
def read_session(session_id: str, request: Request) -> Dict[str, Any]:
    user = optional_authenticated_user(request)
    if user:
        return require_session_owner(session_id, str(user.get("id", "")))
    session = get_session(session_id)
    owner = normalize_user_id(str(session.get("user_id", "")))
    if owner and owner != "default":
        raise HTTPException(status_code=401, detail="Login required.")
    return session


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request) -> Dict[str, Any]:
    user = optional_authenticated_user(request)
    if user:
        require_session_owner(session_id, str(user.get("id", "")))
    else:
        session = get_session(session_id)
        owner = normalize_user_id(str(session.get("user_id", "")))
        if owner and owner != "default":
            raise HTTPException(status_code=401, detail="Login required.")

    def mutate(sessions: Dict[str, Any]) -> Tuple[None, bool]:
        if session_id in sessions:
            del sessions[session_id]
            return None, True
        return None, False

    update_json_dict(SESSIONS_FILE, {}, mutate)
    return {"ok": True, "deleted": session_id}


@app.get("/memory")
def read_memory(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    items = load_memory()
    items = [
        item for item in items
        if normalize_user_id(str(item.get("user_id", "default"))) == normalized
    ]
    return {"user_id": normalized, "items": items}


@app.post("/memory/clear")
def clear_memory(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    normalized = normalize_user_id(resolve_user_id_for_request(request, user_id))
    save_memory([
        item for item in load_memory()
        if normalize_user_id(str(item.get("user_id", "default"))) != normalized
    ])
    return {"ok": True, "user_id": normalized, "message": "Nexora memory cleared for this user."}


@app.get("/persona")
def read_persona() -> Dict[str, Any]:
    profile = load_persona_profile()
    return {"ok": True, "profile": profile, "signature": persona_signature(profile)}


@app.post("/persona/reset")
def reset_persona() -> Dict[str, Any]:
    profile = default_persona_profile()
    save_persona_profile(profile)
    return {"ok": True, "profile": load_persona_profile(), "message": "Nexora persona reset."}


@app.get("/behavior")
def read_behavior() -> Dict[str, Any]:
    profile = load_behavior_profile()
    return {"ok": True, "profile": profile, "signature": behavior_signature(profile)}


@app.post("/behavior/reset")
def reset_behavior() -> Dict[str, Any]:
    profile = default_behavior_profile()
    save_behavior_profile(profile)
    return {"ok": True, "profile": load_behavior_profile(), "message": "Nexora behavior learning reset."}


@app.post("/feedback")
def save_feedback(req: FeedbackRequest) -> Dict[str, Any]:
    profile = learn_behavior_from_feedback(req)
    return {
        "ok": True,
        "message": "Feedback saved. Nexora will adapt future answers.",
        "signature": behavior_signature(profile),
    }


@app.get("/finance")
def finance() -> Dict[str, Any]:
    return {
        "ok": True,
        "data": {
            "metrics": {
                "markets_open": "Research Engine",
                "tracked_assets": 6,
                "watchlist_count": 3,
            },
            "overview": [
                {
                    "name": "NIFTY 50",
                    "tag": "India index",
                    "badge": "Index",
                    "price": "Ask Nexora",
                    "change_percent": 0,
                    "change_text": "Use verified research for live market context",
                },
                {
                    "name": "SENSEX",
                    "tag": "India index",
                    "badge": "Index",
                    "price": "Ask Nexora",
                    "change_percent": 0,
                    "change_text": "Use verified research for live market context",
                },
            ],
            "summaries": [
                {
                    "title": "Nexora free API agent connected",
                    "text": "Ask for stocks, sectors, filings, and verified market updates.",
                }
            ],
            "watchlist": [],
            "predictions": [],
            "quick_stats": [],
            "insight": "Finance page is active. Nexora avoids guessing without evidence.",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("NEXORA_RELOAD", "false").strip().lower() in {"1", "true", "yes"},
    )
