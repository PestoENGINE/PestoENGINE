"""Abstract interface for rate limit storage backends."""

from abc import ABC, abstractmethod


class AbstractRateLimitStore(ABC):
    @abstractmethod
    def increment(self, key: str, window_seconds: int) -> int:
        """Increment the counter for key within the current window.

        Sets TTL on first call for a window; does not reset it on subsequent
        calls within the same window. Returns the updated count.
        """
