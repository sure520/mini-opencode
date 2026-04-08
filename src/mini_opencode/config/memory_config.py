"""Memory configuration module for Mem0 and tiered memory integration.

This module provides configuration management for the Mem0 memory layer
and the tiered memory system, including default configurations and
configuration validation.
"""

from typing import Any

from mini_opencode.config import get_config_section
from mini_opencode.services.memory.types import TieredMemoryConfig

# Default Mem0 configuration
DEFAULT_MEMORY_CONFIG: dict[str, Any] = {
    'vector_store': {
        'provider': 'qdrant',
        'config': {
            'path': './.mem0/qdrant',
        },
    },
    'llm': {
        'provider': 'openai',
        'config': {
            'model': 'gpt-4.1-nano-2025-04-14',
            'temperature': 0,
        },
    },
    'embedder': {
        'provider': 'openai',
        'config': {
            'model': 'text-embedding-3-small',
        },
    },
}

# Default memory settings
DEFAULT_MEMORY_SETTINGS = {
    'enabled': True,
    'user_id': 'default_user',
    'search_limit': 5,
}


def get_memory_enabled() -> bool:
    """Get whether memory is enabled from configuration.

    Returns:
        True if memory is enabled, False otherwise.
    """
    enabled = get_config_section(['memory', 'enabled'])
    return (
        enabled if isinstance(enabled, bool) else DEFAULT_MEMORY_SETTINGS['enabled']
    )


def get_memory_user_id() -> str:
    """Get the memory user ID from configuration.

    Returns:
        The user ID for memory isolation.
    """
    user_id = get_config_section(['memory', 'user_id'])
    return (
        user_id if isinstance(user_id, str) else DEFAULT_MEMORY_SETTINGS['user_id']
    )


def get_memory_search_limit() -> int:
    """Get the memory search limit from configuration.

    Returns:
        The maximum number of memories to retrieve.
    """
    limit = get_config_section(['memory', 'search_limit'])
    return (
        limit if isinstance(limit, int) else DEFAULT_MEMORY_SETTINGS['search_limit']
    )


def get_mem0_config() -> dict[str, Any] | None:
    """Get the Mem0 configuration from config file.

    Returns:
        The Mem0 configuration dictionary, or None if not configured.
    """
    config = get_config_section(['memory', 'config'])
    return config if isinstance(config, dict) else None


def get_effective_memory_config() -> dict[str, Any]:
    """Get the effective memory configuration.

    Merges user configuration with defaults.

    Returns:
        The effective configuration dictionary.
    """
    user_config = get_mem0_config()
    if user_config is None:
        return DEFAULT_MEMORY_CONFIG.copy()

    # Deep merge user config with defaults
    effective_config = DEFAULT_MEMORY_CONFIG.copy()
    for key, value in user_config.items():
        if isinstance(value, dict) and key in effective_config:
            effective_config[key] = {**effective_config[key], **value}
        else:
            effective_config[key] = value

    return effective_config


def validate_memory_config() -> list[str]:
    """Validate the memory configuration.

    Returns:
        List of validation error messages, empty if valid.
    """
    errors: list[str] = []

    if not get_memory_enabled():
        return errors

    # Check if required API keys are set
    import os

    mem0_config = get_mem0_config()
    if mem0_config is None:
        # Using default config which requires OpenAI API key
        if not os.getenv('OPENAI_API_KEY'):
            errors.append(
                'OPENAI_API_KEY environment variable is required for Mem0 '
                'memory service. Please set it in your .env file or environment.'
            )
    else:
        # Check provider-specific requirements
        llm_config = mem0_config.get('llm', {})
        llm_provider = llm_config.get('provider', 'openai')

        if llm_provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
            errors.append(
                'OPENAI_API_KEY is required when using OpenAI as the LLM '
                'provider for Mem0.'
            )

        embedder_config = mem0_config.get('embedder', {})
        embedder_provider = embedder_config.get('provider', 'openai')

        if embedder_provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
            errors.append(
                'OPENAI_API_KEY is required when using OpenAI as the embedder '
                'provider for Mem0.'
            )

    return errors


def get_tiered_memory_enabled() -> bool:
    """Get whether tiered memory is enabled from configuration.

    Returns:
        True if tiered memory is enabled, False otherwise.
    """
    enabled = get_config_section(['memory', 'tiered', 'enabled'])
    return enabled if isinstance(enabled, bool) else False


def get_tiered_memory_config() -> TieredMemoryConfig:
    """Get the tiered memory configuration from config file.

    Reads the ``memory.tiered`` section and constructs a TieredMemoryConfig.
    Falls back to defaults if section is absent or incomplete.

    Returns:
        The TieredMemoryConfig instance.
    """
    tiered_data = get_config_section(['memory', 'tiered'])
    if isinstance(tiered_data, dict):
        return TieredMemoryConfig.from_dict(tiered_data)
    return TieredMemoryConfig()
