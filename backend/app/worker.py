from __future__ import annotations

import logging
import os
import time
from uuid import uuid4

from .db import claim_next_task, init_db
from .orchestrator import run_task


POLL_INTERVAL_SECONDS = float(os.environ.get("GSTACK_WORKER_POLL_INTERVAL", "1.0"))
logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker_id = f"worker_{uuid4().hex[:8]}"
    logger.info("worker starting id=%s", worker_id)
    init_db()
    while True:
        task = claim_next_task(worker_id)
        if task is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        logger.info("claimed task id=%s status=%s stage=%s", task["id"], task["status"], task["current_stage"])
        run_task(task["id"])


if __name__ == "__main__":
    main()
