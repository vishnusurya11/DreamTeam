import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

load_dotenv()

# --- LLM Provider ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")

# General
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# --- Pipeline ---
TICK_INTERVAL_SECONDS = 5
MAX_RETRIES = 3

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACES_DIR = os.path.join(BASE_DIR, "workspaces")
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

# --- Server ---
HOST = "127.0.0.1"
PORT = 8000

# --- Agent Definitions ---
AGENTS = [
    # Planning team
    {
        "name": "Paula",
        "role": "planner",
        "personality": "Experienced project manager. Breaks features into actionable tasks with clear acceptance criteria. Focuses on scope, timeline, and deliverables.",
    },
    {
        "name": "Alex",
        "role": "planner",
        "personality": "Software architect. Focuses on technical decomposition, system dependencies, and design patterns. Ensures tasks are technically sound.",
    },
    {
        "name": "Sam",
        "role": "planner",
        "personality": "Product strategist. Prioritizes by user impact, identifies risks, and defines scope boundaries. Ensures the plan is practical.",
    },
    # Dev team
    {
        "name": "Charlie",
        "role": "builder",
        "personality": "Senior Python developer. Writes clean, well-structured code with clear variable names.",
    },
    {
        "name": "Codex",
        "role": "builder",
        "personality": "Full-stack engineer. Focuses on architecture, design patterns, and maintainability.",
    },
    # QA
    {
        "name": "Henry",
        "role": "qa",
        "personality": "Meticulous QA engineer. Writes thorough test cases and edge case scenarios.",
    },
    # Reviewer
    {
        "name": "Ralph",
        "role": "reviewer",
        "personality": "Experienced code reviewer. Checks for bugs, code style, security issues, and best practices.",
    },
]


def get_model():
    """Create and return a chat model based on LLM_PROVIDER env var."""
    if LLM_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required when using openrouter provider")
        print(f"[config] Using OpenRouter model: {OPENROUTER_MODEL}")
        return ChatOpenAI(
            model=OPENROUTER_MODEL,
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            temperature=TEMPERATURE,
        )
    elif LLM_PROVIDER == "ollama":
        print(f"[config] Using Ollama model: {OLLAMA_MODEL}")
        return ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=TEMPERATURE,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}. Use 'ollama' or 'openrouter'")
