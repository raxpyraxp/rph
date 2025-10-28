import asyncio
import contextlib
import logging
import re
from typing import Callable, List

import aiohttp
import uvicorn
from aiohttp import ClientResponse

from ondemandprocessmanager import OnDemandProcessManager
from processcoordinator import ProcessCoordinator


class WebServer:
    _coordinator: ProcessCoordinator
    _params: dict
    _processes: List[OnDemandProcessManager]
    path: str
    port: int
    _endpoint: str

    def __init__(self, coordinator: ProcessCoordinator, params: dict):
        self._coordinator = coordinator
        self._params = params
        self.path = params['path']
        self._endpoint = params['endpoint']
        self.port = params['port']
        self._processes = []

    async def start(self):
        config = uvicorn.Config(self.create_app(), host="0.0.0.0", port=self._params['port'], timeout_keep_alive=2000, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    @staticmethod
    async def request_from_original(method: str, url: str, headers: dict, data: bytearray,
                                    reply_callback: Callable):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    logging.info(f"Making original server request: {url}")
                    async with session.request(
                            method=method,
                            url=url,
                            headers=headers,
                            data=data
                    ) as resp:
                        await reply_callback(resp)
                        return
            except aiohttp.ClientConnectionError:
                logging.info("Connection error occurred, still waiting for the server")
            except aiohttp.ClientResponseError as e:
                logging.info(f"Response error: {e.status} - {e.message}, still waiting for the server")
            except aiohttp.ClientConnectorError:
                logging.info("Could not connect to the host, still waiting for the server")

            await asyncio.sleep(5)

    def create_app(self):
        async def app(scope, receive, send):
            assert scope['type'] == 'http'
            body = None

            logging.info("Received request: %s %s", scope['method'], scope['path'])

            if scope['path'] == "/stopcoordinator":
                await self._coordinator.stop_all()
                await self.send_ok_status(send)

            elif scope['path'] == "/startcoordinator":
                await self._coordinator.resume_all()
                await self.send_ok_status(send)

            elif scope['path'].startswith(self.path):
                disconnect_event = asyncio.Event()

                async def disconnect_watcher():
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            logging.warning("🚫 Client disconnected.")
                            disconnect_event.set()
                            break

                watcher_task = asyncio.create_task(disconnect_watcher())

                try:
                    process: OnDemandProcessManager | None = None

                    if scope['method'] in ['POST', 'PUT', 'PATCH']:
                        body = await self.read_body(receive)
                        print(f"Request: {body.decode("utf-8")}")

                        process = self.select_process(body.decode("utf-8"))
                        await self._coordinator.stop_all(process)
                        await process.start()
                    else:
                        process = self.find_main_process()
                        await self._coordinator.stop_all(process)
                        await process.start()

                    headers = {key.decode('utf-8'): value.decode('utf-8') for key, value in scope['headers']}

                    async def reply_to_client(resp: ClientResponse):
                        client_headers = [(key.encode('utf-8'), value.strip().encode('utf-8')) for key, value in
                                          resp.headers.items()]

                        await send({
                            'type': 'http.response.start',
                            'status': resp.status,
                            'headers': client_headers,
                        })

                        async for chunk in resp.content.iter_any():
                            if disconnect_event.is_set():
                                logging.info("Stopping (client gone).")
                                break

                            print(f"Response: {chunk}", end="")
                            await send({
                                'type': 'http.response.body',
                                'body': chunk,
                                'more_body': True,
                            })

                        print("")
                        await send({
                            'type': 'http.response.body',
                            'body': b'',
                            'more_body': False,
                        })

                    await asyncio.wait_for(self.request_from_original(
                        scope['method'],
                        f"{process.endpoint}{scope['path']}",
                        headers,
                        body,
                        reply_to_client
                    ), timeout=4 * 60)

                except Exception as e:
                    logging.error(
                        f"The request timed out or failed. Consider the server unresponsive. {str(e)}")

                    await send({
                        'type': 'http.response.start',
                        'status': 500,
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': b'Error! ' + str(e).encode('utf-8'),
                    })

                finally:
                    watcher_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await watcher_task

                    await self._coordinator.resume_all()

        return app

    @staticmethod
    async def read_body(receive):
        body = b''
        more_body = True

        while more_body:
            message = await receive()
            body += message.get('body', b'')
            more_body = message.get('more_body', False)

        return body

    @staticmethod
    async def send_ok_status(send):
        await send({
            'type': 'http.response.start',
            'status': 200
        })

        await send({
            'type': 'http.response.body',
            'body': b'{"status": "ok"}'
        })

    def add_process(self, params: dict):
        process = OnDemandProcessManager(params['name'], params['cmdline'].split(" "),
                                         params['workdir'], params['timeout'], params['endpoint'],
                                         params['conflicts_with'], params['body_regex'])

        self._processes.append(process)
        self._coordinator.add(process)

    def select_process(self, body: str):
        for proc in self._processes:
            if proc.body_regex:
                pattern = re.compile(proc.body_regex)
                if pattern.match(body):
                    return proc

        return self.find_main_process()

    def find_main_process(self):
        for proc in self._processes:
            if proc.body_regex is None:
                return proc

        logging.error("No main process found, bailing!")
        return None
