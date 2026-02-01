# -*- coding: utf-8 -*-
# @file conftest.py
# @brief pytest configuration for LLM integration tests
# @author sailing-innocent
# @date 2025-02-01

import os
import sys
import pytest
import asyncio

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from sail_server.utils.env import read_env

# Load dev environment
read_env("dev")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db_session():
    """Provide a database session for testing."""
    try:
        from sail_server.db import g_db_func
        db = next(g_db_func())
        yield db
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture
def llm_config_openai():
    """OpenAI LLM configuration."""
    from sail_server.utils.llm import LLMConfig, LLMProvider
    config = LLMConfig.from_env(LLMProvider.OPENAI)
    if not config.validate():
        pytest.skip("OpenAI API key not configured")
    return config


@pytest.fixture
def llm_config_google():
    """Google LLM configuration."""
    from sail_server.utils.llm import LLMConfig, LLMProvider
    config = LLMConfig.from_env(LLMProvider.GOOGLE)
    if not config.validate():
        pytest.skip("Google API key not configured")
    return config


@pytest.fixture
def llm_config_anthropic():
    """Anthropic LLM configuration."""
    from sail_server.utils.llm import LLMConfig, LLMProvider
    config = LLMConfig.from_env(LLMProvider.ANTHROPIC)
    if not config.validate():
        pytest.skip("Anthropic API key not configured")
    return config


@pytest.fixture
def llm_config_external():
    """External (no API) LLM configuration."""
    from sail_server.utils.llm import LLMConfig, LLMProvider
    return LLMConfig(provider=LLMProvider.EXTERNAL)


@pytest.fixture
def template_manager():
    """Prompt template manager."""
    from sail_server.utils.llm import get_template_manager
    return get_template_manager()


@pytest.fixture
def sample_variables():
    """Sample variables for template testing."""
    return {
        "work_title": "测试小说",
        "chapter_range": "第1章 - 第3章",
        "chapter_contents": """
张三是镇上最年轻的铁匠，年仅二十五岁便继承了父亲的铁匠铺。
这一天，一位身着道袍的老者来到了他的铺子。
"小伙子，能帮我修一修这把剑吗？"老者取出一把古朴的长剑。
老者自称李四，是太虚门的弟子。
""",
        "known_characters": "",
        "setting_types": "item, location, organization",
    }
