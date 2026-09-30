"""Shared LLM and embedding provider resolution."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
import requests
from chromadb.utils import embedding_functions
from platformdirs import user_data_dir

SCHEMA_COLLECTION_NAME = "database_schema_metadata"


def default_chroma_path() -> Path:
    configured = os.getenv("NL2SQL_DATA_DIR")
    base = Path(configured).expanduser() if configured else Path(user_data_dir("NL2SQL", "nonvegetable"))
    return base / "chroma"


CHROMA_PATH = str(default_chroma_path())

DEFAULT_LLM_PROVIDER = "lmstudio"
DEFAULT_LLM_MODEL = "google/gemma-4-e2b"
DEFAULT_EMBEDDING_PROVIDER = "lmstudio"
DEFAULT_LM_STUDIO_ORIGIN = "http://localhost:1234"
DEFAULT_LM_STUDIO_EMBEDDING_MODEL = "text-embedding-nomic-embed-text-v1.5"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_EMBEDDING_MODEL = "mxbai-embed-large"
DEFAULT_OLLAMA_ORIGIN = "http://localhost:11434"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/embeddings"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

CLOUD_PROVIDERS = {"openai", "anthropic", "claude", "gemini", "google", "google-genai"}
PROVIDER_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "google-genai": "GEMINI_API_KEY",
}
PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Claude (Anthropic)",
    "claude": "Claude (Anthropic)",
    "gemini": "Gemini",
    "google": "Gemini",
    "google-genai": "Gemini",
    "lmstudio": "LM Studio",
    "lm-studio": "LM Studio",
    "ollama": "Ollama",
}


def normalize_provider(name: str) -> str:
    """Normalize provider aliases such as 'LM Studio' or 'lm_studio'."""
    return (name or "").strip().lower().replace("_", "-").replace(" ", "-")


def lm_studio_origin() -> str:
    """LM Studio host, e.g. http://localhost:1234 (no /v1 suffix)."""
    raw = os.getenv("LM_STUDIO_BASE_URL", DEFAULT_LM_STUDIO_ORIGIN).strip().rstrip("/")
    if raw.endswith("/v1"):
        return raw[: -len("/v1")].rstrip("/")
    return raw or DEFAULT_LM_STUDIO_ORIGIN


def lm_studio_base_url() -> str:
    """OpenAI-compatible base URL, e.g. http://localhost:1234/v1."""
    return f"{lm_studio_origin()}/v1"


def lm_studio_api_key() -> str:
    # LM Studio does not validate keys; the OpenAI client still requires a value.
    return os.getenv("LM_STUDIO_API_KEY", "lm-studio")


def lm_studio_no_model_message() -> str:
    return (
        f"No chat model is loaded in LM Studio on {lm_studio_origin()}. "
        "Open LM Studio, load a model, and keep the local server running "
        "(or run `lms load <model-id>`), then refresh."
    )


def ollama_origin() -> str:
    """Ollama host, e.g. http://localhost:11434."""
    host = (os.getenv("OLLAMA_HOST") or "").strip().rstrip("/")
    if host:
        if host.endswith("/v1"):
            return host[: -len("/v1")].rstrip("/")
        return host
    url = (os.getenv("OLLAMA_URL") or DEFAULT_OLLAMA_URL).strip().rstrip("/")
    for suffix in ("/api/embeddings", "/api/chat", "/api/generate", "/api", "/v1"):
        if url.endswith(suffix):
            return url[: -len(suffix)].rstrip("/") or DEFAULT_OLLAMA_ORIGIN
    return url or DEFAULT_OLLAMA_ORIGIN


def ollama_no_model_message() -> str:
    return (
        f"No chat models found in Ollama on {ollama_origin()}. "
        "Pull a model with `ollama pull <model>` (for example `ollama pull llama3.2`), then refresh."
    )


def ollama_unreachable_message(exc: Exception | None = None) -> str:
    extra = f" ({exc})" if exc else ""
    return (
        f"Could not reach Ollama at {ollama_origin()}{extra}. "
        "Start it with `ollama serve` and pull a model, then refresh."
    )


def api_key_env_name(provider: str) -> str | None:
    return PROVIDER_API_KEY_ENV.get(normalize_provider(provider))


def provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(normalize_provider(provider), provider)


