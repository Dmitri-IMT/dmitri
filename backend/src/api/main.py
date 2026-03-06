from __future__ import annotations

from fastapi import FastAPI

from api.schemas import ScanIngestResponse, ScanResult

app = FastAPI(title="Vulnerability Scanner Backend", version="0.1.0")


@app.get("/", summary="Health probe")
def read_health() -> dict[str, str]:
    """Simple endpoint used for uptime checks."""

    return {"status": "ok"}


@app.post(
    "/scans",
    summary="Receive scan payloads",
    response_model=ScanIngestResponse,
)
def ingest_scan(scan: ScanResult) -> ScanIngestResponse:
    """Accept scan payloads from the hardware agent."""

    return ScanIngestResponse(
        message="scan received successfully",
        scan_id=scan.scan_id,
        devices_received=len(scan.devices),
    )
