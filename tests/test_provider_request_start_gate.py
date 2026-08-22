from __future__ import annotations

import importlib
import math

from ocrllm.providers.provider_request_start_gate import ProviderRequestStartGate


class QuantizedWindowsClock:
    """Model GetTickCount64 plus timer-quantized sleep on Windows."""

    quantum_seconds = 0.015625

    def __init__(self) -> None:
        self.actual_seconds = self.quantum_seconds - 0.000001

    def monotonic(self) -> float:
        ticks = math.floor(self.actual_seconds / self.quantum_seconds)
        return ticks * self.quantum_seconds

    def perf_counter(self) -> float:
        return self.actual_seconds

    def sleep(self, seconds: float) -> None:
        ticks = max(1, math.ceil(seconds / self.quantum_seconds))
        self.actual_seconds += ticks * self.quantum_seconds

    def advance(self, seconds: float) -> None:
        self.actual_seconds += seconds


def test_start_gate_does_not_lose_interval_to_coarse_clock_tick(monkeypatch):
    gate_module = importlib.import_module(
        "ocrllm.providers.provider_request_start_gate"
    )
    clock = QuantizedWindowsClock()
    monkeypatch.setattr(gate_module.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(gate_module.time, "perf_counter", clock.perf_counter)
    monkeypatch.setattr(gate_module.time, "sleep", clock.sleep)
    interval_seconds = 0.03
    gate = ProviderRequestStartGate(interval_seconds)

    gate.wait(None)
    first_permit_at = clock.actual_seconds
    clock.advance(0.000002)
    gate.wait(None)
    second_permit_at = clock.actual_seconds

    assert second_permit_at - first_permit_at >= interval_seconds
