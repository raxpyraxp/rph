import asyncio
import logging
from datetime import datetime, timedelta

from processmanager import ProcessManager


class PausableProcessManager(ProcessManager):
    _schedule_start_date: datetime | None

    def __init__(self, name: str, cmdline: list, workdir: str):
        super().__init__(name, cmdline, workdir)
        self._schedule_start_date = datetime.now()

    async def start(self):
        logging.info("Pausable process start called - starting countdown for process: %s", " ".join(self._cmdline))
        await super().start()

    async def start_immediately(self):
        self._schedule_start_date = datetime.now()
        logging.info("Starting process immediately %s", " ".join(self._cmdline))
        await self.start()

    async def _run(self):
        while datetime.now() < self._schedule_start_date:
            await asyncio.sleep(1)

        await super()._run()

    async def process_terminated(self):
        if not self._terminated_by_manager:
            logging.info("Process terminated outside, restarting: %s", " ".join(self._cmdline))
            await self.start_immediately()

    def reschedule(self, date: datetime):
        self._schedule_start_date = date
        logging.info("Scheduling process to start again at %s. Process is %s",
                     self._schedule_start_date, " ".join(self._cmdline))
