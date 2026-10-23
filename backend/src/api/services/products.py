from __future__ import annotations

from collections.abc import Iterable


def observed_product(cpes: Iterable[str]) -> tuple[str, str | None] | None:
    candidates = sorted(
        (product for product in map(_cpe_product, cpes) if product is not None),
        key=lambda product: (product[1] is None, product),
    )
    return candidates[0] if candidates else None


def normalize_product_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.lower().split())[:160]
    return text or None


def _cpe_product(cpe: str) -> tuple[str, str | None] | None:
    if cpe.startswith("cpe:2.3:"):
        parts = cpe.split(":")[2:]
    elif cpe.startswith("cpe:/"):
        parts = cpe[5:].split(":")
    else:
        return None
    if len(parts) < 3 or parts[0] != "a" or not parts[1] or not parts[2]:
        return None
    version = parts[3] if len(parts) > 3 and parts[3] not in {"", "*", "-"} else None
    product = normalize_product_text(f"{parts[1]} {parts[2]}".replace("_", " "))
    if product is None:
        return None
    return product, normalize_product_text(version)

