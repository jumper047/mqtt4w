import asyncio
import ctypes
import json
import logging
import struct
from enum import IntEnum
from pathlib import Path
from typing import AsyncGenerator, List

from mqtt4w.services.common.baseservice import BaseService
from mqtt4w.services.common.config import ServiceBaseModel
from mqtt4w.services.common.constants import OFF, ON
from mqtt4w.services.common.discovery import (
    SUBTOPIC_TEMPLATE,
    DiscoveryEntity,
    EntityType,
    generate_availability_config,
    generate_device_cfg,
    generate_subconfig,
)
from mqtt4w.services.common.structures import Message
from pydantic import PositiveInt

LIBXEXT_NAME = "libXext.so"


LOG = logging.getLogger(__name__)


class DPMS(IntEnum):
    NONE = -2
    FAIL = -1
    ON = 0
    STANDBY = 1
    SUSPEND = 2
    OFF = 3


class DPMSService(BaseService):
    def __init__(self, subtopic, display, check_interval):
        super().__init__()
        self.incoming_msg = asyncio.Queue()
        self.outgoing_msg = asyncio.Queue()
        self.subtopic = subtopic
        self.state_topic = subtopic / "state"
        self.display = display
        self.libXext = self.get_libxext()
        self.check_interval = check_interval
        self.register_sender_gen(self.display_states)
        self.register_discoverables()

    def register_discoverables(self):
        dpms_id = "dpms_state"
        subconfig = generate_subconfig(
            "DPMS state",
            state_topic=str(self.state_topic),
            payload_on=ON,
            payload_off=OFF,
        )
        self.register_discoverable(EntityType.BINARY_SENSOR, dpms_id, subconfig)

    def get_libxext(self):
        try:
            ctypes.cdll.LoadLibrary(LIBXEXT_NAME)
            return ctypes.CDLL(LIBXEXT_NAME)
        except OSError:
            LOG.error("Please install libXext package!")

    def dpms_state(self):
        state = 1
        display = self.display.encode("ascii")
        display_name = ctypes.c_char_p()
        display_name.value = display
        self.libXext.XOpenDisplay.restype = ctypes.c_void_p  # type: ignore
        display = ctypes.c_void_p(self.libXext.XOpenDisplay(display_name))  # type: ignore
        dummy1_i_p = ctypes.create_string_buffer(8)
        dummy2_i_p = ctypes.create_string_buffer(8)
        if display.value:
            if self.libXext.DPMSQueryExtension(  # type: ignore
                display, dummy1_i_p, dummy2_i_p
            ) and self.libXext.DPMSCapable(  # type: ignore
                display
            ):
                onoff_p = ctypes.create_string_buffer(1)
                state_p = ctypes.create_string_buffer(2)
                if self.libXext.DPMSInfo(display, state_p, onoff_p):  # type: ignore
                    onoff = struct.unpack("B", onoff_p.raw)[0]
                    if onoff:
                        state = struct.unpack("H", state_p.raw)[0]
            self.libXext.XCloseDisplay(display)  # type: ignore
        return state

    async def display_states(self):
        state = self.dpms_state()
        yield Message(self.state_topic, OFF if state else ON)
        while True:
            new_state = self.dpms_state()
            if state != new_state:
                state = new_state
                yield Message(str(self.state_topic), OFF if state else ON)
            await asyncio.sleep(self.check_interval)


class ServiceModel(ServiceBaseModel):
    _constructor = DPMSService

    subtopic: Path = Path("dpms")
    display: str = ":1"
    check_interval: PositiveInt = 5
