# RPH - Resource Process Holder

This is a simple python script utilizing uvicorn that holds processes and launches them on demand.

## What it does?

Upon a start it's a simple daemon that runs in a background and listens for connections on defined HTTP ports and
starts a destination app on-demand, forwarding the request to it. Think of it as a
"proxy that runs the service on demand".

## Use cases

I've started to play with local LLMs on my PC, which can be really resource-hungry (dense 24B in somewhat decent Q4
quant still requires a LOT of memory. And don't let me start on even bigger MoE models). In addition I've had another
GPU-VRAM-hungry app, that was running all the time (I was able to use a PC with it, but it will be a disaster if I'd
run a KoboldCPP or llama in parallel with that).

So I was looking for a way to temporarily stop that process if I'll get a request for text generation.

## The concept

This script can hold multiple ondemand and pausable process.

### Pausable process

It's a long-term process, that can run indefinitely, but will be temporarily stopped for the time
the ondemand process is started. Once the on-demand process is killed - it will be restarted.

Additionally, if the process dies outside RPH management (i.e. if it's exited by itself, killed by the system,
but not by RPH) - it will be restarted.

### On-demand process

It's a process, that will be ran upon incoming HTTP request. When the RPH gets a request - it starts the app,
defined in the configuration, which can serve the request. If service is not used for some time - it will be stopped,
allowing user to use PC resources for something else. Or pausable processes to be restarted.

## Don't we have an alternative?

Well, maybe, maybe not :) I don't know, I made this script for my own needs, not bothering with searching
for alternatives.

The closest alternative probably is a socket activation in systemd, but I needed that for Windows/macOS for example.

## Installation

Requires python3 (I was using version 3.13). As for the OS - there's no OS specific features for now, so it should work
anywhere Python is supported (at least Windows/Linux/macOS were tested).

### *nix

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Make a config.json from the config.example.json and start it:

    .venv/bin/python rph.py

### Windows

    python3 -m venv .venv
    .venv\Scripts\pip install -r requirements.txt

Make a config.json from the config.example.json and start it:

    .venv/Scripts/python rph.py

## Configuration

The configuration stored in a config.json script in the same folder as the project (for now, will be changed later).
It should be an array of objects, that define processes RPH will control.

The configuration example is in the `config.example.json` file.

### On-demand process

You can define multiple on-demand processes. Each section with different port starts it's own proxy web server
on a configured port.

| Parameter      | Example                                                                         | Description                                                                                                                                                                                                                                                                                                    |
|:---------------|:--------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| type           | `ondemand`                                                                      | The type of the process, ondemand in this case                                                                                                                                                                                                                                                                 |
| name           | `koboldcpp-mistral`                                                             | An app name, that will be launched upon getting a request on a port                                                                                                                                                                                                                                            |
| cmdline        | `/opt/koboldcpp --config Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf.kcpps` | Path to the executable with it's arguments                                                                                                                                                                                                                                                                     |
| workdir        | `/opt/llm-models`                                                               | Working directory for the process                                                                                                                                                                                                                                                                              |
| endpoint       | `http://127.0.0.1:5000`                                                         | The endpoint that the app is normally reachable                                                                                                                                                                                                                                                                |
| body_regex     | `.*Immediately stop roleplay and generate summary for the following.*`          | This is a regex pattern that the following app can accept. If null, it accepts all requests if no other app accepted the request on the same port. An experiment of mine, maybe useful                                                                                                                         |
| conflicts_with | `koboldcpp-gemma`                                                               | An array that holds a list of other on-demand process that will also be killed when this process is launched                                                                                                                                                                                                   |
| port           | `6000`                                                                          | The proxy port, which RPH will listen. This is where other apps should send their requests if they want to reach the app                                                                                                                                                                                       |
| path           | `/`                                                                             | A simple filter. This will catch any request to the path and it's children. For example, in case of KoboldCPP you may want to limit usage to the generator itself, so you can put `/v1` in it and RPH will redirect requests like `/v1/completions`, `/v1/models`, but not `/api/extra/tokencount` for example |
| timeout        | `10`                                                                            | Timeout (in minutes) after which the process will be killed and pausable process will be restarted                                                                                                                                                                                                             |

#### Same port listening

Additionally, you can make another on-demand process to serve a request on a same port if the body contains some
pattern, defined by `body_regex` parameter. In this scenario, the process with `null` `body_regex` parameter
will become a 'main' process which serves almost all requests, but other processes that has `body_regex` set
will serve some of them.

A use-case where this can be useful: main KoboldCPP instance serves all text generation requests while another
KoboldCPP instance with a tiny model serves summarization requests (i.e. a part of summarization prompt can be caught
and redirected to smaller model).

### Pausable process

Same as on-demand, you can define multiple pausable processes. This is more straightforward - just a simple cmdline
and workdir for each will do.

| Parameter      | Example                                                                | Description                                                         |
|:---------------|:-----------------------------------------------------------------------|:--------------------------------------------------------------------|
| type           | `pausable`                                                             | The type of the process, ondemand in this case                      |
| name           | `other-long-term-resource-hungry-app`                                  | An app name, that will be launched upon getting a request on a port |
| cmdline        | `/opt/other-long-term-resource-hungry-app/app argument1 argument2`     | Path to the executable with it's arguments                          |
| workdir        | `/opt/other-long-term-resource-hungry-app`                             | Working directory for the process                                   |

## API

All ports are serving a little API which controls pausable processes. You can stop and start pausable processes at
any time with it.

Just two endpoints: `/startcoordinator` and `/stopcoordinator` that will start and stop pausable processes.

NOTE: For now the way it works: if RPH gets a request for an on-demand app, it will restart pausable app after the
timeout. This will be fixed soon.

## License

Licensed under the MIT License.
See LICENSE for more information.