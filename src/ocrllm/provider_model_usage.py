"""Cumulative call and token facts for one exact provider model."""

from __future__ import annotations

from dataclasses import dataclass

from .providers.provider_model import ProviderModel


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderModelUsage:
    """Keep cumulative trustworthy usage for one exact provider model."""

    vendor: str
    model: str
    calls: int
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        if not _is_text(self.vendor) or not _is_text(self.model):
            raise ValueError("provider-model usage identity is invalid")
        if type(self.calls) is not int or self.calls < 1:
            raise ValueError("provider-model usage calls are invalid")
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("provider-model token usage is invalid")


def build_provider_model_usage_order(
    provider_lanes: tuple[tuple[ProviderModel, ...], ...],
    *,
    slot_count: int,
) -> dict[tuple[str, str], int]:
    """Order model rows by absolute slot and lane-local candidate order."""
    order: dict[tuple[str, str], int] = {}
    lane_count = len(provider_lanes)
    for slot_index in range(slot_count):
        for provider in provider_lanes[slot_index % lane_count]:
            identity = (provider.vendor, provider.model)
            if identity not in order:
                order[identity] = len(order)
    return order


def add_provider_model_usage(
    usage: tuple[ProviderModelUsage, ...],
    *,
    provider: ProviderModel,
    calls: int,
    input_tokens: int | None,
    output_tokens: int | None,
    usage_order: dict[tuple[str, str], int],
) -> tuple[ProviderModelUsage, ...]:
    """Merge one attempt and keep completion-independent row ordering."""
    rows = list(usage)
    if calls != 0:
        for index, row in enumerate(rows):
            if (row.vendor, row.model) == (provider.vendor, provider.model):
                rows[index] = ProviderModelUsage(
                    vendor=row.vendor,
                    model=row.model,
                    calls=row.calls + calls,
                    input_tokens=_add_known(row.input_tokens, input_tokens),
                    output_tokens=_add_known(row.output_tokens, output_tokens),
                )
                break
        else:
            rows.append(
                ProviderModelUsage(
                    vendor=provider.vendor,
                    model=provider.model,
                    calls=calls,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            )
    indexed = tuple(enumerate(rows))
    return tuple(
        row
        for _, row in sorted(
            indexed,
            key=lambda item: usage_order.get(
                (item[1].vendor, item[1].model),
                len(usage_order) + item[0],
            ),
        )
    )


def _add_known(left: int | None, right: int | None) -> int | None:
    return left + right if left is not None and right is not None else None


def _is_text(value: object) -> bool:
    return type(value) is str and bool(value.strip())
