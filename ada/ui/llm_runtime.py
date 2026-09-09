import os
import platform
import socket
from urllib.parse import urlparse

from openai import OpenAI
from ada.ui.runtime_preferences import load_llm_config


def is_wsl():
    if platform.system() != "Linux":
        return False

    release = platform.release().lower()
    if "microsoft" in release or "wsl" in release:
        return True

    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def runtime_platform():
    sys_name = platform.system()
    if sys_name == "Darwin":
        return "macos"
    if sys_name == "Windows":
        return "windows"
    if is_wsl():
        return "wsl"
    if sys_name == "Linux":
        return "linux"
    return sys_name.lower()


def _can_connect(base_url, timeout_s=0.20):
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname
        if host is None:
            return False

        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80

        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _clean_env(name):
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def detect_provider():
    # Accepted values: auto | local | openai
    saved_config = load_llm_config()
    provider = (_clean_env("ADA_LLM_PROVIDER") or saved_config.get("provider") or "auto").lower()
    local_base = _clean_env("ADA_LOCAL_BASE_URL") or saved_config.get("base_url") or "http://127.0.0.1:11434/v1"
    explicit_base = _clean_env("OPENAI_BASE_URL") or saved_config.get("base_url")

    if provider == "local":
        return "local", explicit_base or local_base
    if provider == "openai":
        return "openai", ""
    if explicit_base:
        return "local", explicit_base
    if _can_connect(local_base):
        return "local", local_base
    return "openai", ""


def build_client_and_model(model=None):
    provider, local_base = detect_provider()
    saved_config = load_llm_config()

    if provider == "local":
        # OPENAI_BASE_URL can override the local default if desired.
        base_url = _clean_env("OPENAI_BASE_URL") or saved_config.get("base_url") or local_base
        api_key = os.environ.get("OPENAI_API_KEY", "local")
        client = OpenAI(api_key=api_key, base_url=base_url)
        selected_model = model or _clean_env("OPENAI_MODEL") or saved_config.get("model") or "gpt-oss:20b"
        return client, selected_model

    # OPENAI cloud path
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set and local provider was not detected. "
            "Set ADA_LLM_PROVIDER=local (with local server running) or set OPENAI_API_KEY."
        )

    org = os.environ.get("OPENAI_ORG")
    kwargs = {"api_key": api_key}
    if org:
        kwargs["organization"] = org

    client = OpenAI(**kwargs)
    selected_model = model or _clean_env("OPENAI_MODEL") or saved_config.get("model") or "gpt-5.5"
    return client, selected_model


def resolve_runtime_info(model=None):
    provider, local_base = detect_provider()
    saved_config = load_llm_config()
    selected_model = model or _clean_env("OPENAI_MODEL") or saved_config.get("model")
    info = {
        "platform": runtime_platform(),
        "provider": provider,
        "model": selected_model,
        "saved_config": saved_config,
    }
    if provider == "local":
        info["base_url"] = _clean_env("OPENAI_BASE_URL") or saved_config.get("base_url") or local_base
    return info
