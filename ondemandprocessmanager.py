import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from processmanager import ProcessManager


class OnDemandProcessManager(ProcessManager):
    _schedule_end_date: datetime
    timeout: int
    endpoint: str
    _watched: bool
    conflicts_with: List[str]
    body_regex: str

    def __init__(self, name: str, cmdline: list, workdir: str, timeout: int, endpoint: str, conflicts_with: list[str],
                 body_regex: str):
        super().__init__(name, cmdline, workdir)
        self.conflicts_with = conflicts_with
        self._schedule_end_date = datetime.now()
        self.endpoint = endpoint
        self.timeout = timeout
        self._watched = False
        self.body_regex = body_regex

    async def start(self):
        logging.info("Ondemand process start called: %s", " ".join(self._cmdline))
        self._schedule_end_date = datetime.now() + timedelta(minutes=self.timeout)
        logging.info("Rescheduling process to be terminated at %s. Process is %s",
                     self._schedule_end_date,
                     " ".join(self._cmdline))
        await super().start()

    async def _run(self):
        if not self._watched:
            asyncio.create_task(self.watch())
            await super()._run()

    async def watch(self):
        self._watched = True

        while datetime.now() < self._schedule_end_date:
            await asyncio.sleep(1)

        await self.terminate()
        self._watched = False

    async def process_terminated(self):
        if not self._terminated_by_manager:
            logging.info("Process terminated outside: %s", " ".join(self._cmdline))

        self._schedule_end_date = datetime.now()
