"""Application-level errors. Messages carry identifiers only: no prompts, bodies or secrets."""

from villasanj.shared.domain.errors import VillasanjError


class ApplicationError(VillasanjError):
    """A use case could not complete for a reason the caller may handle."""


class ConfigurationError(ApplicationError):
    """Configuration is missing or inconsistent (e.g. a task routed to an unknown model)."""


class BudgetExceeded(ApplicationError):
    """An LLM call was refused because it could push spend over a job or project budget."""


class LLMError(ApplicationError):
    """Base class for LLM failures surfaced to use cases."""


class LLMOutputInvalid(LLMError):
    """The model kept returning output that does not validate against the requested schema."""


class LLMUnavailable(LLMError):
    """No configured model could serve the request (transport failures on all of them)."""
