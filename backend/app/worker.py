from __future__ import annotations

import os
import time
from uuid import uuid4

from .db import claim_next_task, init_db
from .orchestrator import run_task


POLL_INTERVAL_SECONDS = float(os.environ.get("GSTACK_WORKER_POLL_INTERVAL", "1.0"))


def main() -> None:
    worker_id = f"worker_{uuid4().hex[:8]}"
    init_db()
    while True:
        task = claim_next_task(worker_id)
        if task is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        run_task(task["id"])


if __name__ == "__main__":
    main()

