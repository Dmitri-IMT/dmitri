from __future__ import annotations

import logging

from api.services.worker import run_worker_loop


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_worker_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
