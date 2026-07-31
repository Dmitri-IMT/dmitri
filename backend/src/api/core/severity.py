from __future__ import annotations

from typing import Literal, get_args

Severity = Literal["low", "medium", "high", "critical"]

# The single severity-domain definition, ranked in ``Severity`` declaration order
# (low=1 … critical=4). Read by host ranking, the scan-list aggregates, and the
# ``findings.severity`` check constraint. It lives here rather than beside the
# response schemas so the model layer can import the domain without depending on
# the layer above it.
SEVERITY_ORDER: dict[str, int] = {
    name: rank for rank, name in enumerate(get_args(Severity), start=1)
}
