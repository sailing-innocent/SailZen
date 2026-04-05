import os
from typing import Optional


def make_gateway(
    config_provider: Optional[str] = None, config_api_key: Optional[str] = None
):
    """Build a minimal LLMGateway from environment variables or config.

    Args:
        config_provider: Optional provider name from config file (e.g., "moonshot")
        config_api_key: Optional API key from config file
    """
    try:
        from sail_server.utils.llm.gateway import LLMGateway
        from sail_server.utils.llm.providers import ProviderConfig
        from sail_server.utils.llm.available_providers import (
            DEFAULT_LLM_PROVIDER,
            DEFAULT_LLM_MODEL,
            DEFAULT_LLM_CONFIG,
        )

        provider_env_keys = {
            "moonshot": "MOONSHOT_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }

        # Default models for each provider
        default_models = {
            "moonshot": DEFAULT_LLM_MODEL
            if DEFAULT_LLM_PROVIDER == "moonshot"
            else "kimi-k2.5",
            "openai": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "google": os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash"),
            "deepseek": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
            "anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
        }

        gw = LLMGateway()
        registered = []

        # First, check if config file has explicit provider + api_key
        if config_provider and config_api_key:
            provider = config_provider.lower()
            if provider in provider_env_keys:
                model = default_models.get(provider, "")
                cfg = ProviderConfig(
                    provider_name=provider,
                    model=model,
                    api_key=config_api_key,
                    api_base=os.environ.get(f"{provider.upper()}_API_BASE"),
                )
                gw.register_provider(provider, cfg)
                registered.append(provider)
                print(f"[BotBrain] Registered provider from config: {provider}")

        # Then check environment variables for other providers
        for pname, env_key in provider_env_keys.items():
            if pname in registered:
                continue  # Skip if already registered from config
            key = os.environ.get(env_key, "")
            if key:
                cfg = ProviderConfig(
                    provider_name=pname,
                    model=default_models[pname],
                    api_key=key,
                    api_base=os.environ.get(f"{pname.upper()}_API_BASE"),
                )
                gw.register_provider(pname, cfg)
                registered.append(pname)

        if not registered:
            return None, None, None
        primary = (
            DEFAULT_LLM_PROVIDER
            if DEFAULT_LLM_PROVIDER in registered
            else registered[0]
        )
        model = default_models.get(primary, "")
        temp = float(DEFAULT_LLM_CONFIG.get("temperature", 0.7))
        return gw, primary, (model, temp)

    except Exception as exc:
        print(f"[BotBrain] Gateway init failed: {exc}")
        return None, None, None
