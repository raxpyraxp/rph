import json
import logging
from asyncio import TaskGroup

import asyncio

from pausableprocessmanager import PausableProcessManager
from processcoordinator import ProcessCoordinator
from webserver import WebServer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

coordinator = ProcessCoordinator()
webservers = []

async def main():
    with open("config.json") as f:
        config = json.loads(f.read())

        async with TaskGroup() as tg:
            for entry in config:
                if entry['type'] == 'ondemand':
                    webserver = find_webserver(entry)

                    if webserver is None:
                        webserver = WebServer(coordinator, entry)
                        add_webserver(webserver)
                        tg.create_task(webserver.start())

                    webserver.add_process(entry)
                if entry['type'] == 'pausable':
                    pausable = PausableProcessManager(entry['name'], entry['cmdline'].split(" "), entry['workdir'])
                    coordinator.add(pausable)
                    tg.create_task(pausable.start_immediately())

def find_webserver(entry: dict):
    for webserver in webservers:
        if webserver.port == entry['port']:
            return webserver

    return None

def add_webserver(webserver: WebServer):
    webservers.append(webserver)

if __name__ == "__main__":
    asyncio.run(main())
