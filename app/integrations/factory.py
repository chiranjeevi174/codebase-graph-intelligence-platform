"""PRProviderFactory for resolving GitHub and GitLab integration provider instances."""

from app.config.settings import Settings, get_settings
from app.integrations.base import PRProvider
from app.integrations.github import GitHubProvider
from app.integrations.gitlab import GitLabProvider


class PRProviderFactory:
    """Factory creating provider instances based on provider type ('github' or 'gitlab')."""

    _providers: dict[str, type[PRProvider]] = {
        "github": GitHubProvider,
        "gitlab": GitLabProvider,
    }

    @classmethod
    def get_provider(cls, provider_type: str, settings: Settings | None = None) -> PRProvider:
        """Instantiate provider by type string."""
        pt_clean = (provider_type or "").strip().lower()
        if pt_clean not in cls._providers:
            raise ValueError(f"Unsupported PR provider '{provider_type}'. Supported providers: {list(cls._providers.keys())}")
        
        provider_cls = cls._providers[pt_clean]
        return provider_cls(settings=settings or get_settings())

    @classmethod
    def register_provider(cls, name: str, provider_cls: type[PRProvider]):
        """Register a custom PR provider implementation."""
        cls._providers[name.lower()] = provider_cls
