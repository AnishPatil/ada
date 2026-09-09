import json
from pathlib import Path


CONFIG_DIR = Path.home() / ".ada"
CONFIG_PATH = CONFIG_DIR / "llm_config.json"

DEFAULT_LLM_CONFIG = {
    "provider": "auto",
    "model": "",
    "base_url": "",
}


def _normalize_config(config):
    normalized = DEFAULT_LLM_CONFIG.copy()
    if isinstance(config, dict):
        for key in normalized:
            value = config.get(key, normalized[key])
            if value is None:
                value = ""
            normalized[key] = str(value).strip() if isinstance(value, str) else value

    provider = str(normalized.get("provider", "auto")).strip().lower()
    if provider not in {"auto", "openai", "local"}:
        provider = "auto"

    normalized["provider"] = provider
    normalized["model"] = str(normalized.get("model", "")).strip()
    normalized["base_url"] = str(normalized.get("base_url", "")).strip()
    return normalized


def load_llm_config():
    if not CONFIG_PATH.exists():
        return DEFAULT_LLM_CONFIG.copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return _normalize_config(json.load(f))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return DEFAULT_LLM_CONFIG.copy()


def save_llm_config(config):
    normalized = _normalize_config(config)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)
        f.write("\n")
    return normalized
