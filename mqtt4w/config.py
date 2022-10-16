from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from pydantic import BaseModel

from mqtt4w.services.file_usage_tracker import ServiceModel as FileUsageModel
from mqtt4w.services.windows_tracker import ServiceModel as WindowTrackerModel


class ServicesModel(BaseModel):
    windows_tracker: WindowTrackerModel = WindowTrackerModel()
    file_usage: FileUsageModel = FileUsageModel()

    def list(self):
        return [self.windows_tracker, self.file_usage]


class MqttClientModel(BaseModel):
    hostname: str
    port: int = 1883
    username: str
    password: str


class MqttDiscoveryModel(BaseModel):
    enabled: bool = True
    prefix: Path = Path("homeassistant")


class MqttModel(BaseModel):
    base_topic: Path = Path("mqtt4w")
    client: MqttClientModel
    discovery: MqttDiscoveryModel = MqttDiscoveryModel()


class LoggingModel(BaseModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    filename: Optional[Path] = None


class Config(BaseModel):
    workstation_name: Optional[str] = None
    mqtt: MqttModel
    logging: LoggingModel = LoggingModel()
    services: ServicesModel = ServicesModel()


def load_config(config_path: str) -> Config:
    with open(config_path, encoding="utf-8") as c:
        config_dict = yaml.safe_load(c)
    return Config(**config_dict)
