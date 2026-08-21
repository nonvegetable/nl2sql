"""
Shared LLM and embedding provider resolution.

Defaults to the local LM Studio OpenAI-compatible server. Ollama and cloud
providers remain available via LLM_PROVIDER / EMBEDDING_PROVIDER.
"""

import os

import chromadb
import requests
from chromadb.utils import embedding_functions

SCHEMA_COLLECTION_NAME = "database_schema_metadata"
CHROMA_PATH = "./chroma_db"

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
    """
    Open the schema collection with the active embedding function.

    When `create` is True (schema sync), a leftover collection from another
    embedding provider is deleted and recreated. When False (query path), a
    mismatch raises a clear 'please re-sync' error instead of crashing import.
    """
    client = get_chroma_client()
    embed_fn = build_embedding_function()

    try:
        if create:
            return client.get_or_create_collection(
                name=SCHEMA_COLLECTION_NAME,
                embedding_function=embed_fn,
            )
        return client.get_collection(
            name=SCHEMA_COLLECTION_NAME,
            embedding_function=embed_fn,
        )
    except ValueError as exc:
        message = str(exc)
        if "Embedding function conflict" in message:
            if create:
                client.delete_collection(SCHEMA_COLLECTION_NAME)
                return client.get_or_create_collection(
                    name=SCHEMA_COLLECTION_NAME,
                    embedding_function=embed_fn,
                )
            raise ValueError(
                "The schema vector store was built with a different embedding provider. "
                "Sync the schema again (sidebar → Sync Schema to Vector DB, or "
                "`python sync_schema.py`) so it is rebuilt for the current settings."
            ) from exc
        raise