def resolve_api_key(provider: str, api_key: str | None = None) -> str | None:
    if api_key and str(api_key).strip():
        return str(api_key).strip()
    env_name = api_key_env_name(provider)
    if not env_name:
        return None
    value = os.getenv(env_name)
    if not value and env_name == "GEMINI_API_KEY":
        value = os.getenv("GOOGLE_API_KEY")
    return (value or "").strip() or None


def missing_api_key_message(provider: str) -> str:
    label = provider_label(provider)
    env_name = api_key_env_name(provider)
    extra = f" You can also set {env_name} in .env." if env_name else ""
    return f"Enter your {label} API key in the sidebar to list models and make calls.{extra}"


def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)


def open_schema_collection(*, create: bool = False):
    client = get_chroma_client()
    embed_fn = build_embedding_function()

    try:
        if create:
            return client.get_or_create_collection(name=SCHEMA_COLLECTION_NAME, embedding_function=embed_fn)
        return client.get_collection(name=SCHEMA_COLLECTION_NAME, embedding_function=embed_fn)
    except ValueError as exc:
        message = str(exc)
        if "Embedding function conflict" in message:
            if create:
                client.delete_collection(SCHEMA_COLLECTION_NAME)
                return client.get_or_create_collection(name=SCHEMA_COLLECTION_NAME, embedding_function=embed_fn)
            raise ValueError(
                "The schema vector store was built with a different embedding provider. "
                "Sync the schema again so it is rebuilt for the current settings."
            ) from exc
        raise


def build_embedding_function():
    provider = normalize_provider(os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER))

    if provider in {"lmstudio", "lm-studio"}:
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=lm_studio_api_key(),
            api_base=lm_studio_base_url(),
            model_name=os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_LM_STUDIO_EMBEDDING_MODEL),
        )

    if provider == "openai":
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("Configuration Error: 'OPENAI_API_KEY' is missing in .env for OpenAI embeddings.")
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai_api_key,
            model_name=os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_OPENAI_EMBEDDING_MODEL),
        )

    return embedding_functions.OllamaEmbeddingFunction(
        url=os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL),
        model_name=os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_OLLAMA_EMBEDDING_MODEL),
    )


def call_llm(
    system_prompt: str,
    user_prompt: str,
    provider: str = None,
    model_name: str = None,
    api_key: str = None,
) -> str:
    active_provider = normalize_provider(provider or os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER))
    default_model = DEFAULT_LLM_MODEL if active_provider in {"lmstudio", "lm-studio"} else DEFAULT_OLLAMA_MODEL
    active_model = model_name or os.getenv("LLM_MODEL_NAME", default_model)
    resolved_key = resolve_api_key(active_provider, api_key)

    if active_provider == "openai":
        import openai

        if not resolved_key:
            raise ValueError(missing_api_key_message("openai"))
        if not active_model:
            raise ValueError("Select an OpenAI model before generating SQL.")
        client = openai.OpenAI(api_key=resolved_key)
        response = client.chat.completions.create(
            model=active_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    if active_provider in {"anthropic", "claude"}:
        import anthropic

        if not resolved_key:
            raise ValueError(missing_api_key_message("anthropic"))
        if not active_model:
            raise ValueError("Select a Claude model before generating SQL.")
        client = anthropic.Anthropic(api_key=resolved_key)
        response = client.messages.create(
            model=active_model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2048,
        )
        return response.content[0].text.strip()

    if active_provider in {"gemini", "google", "google-genai"}:
        import google.generativeai as genai

        if not resolved_key:
            raise ValueError(missing_api_key_message("gemini"))
        if not active_model:
            raise ValueError("Select a Gemini model before generating SQL.")
        genai.configure(api_key=resolved_key)
        model = genai.GenerativeModel(active_model)
        response = model.generate_content(system_prompt + "

" + user_prompt)
        return response.text.strip()

    if active_provider in {"lmstudio", "lm-studio"}:
        response = requests.post(
            f"{lm_studio_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {lm_studio_api_key()}"},
            json={
                "model": active_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    if active_provider == "ollama":
        response = requests.post(
            f"{ollama_origin()}/api/chat",
            json={
                "model": active_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()

    raise ValueError(f"Unsupported provider: {provider}")
