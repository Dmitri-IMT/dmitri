"""CLI entry point for the hardware agent scan pipeline."""

from __future__ import annotations

import argparse
import logging

from agent.config import load_settings
from agent.scanner.pipeline import ScanOrchestrator


def main() -> None:
    """Run the scan pipeline and write the normalized payload to disk."""

    parser = argparse.ArgumentParser(
        description="Run the hardware-agent Nmap pipeline."
    )
    parser.add_argument("--subnet", help="Override the configured scan subnet.")
    parser.add_argument(
        "--mode",
        choices=("quick", "standard", "full"),
        help="Override the configured scan mode.",
    )
    parser.add_argument("--output", help="Write the resulting payload to this path.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings().with_overrides(
        scan_subnet=args.subnet,
        scan_mode=args.mode,
        output_path=args.output,
    )
    orchestrator = ScanOrchestrator(settings)
    try:
        payload = orchestrator.run()
    except KeyboardInterrupt:
        partial_payload = orchestrator.build_partial_payload(
            interrupted_stage=orchestrator.current_stage,
        )
        output_path = orchestrator.write_payload(partial_payload)
        print(
            "Scan cancelled by user. A partial payload was written with "
            f"{len(partial_payload.devices)} devices and "
            f"{len(partial_payload.findings)} findings."
        )
        print(f"Partial payload written to {output_path}")
        raise SystemExit(130)

    output_path = orchestrator.write_payload(payload)
    print(
        f"Scan completed for {payload.subnet} with "
        f"{len(payload.devices)} devices and {len(payload.findings)} findings."
    )
    print(f"Payload written to {output_path}")


if __name__ == "__main__":
    main()
