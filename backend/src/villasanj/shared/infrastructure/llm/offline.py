"""A provider for the offline demo (``LLM__PROVIDER=offline``, ROADMAP M11 criterion 1).

It never opens a connection: every call is refused, so only answers already in the LLM cache
are served (the cache sits before the provider in the chain). It replays the cache of the
provider that wrote it, because cache keys include the provider's name. A refused call may fall
back, since a fallback model's answer may be the cached one; it is never retried.
"""

from __future__ import annotations

from villasanj.shared.application.llm.ports import (
    ProviderCall,
    ProviderRejectedError,
    ProviderResult,
)


class OfflineProvider:
    name = "offline"

    def __init__(self, replays: str) -> None:
        self.replays = replays  # the provider whose cached answers are served

    async def complete(self, call: ProviderCall) -> ProviderResult:
        raise ProviderRejectedError("offline-not-cached")

    async def ready(self) -> bool:
        return True  # nothing to reach: the cache is the database
