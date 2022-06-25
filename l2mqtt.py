from dataclasses import dataclass, field
from asyncinotify import Inotify, Mask
import subprocess
import shutil
import json
from typing import List, Dict, Union, Any
from dataclasses import asdict, dataclass, field
from  asyncio_mqtt import Client, MqttError
import asyncio
from ewmh import EWMH
import Xlib
from collections import defaultdict

MQTT_SERVER = "192.168.1.200"
USERNAME = "homeassistant"
PASSWORD = "owlsarenot"
RECONNECT_INTERVAL = 3

 
@dataclass
class WindowsTrackerConfig:
    sensors: Dict[str, List[str]]

@dataclass
class FileUsageTrackerConfig:
    sensors: Dict[str, List[str]]

@dataclass
class MqttConfig:
    server: str
    port: int
    username: str
    password: str

@dataclass
class ServicesConfig:
    windows_tracker: WindowsTrackerConfig
    file_usage: FileUsageTrackerConfig

@dataclass
class Config:
    mqtt: MqttConfig
    services: ServicesConfig


config = Config(
    MqttConfig(
        MQTT_SERVER, 
        1883,
        USERNAME,
        PASSWORD
    ),
    ServicesConfig(
        WindowsTrackerConfig(
            sensors={"video_conference": ["Zoom Meeting",
                                                 "Телемост"]}
        ),
        FileUsageTrackerConfig(
            sensors={"camera": ['/dev/video0']}
        )
    )
)

class Service:
    """Abstract class for service"""

    def get_topic(self, *topic_path):
        return "/".join([self.topic, *topic_path])

    async def publish_states(self, states):
        for name, state in states.items():
            state_topic = self.get_topic(name, "state")
            payload = 'ON' if state else 'OFF'
            await self.client.publish(state_topic, payload, qos=1)


@dataclass
class Sensor:
    entities: Dict[str, bool] = field(default_factory=dict)

    @property
    def enabled(self):
        return any(self.entities.values())

class FileUsageService(Service):
    """Exposes information about any file opened.

    This service is mostly usefull to track usage of the camera/microphone,
    but can be used in any other scenario."""

# https://unix.stackexchange.com/questions/79483/can-i-query-which-processes-if-any-are-currently-accessing-the-microphone
# https://unix.stackexchange.com/questions/344454/how-to-know-if-my-webcam-is-used-or-not
# https://asyncinotify.readthedocs.io/en/latest/
    SENSOR_TYPE = "binary_sensor"

    def __init__(self,
                 client,
                 topic,
                 *,
                 sensors
                 ):
        self.client = client
        self.topic = topic
        self.sensors = self.get_sensors_struct(sensors)
        self.tracked_files = self.get_tracked_files(sensors)
        self.fuser_available = shutil.which('fuser')

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
            config_topic = self.get_topic(sensor, 'config')
            state_topic = self.get_topic(sensor, 'state')
            config = {
                'name': sensor,
                'state_topic': state_topic
            }
            payload = json.dumps(config)
            await self.client.publish(config_topic, payload, qos=1, retain=True)


    def already_opened(self, device):
        p = subprocess.run(['fuser', device], capture_output=True)
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

    async def start(self):
        inotify = Inotify()
        for f in self.tracked_files:
            inotify.add_watch(f, Mask.OPEN | Mask.CLOSE)
        self.set_initial_states()
        states = self.get_states()
        await self.publish_states(states)
        async for event in inotify:
            sensor = self.tracked_files[str(event.path)]
            self.sensors[sensor].entities[event.path] = event.mask == Mask.OPEN
            new_states = self.get_states()
            states_changed = {s: st for s, st in new_states.items() if st != states[s]}
            if states_changed:
                await self.publish_states(states_changed)
                states = new_states


class WindowsTrackerService(Service):
    """Exposes information about specified windows

    Tracker topic contains subtopics which tracking
    certain windows. For example if you set up
    tracking of thhe viber call window
    windows_tracker/viber/state
    will switch to ON if window exists and OFF otherwise.
    ... but more features to come"""

    SENSOR_TYPE = "binary_sensor"

    def __init__(
            self,
            client,
            topic,
            *,
            sensors=None
    ):
        self.topic = topic
        self.ewmh = self.create_ewmh()
        self.client = client
        self.sensors = list(sensors.keys())
        self.tracked_titles = self.get_tracked_titles(sensors)

    def create_ewmh(self):
        e = EWMH()
        root = e.display.screen().root
        root.change_attributes(event_mask=Xlib.X.SubstructureNotifyMask)
        return e

    def get_tracked_titles(self, sensors):
        tracked_titles = defaultdict(lambda: [])
        for sensor_name, titles in sensors.items():
            for title in titles:
                tracked_titles[title].append(sensor_name)
        return tracked_titles
            
    async def advertise(self):
        for sensor in self.sensors:
            config_topic = self.get_topic(sensor, 'config')
            state_topic = self.get_topic(sensor, 'state')
            config = {
                'name': sensor,
                'state_topic': state_topic
            }
            payload = json.dumps(config)
            await self.client.publish(config_topic, payload, qos=1, retain=True)

    def all_windows_titles(self):
        titles = set()
        client_list = self.ewmh.getClientList()
        for window in client_list:
            try:
                window_title = self.ewmh.getWmName(window).decode()
            except Xlib.error.BadWindow:
                continue
            else:
                titles.add(window_title)
        return titles

    def sensors_states(self):
        states = {x: False for x in self.sensors}
        for title in self.all_windows_titles():
            if title in self.tracked_titles:
                for sensor in self.tracked_titles[title]:
                    states[sensor] = True
        return states

    async def start(self):
        await self.advertise()
        states = self.sensors_states()
        await self.publish_states(states)
        loop = asyncio.get_running_loop()
        while True:
            # await asyncio.to_thread(self.ewmh.display.next_event)
            await loop.run_in_executor(None, self.ewmh.display.next_event)
            new_states = self.sensors_states()
            changed = {t: v for t, v in new_states.items() if v != states[t]}
            if changed:
                await self.publish_states(changed)
            states = new_states


constructors = {
    "windows_tracker": WindowsTrackerService,
    "file_usage": FileUsageService
}


async def start_services(client):
    
    serv_conf = asdict(config.services)
    services = [constructors[name](client, "mqtt4w", **conf) for name, conf in serv_conf.items()]
    tasks = set()
    for service in services:
        tasks.add(asyncio.create_task(service.start()))
    await asyncio.gather(*tasks)


async def main():
    # Run the advanced_example indefinitely. Reconnect automatically
    # if the connection is lost.
    reconnect_interval = 3  # [seconds]
    while True:
        try:
            client = Client(MQTT_SERVER, username=USERNAME, password=PASSWORD)
            await client.connect()
            await start_services(client)
        except MqttError as error:
            print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        finally:
            await asyncio.sleep(reconnect_interval)
 

asyncio.run(main())

