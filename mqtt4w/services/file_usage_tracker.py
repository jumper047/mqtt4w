import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Dict, List

from asyncinotify import Inotify, Mask
from mqtt4w.services.common import (
    AbstractService,
    Message,
    Receiver,
    ServiceBaseModel,
    messages_for_states_generator,
)
from pydantic import Field


@dataclass
class Sensor:
    entities: Dict[str, bool] = field(default_factory=dict)

    @property
    def enabled(self):
        return any(self.entities.values())


class FileUsageService(AbstractService):
    """Exposes information about any file opened.

    This service is mostly usefull to track usage of the camera/microphone,
    but can be used in any other scenario."""

    # https://unix.stackexchange.com/questions/79483/can-i-query-which-processes-if-any-are-currently-accessing-the-microphone
    # https://unix.stackexchange.com/questions/344454/how-to-know-if-my-webcam-is-used-or-not
    # https://asyncinotify.readthedocs.io/en/latest/

    def __init__(self, *, subtopic, sensors):
        sensors = sensors or {}
        self.subtopic = subtopic
        self.sensors = self.get_sensors_struct(sensors)
        self.tracked_files = self.get_tracked_files(sensors)
        self.fuser_available = shutil.which("fuser")

    def get_sensors_struct(self, sensors):
        s = {x: Sensor() for x in sensors}
        for sensor, files in sensors.items():
            for file in files:
                s[sensor].entities[file] = False
        return s

    def get_tracked_files(self, sensors):
        tracked_files = {}
        for sensor_name, files in sensors.items():
            for file in files:
                tracked_files[file] = sensor_name
        return tracked_files

    async def advertise(self):
        for sensor in self.sensors:
            config_topic = self.subtopic / sensor / "config"
            state_topic = self.subtopic / sensor / "state"
            config = {"name": sensor, "state_topic": state_topic}
            payload = json.dumps(config)
            await self.publish(config_topic, payload, qos=1, retain=True)

    def already_opened(self, device):
        p = subprocess.run(["fuser", device], capture_output=True)
        return bool(p.stdout)

    def set_initial_states(self):
        for file, sensor in self.tracked_files.items():
            if self.already_opened(file):
                self.sensors[sensor].entities[file] = True

    def get_states(self):
        states = {}
        for sensor in self.sensors:
            states[sensor] = self.sensors[sensor].enabled
        return states

    async def generate_message(self) -> AsyncGenerator[Message, None]:
        inotify = Inotify()
        for f in self.tracked_files:
            inotify.add_watch(f, Mask.OPEN | Mask.CLOSE)
        self.set_initial_states()
        states = self.get_states()
        async for message in messages_for_states_generator(states, self.subtopic):
            yield message
        async for event in inotify:
            sensor = self.tracked_files[str(event.path)]
            self.sensors[sensor].entities[event.path] = event.mask == Mask.OPEN
            new_states = self.get_states()
            states_changed = {s: st for s, st in new_states.items() if st != states[s]}
            if states_changed:
                for s in states_changed:
                    sensor = self.sensors[s]
                    state_topic = self.subtopic / s / "state"
                    payload = "ON" if states_changed[s] else "OFF"
                    yield Message(str(state_topic), payload)
                states = new_states

    @property
    def message_receivers(self) -> List[Receiver]:
        return []


class ServiceModel(ServiceBaseModel):
    _constructor = FileUsageService

    subtopic: Path = Path("file_usage_tracker")
    sensors: Dict[str, List[str]] = Field(default_factory=dict)
