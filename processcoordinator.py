from datetime import datetime, timedelta

from ondemandprocessmanager import OnDemandProcessManager
from pausableprocessmanager import PausableProcessManager
from processmanager import ProcessManager


class ProcessCoordinator:
    pausable_processes: list[PausableProcessManager]
    ondemand_processes: list[OnDemandProcessManager]

    def __init__(self):
        self.pausable_processes = []
        self.ondemand_processes = []

    def add(self, process: ProcessManager):
        if isinstance(process, PausableProcessManager):
            self.pausable_processes.append(process)

        if isinstance(process, OnDemandProcessManager):
            self.ondemand_processes.append(process)

    def remove(self, process: ProcessManager):
        if isinstance(process, PausableProcessManager):
            self.pausable_processes.remove(process)

        if isinstance(process, OnDemandProcessManager):
            self.ondemand_processes.remove(process)

    async def stop_all(self, requesting_process: OnDemandProcessManager | None=None):
        await self.stop_all_pausable(requesting_process)

        if requesting_process:
            await self.stop_all_ondemand(requesting_process)

    async def stop_all_pausable(self, requesting_process: OnDemandProcessManager | None=None):
        for proc in self.pausable_processes:
            await proc.terminate()

            if requesting_process:
                proc.reschedule(datetime.now() + timedelta(minutes=requesting_process.timeout))

    async def stop_all_ondemand(self, requesting_process: OnDemandProcessManager):
        for proc in self.ondemand_processes:
            if proc.name in requesting_process.conflicts_with:
                await proc.terminate()

    async def resume_all(self):
        for proc in self.pausable_processes:
            await proc.start()