def build_embedding_function():
    """Return a Chroma embedding function for the configured provider."""
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

    # Default local Ollama embeddings — kept for users who still run Ollama.
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
    """Universal LLM wrapper supporting LM Studio, Ollama, OpenAI, Anthropic, and Gemini."""
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
        model = genai.GenerativeModel(
            model_name=active_model,
            system_instruction=system_prompt,
        )
        response = model.generate_content(user_prompt)
        return response.text.strip()

    if active_provider in {"lmstudio", "lm-studio"}:
        from openai import OpenAI

        base_url = lm_studio_base_url()
        try:
            loaded = get_lm_studio_loaded_llm_models()
        except ConnectionError:
            raise
        if not loaded:
            raise ConnectionError(lm_studio_no_model_message())
        if not active_model or active_model not in loaded:
            active_model = loaded[0]

        client = OpenAI(base_url=base_url, api_key=lm_studio_api_key())
        try:
            response = client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:
            raise ConnectionError(
                f"Could not reach LM Studio at {base_url}. "
                "Start the local server with `lms server start` and load a model "
                f"(currently trying {active_model})."
            ) from exc
        content = response.choices[0].message.content or ""
        return content.strip()

    # Default local Ollama — kept so existing Ollama configs still work.
    import ollama

    try:
        available = get_ollama_llm_models()
    except ConnectionError:
        raise
    if not available:
        raise ConnectionError(ollama_no_model_message())
    if not active_model:
        active_model = available[0]

    try:
        client = ollama.Client(host=ollama_origin())
        response = client.chat(
            model=active_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        raise ConnectionError(
            f"Ollama request failed for {active_model} at {ollama_origin()}. {exc}"
        ) from exc
    return response["message"]["content"].strip()


def _is_embedding_model(model_id: str, kind: str = "") -> bool:
    kind = (kind or "").lower()
    name = (model_id or "").lower()
    return kind in {"embeddings", "embedding"} or "embed" in name


def _loaded_llm_ids(payload, *, require_loaded_state: bool) -> list[str]:
    """Extract chat/VLM model ids from an LM Studio models payload."""
    items = []
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            items = payload["data"]
        elif isinstance(payload.get("models"), list):
            items = payload["models"]
        elif "error" in payload:
            return []
    elif isinstance(payload, list):
        items = payload

    loaded = []
    seen = set()
    for item in items:
        if isinstance(item, str):
            model_id, kind, state = item, "", "loaded"
        elif isinstance(item, dict):
            model_id = item.get("id") or item.get("name")
            kind = item.get("type") or ""
            state = (item.get("state") or "loaded").lower()
        else:
            continue
        if not model_id or _is_embedding_model(model_id, kind):
            continue
        if require_loaded_state and state not in {"loaded", "loading"}:
            continue
        if model_id not in seen:
            seen.add(model_id)
            loaded.append(model_id)
    return loaded


def get_lm_studio_loaded_llm_models(timeout: int = 5) -> list[str]:
    """Return chat/VLM models currently loaded in LM Studio (not embeddings).

    Prefers `/api/v0/models` which includes load state. Raises ConnectionError
    if the server cannot be reached. Returns an empty list when the server is
    up but no chat model is loaded.
    """
    origin = lm_studio_origin()
    headers = {"Authorization": f"Bearer {lm_studio_api_key()}"}

    v0_url = f"{origin}/api/v0/models"
    try:
        resp = requests.get(v0_url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                return _loaded_llm_ids(data, require_loaded_state=True)
    except requests.RequestException:
        pass

    v1_url = f"{origin}/v1/models"
    try:
        resp = requests.get(v1_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "error" in data and "data" not in data:
            raise ConnectionError(data.get("error") or f"Unexpected response from {v1_url}")
        return _loaded_llm_ids(data, require_loaded_state=False)
    except Exception as exc:
        raise ConnectionError(
            f"Could not reach LM Studio at {origin}. "
            "Start the local server with `lms server start` and load a model."
        ) from exc


def get_lm_studio_models(timeout: int = 5):
    """Backward-compatible alias: currently loaded chat models in LM Studio."""
    return get_lm_studio_loaded_llm_models(timeout=timeout)


def _dedupe_sort(items, preferred=()):
    seen = set()
    ordered = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    preferred_present = [item for item in preferred if item in seen]
    rest = sorted(item for item in ordered if item not in set(preferred))
    return preferred_present + rest


def get_ollama_llm_models(timeout: int = 5) -> list[str]:
    """Return pulled Ollama chat models (embedding models excluded)."""
    origin = ollama_origin()
    url = f"{origin}/api/tags"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise ConnectionError(ollama_unreachable_message(exc)) from exc

    models = []
    seen = set()
    for item in data.get("models") or []:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("name") or item.get("model")
        else:
            continue
        if not name or _is_embedding_model(name):
            continue
        if name not in seen:
            seen.add(name)
            models.append(name)
    return models


def _cloud_http_error(label: str, resp: requests.Response) -> Exception:
    try:
        body = resp.json()
        error = body.get("error")
        if isinstance(error, dict):
            detail = error.get("message") or str(error)
        else:
            detail = error or body.get("message") or resp.text
    except Exception:
        detail = resp.text
    detail_text = str(detail or "")
    if resp.status_code in (401, 403) or "api key" in detail_text.lower():
        return ValueError(f"That {label} API key was rejected. Check the key and try again.")
    return ConnectionError(f"Could not list {label} models ({resp.status_code}): {detail_text}")


def _list_openai_chat_models(api_key: str, timeout: int) -> list[str]:
    resp = requests.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    if not resp.ok:
        raise _cloud_http_error("OpenAI", resp)
    skip = (
        "embedding", "whisper", "tts", "dall-e", "dall_e", "dalle",
        "audio", "transcribe", "moderation", "realtime", "image",
        "search", "sora", "davinci", "babbage", "canary",
    )
    ids = []
    for item in resp.json().get("data") or []:
        model_id = item.get("id") if isinstance(item, dict) else None
        if not model_id:
            continue
        lower = model_id.lower()
        if any(token in lower for token in skip):
            continue
        if not lower.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-")):
            continue
        ids.append(model_id)
    return _dedupe_sort(
        ids,
        preferred=("gpt-4.1", "gpt-4o", "gpt-4o-mini", "o4-mini", "o3-mini", "gpt-4.1-mini"),
    )


def _list_anthropic_chat_models(api_key: str, timeout: int) -> list[str]:
    resp = requests.get(
        "https://api.anthropic.com/v1/models",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=timeout,
    )
    if not resp.ok:
        raise _cloud_http_error("Claude (Anthropic)", resp)
    ids = []
    for item in resp.json().get("data") or []:
        model_id = item.get("id") if isinstance(item, dict) else None
        if model_id:
            ids.append(model_id)
    return _dedupe_sort(ids)


def _list_gemini_chat_models(api_key: str, timeout: int) -> list[str]:
    resp = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key},
        timeout=timeout,
    )
    if not resp.ok:
        raise _cloud_http_error("Gemini", resp)
    ids = []
    for item in resp.json().get("models") or []:
        name = (item.get("name") or "").removeprefix("models/")
        methods = item.get("supportedGenerationMethods") or []
        if not name or _is_embedding_model(name):
            continue
        if "generateContent" not in methods:
            continue
        ids.append(name)
    return _dedupe_sort(ids, preferred=("gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"))


def list_cloud_chat_models(provider: str, api_key: str, timeout: int = 15) -> list[str]:
    """List chat models for OpenAI, Anthropic, or Gemini using the given API key."""
    active = normalize_provider(provider)
    key = (api_key or "").strip()
    if not key:
        raise ValueError(missing_api_key_message(provider))
    if active == "openai":
        return _list_openai_chat_models(key, timeout)
    if active in {"anthropic", "claude"}:
        return _list_anthropic_chat_models(key, timeout)
    if active in {"gemini", "google", "google-genai"}:
        return _list_gemini_chat_models(key, timeout)
    raise ValueError(f"Unknown cloud provider: {provider}")
