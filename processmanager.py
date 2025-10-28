import asyncio
import codecs
import logging
import sys
from asyncio.subprocess import Process

import psutil


class ProcessManager:
    _cmdline: list
    _process: Process | None
    _running: bool
    _workdir: str
    _terminated_by_manager: bool

    def __init__(self, name: str, cmdline: list, workdir: str):
        self.name = name
        self._cmdline = cmdline
        self._process = None
        self._running = False
        self._workdir = workdir
        self._terminated_by_manager = False

    async def start(self):
        self._terminated_by_manager = False

        if self._process is None or self._process.returncode is not None:
            asyncio.create_task(self._run())

    async def terminate(self):
        logging.info("Terminated %s", " ".join(self._cmdline))
        self._terminated_by_manager = True

        if self._process is not None and self._process.returncode is None:
            parent = psutil.Process(self._process.pid)
            children = parent.children(recursive=True)

            self._process.terminate()

            for child in children:
                child.terminate()

            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                logging.warning("Process did not terminate, killing it.")
                self._process.kill()
                await self._process.wait()

    async def _run(self):
        # Standard implementation just runs the process
        await self._run_process()

    async def _run_process(self):
        if not self._running:
            self._running = True
            logging.info("Starting process %s", " ".join(self._cmdline))
            self._process = await asyncio.create_subprocess_exec(
                *self._cmdline,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._workdir
            )

            asyncio.create_task(self._read_stream(self._process.stdout))
            asyncio.create_task(self._read_stream(self._process.stderr))

            await self._process.wait()
            await self.process_terminated()
            self._running = False

    @staticmethod
    async def _read_stream(stream):
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        line_buffer = ""

        while True:
            chunk = await stream.read(16)
            if not chunk:
                text = decoder.decode(b"", final=True)
                if text:
                    line_buffer += text
                if line_buffer:
                    sys.stdout.write(line_buffer)
                    sys.stdout.flush()
                break

            text = decoder.decode(chunk)
            for char in text:
                line_buffer += char
                if char in ("\r", "\n"):
                    sys.stdout.write(line_buffer)
                    sys.stdout.flush()
                    line_buffer = ""

    async def process_terminated(self):
        pass
