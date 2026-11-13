"""Running as a Home Assistant app: options from the Supervisor and Wyoming discovery.

Outside Home Assistant (plain Docker) there is no SUPERVISOR_TOKEN and none of this applies.
"""

import asyncio
import json
import logging
import os
import socket
import urllib.request
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

OPTIONS_PATH = Path("/data/options.json")
DISCOVERY_URL = "http://supervisor/discovery"


def supervisor_token() -> str | None:
    return os.environ.get("SUPERVISOR_TOKEN") or None


def options_args(path: Path = OPTIONS_PATH) -> list[str]:
    """Command line arguments for the app options Home Assistant writes to /data/options.json."""
    options: dict[str, Any] = json.loads(path.read_text())
    args = ["--data-dir", str(path.parent)]
    if options.get("voice"):
        args += ["--voice", str(options["voice"])]
    if options.get("sample_rate"):
        args += ["--sample-rate", str(options["sample_rate"])]
    if options.get("threads"):
        args += ["--threads", str(options["threads"])]
    if options.get("debug_logging"):
        args.append("--debug")
    return args


def _post_discovery(token: str, uri: str) -> None:
    body = json.dumps({"service": "wyoming", "config": {"uri": uri}}).encode()
    request = urllib.request.Request(
        DISCOVERY_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


async def announce(token: str, port: int, attempts: int = 60) -> None:
    """Tell Home Assistant about the server once it accepts connections.

    Home Assistant then offers to add the Wyoming integration by itself.
    """
    for _ in range(attempts):
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.5)
            continue
        writer.close()
        await writer.wait_closed()
        break
    else:
        _LOGGER.error("The server did not start listening; Home Assistant is not told about it")
        return
    # Other apps and Home Assistant reach this app by its host name.
    uri = f"tcp://{socket.gethostname()}:{port}"
    try:
        await asyncio.to_thread(_post_discovery, token, uri)
    except OSError as err:
        _LOGGER.error("Discovery message to Home Assistant failed: %s", err)
        return
    _LOGGER.info("Sent discovery information to Home Assistant (%s)", uri)
