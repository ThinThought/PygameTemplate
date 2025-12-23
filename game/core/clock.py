import pygame


class GameClock:
    """Wrapper around pygame.time.Clock that filters dt spikes for physics."""

    def __init__(
        self, fps: int, *, spike_limit: float = 2.5, smoothing: float = 0.25
    ) -> None:
        self._clock = pygame.time.Clock()
        self._fps = max(1, int(fps))

        self._target_dt = 1.0 / self._fps
        self._max_dt = self._target_dt * max(1.0, float(spike_limit))
        self._smoothing = max(0.0, min(1.0, float(smoothing)))
        self._smoothed_dt = self._target_dt
        self._last_raw_dt = self._target_dt

    @property
    def last_raw_dt(self) -> float:
        """Returns the last unfiltered dt (seconds)."""
        return self._last_raw_dt

    def tick(self) -> float:
        raw = self._clock.tick(self._fps) / 1000.0
        self._last_raw_dt = raw

        if raw <= 0:
            return self._smoothed_dt

        clamped = min(raw, self._max_dt)
        if self._smoothing <= 0.0:
            self._smoothed_dt = clamped
        else:
            alpha = self._smoothing
            self._smoothed_dt += (clamped - self._smoothed_dt) * alpha

        return self._smoothed_dt
