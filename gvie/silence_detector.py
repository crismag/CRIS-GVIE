"""Silence detection based on consecutive non-speech frame counting."""


class SilenceDetector:
    """Determines when the user has stopped speaking.

    Counts consecutive non-speech frames and returns ``True`` once the
    accumulated silence exceeds *silence_timeout* seconds.
    """

    def __init__(
        self,
        silence_timeout: float = 1.5,
        sample_rate: int = 16_000,
        chunk_size: int = 512,
    ) -> None:
        self.silence_timeout = silence_timeout
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        # Number of consecutive silent chunks that constitute a timeout.
        self._threshold_chunks = int(silence_timeout * sample_rate / chunk_size)
        self._silent_chunks = 0

    def update(self, is_speech: bool) -> bool:
        """Update internal state with the latest VAD result.

        Returns ``True`` when accumulated silence has exceeded the timeout.
        Resets the counter on any speech frame.
        """
        if is_speech:
            self._silent_chunks = 0
            return False
        self._silent_chunks += 1
        return self._silent_chunks >= self._threshold_chunks

    def reset(self) -> None:
        """Reset the silence counter (e.g. at the start of a new turn)."""
        self._silent_chunks = 0
