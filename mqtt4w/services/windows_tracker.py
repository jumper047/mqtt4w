import asyncio
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Set

import Xlib
from ewmh import EWMH
from mqtt4w.services.common import (
    AbstractService,
    Message,
    ServiceBaseModel,
    messages_for_states_generator,
)
from pydantic import Field

ALL_WINDOWS_SUBTOPIC = "all_windows"
ACTIVE_WINDOW_SUBTOPIC = "active_window"
FULLSCREEN_SUBTOPIC = "fullscreen"
TITLE_SUBTOPIC = "title"


@dataclass
class WindowParams:
    title: str = ""
    is_fullscreen: bool = False


class WindowsTrackerService(AbstractService):
    """Exposes information about specified windows

    Tracker topic contains subtopics which tracking
    certain windows. For example if you set up
    tracking of thhe viber call window
    windows_tracker/viber/state
    will switch to ON if window exists and OFF otherwise.
    ... but more features to come"""

    def __init__(
        self,
        *,
        subtopic: Path,
        expose_active_window: bool,
        sensors: Dict[str, List[str]]
    ):
        self.subtopic = subtopic
        self.ewmh = self.create_ewmh()
        self.expose_active_window = expose_active_window
        self.sensors = list(sensors.keys())
        self.tracked_titles = self.get_tracked_titles(sensors)

    def create_ewmh(self) -> EWMH:
        e = EWMH()
        root = e.display.screen().root
        root.change_attributes(event_mask=Xlib.X.SubstructureNotifyMask)  # type: ignore
        return e

    def get_tracked_titles(self, sensors: Dict[str, List[str]]) -> Dict[str, List[str]]:
        tracked_titles = defaultdict(lambda: [])
        for sensor_name, titles in sensors.items():
            for title in titles:
                tracked_titles[title].append(sensor_name)
        return tracked_titles

    def all_windows_titles(self) -> Set[str]:
        titles = set()
        client_list = self.ewmh.getClientList()
        for window in client_list:
            try:
                window_title = self.ewmh.getWmName(window).decode()  # type: ignore
            except Xlib.error.BadWindow:  # type: ignore
                continue
            else:
                titles.add(window_title)
        return titles

    def get_active_window_params(self) -> WindowParams:
        window = self.ewmh.getActiveWindow()
        try:
            name = self.ewmh.getWmName(window).decode()  # type: ignore
            params = self.ewmh.getWmState(window, str=True)
        except Xlib.error.BadWindow:  # type: ignore
            return WindowParams()
        is_fullscreen = "_NET_WM_STATE_FULLSCREEN" in params
        return WindowParams(name, is_fullscreen)

    def sensors_states(self):
        states = {x: False for x in self.sensors}
        for title in self.all_windows_titles():
            if title in self.tracked_titles:
                for sensor in self.tracked_titles[title]:
                    states[sensor] = True
        return states

    async def generate_message(self) -> AsyncGenerator[Message, None]:
        states = self.sensors_states()
        active_win_title = ""
        active_win_fullscreen = False
        async for message in messages_for_states_generator(states, self.subtopic):
            yield message
        loop = asyncio.get_running_loop()
        while True:
            window_params = self.get_active_window_params()
            if self.expose_active_window:
                new_active_win_title = window_params.title
                if active_win_title != new_active_win_title:
                    active_win_title = new_active_win_title
                    yield Message(
                        str(self.subtopic / ACTIVE_WINDOW_SUBTOPIC / TITLE_SUBTOPIC),
                        active_win_title,
                    )
            new_active_win_fullscreen = window_params.is_fullscreen
            if new_active_win_fullscreen != active_win_fullscreen:
                active_win_fullscreen = new_active_win_fullscreen
                yield Message(
                    str(self.subtopic / ACTIVE_WINDOW_SUBTOPIC / FULLSCREEN_SUBTOPIC),
                    "ON" if active_win_fullscreen else "OFF",
                )
            # await asyncio.to_thread(self.ewmh.display.next_event)
            await loop.run_in_executor(None, self.ewmh.display.next_event)
            new_states = self.sensors_states()
            changed = {t: v for t, v in new_states.items() if v != states[t]}
            if changed:
                async for message in messages_for_states_generator(
                    changed, self.subtopic
                ):
                    yield message
            states = new_states


class ServiceModel(ServiceBaseModel):
    _constructor = WindowsTrackerService

    subtopic: Path = Path("windows_tracker")
    expose_active_window: bool = True
    sensors: Dict[str, List[str]] = Field(default_factory=dict)
