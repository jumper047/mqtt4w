import yaml
from typing import Any, Dict, Optional, Literal
from pathlib import Path

from mqtt4w.services.windows_tracker import ServiceModel as WindowTrackerModel
from mqtt4w.services.file_usage_tracker import ServiceModel as FileUsageModel
from pydantic import BaseModel


class ServicesModel(BaseModel):
    windows_tracker: WindowTrackerModel = WindowTrackerModel()
    file_usage: FileUsageModel = FileUsageModel()


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

class Config(BaseModel):
    workstation_name: str
    mqtt: MqttModel
    logging_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    services: ServicesModel = ServicesModel()


def load_config(config_path: str) -> Config:
    with open(config_path, encoding='utf-8') as c:
        config_dict = yaml.safe_load(c)
    return Config(**config_dict)
