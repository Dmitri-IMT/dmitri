from __future__ import annotations

import logging
import threading

from api.core.config import get_settings
from api.services.ai.groq import ai_is_available
from api.services.worker import run_ai_worker_loop, run_worker_loop


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if ai_is_available(get_settings()):
        threading.Thread(target=run_ai_worker_loop, daemon=True).start()
    run_worker_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
