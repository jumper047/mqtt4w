import argparse
import asyncio
import logging
import os
import sys

from asyncio_mqtt import MqttError
from xdg.BaseDirectory import save_config_path

from mqtt4w import NAME
from mqtt4w.client import MQTTClient
from mqtt4w.config import load_config
from mqtt4w.manager import ServicesManager

LOG = logging.getLogger(__name__)


def parse_args():
    args_parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    args_parser.add_argument(
        "-c",
        "--config",
        default=os.path.join(save_config_path(NAME), "config.yaml"),
        help="Path to configuration file",
    )
    return args_parser.parse_args()


async def async_main():
    args = parse_args()
    config = load_config(args.config)
    logging.basicConfig(**config.logging.dict())
    LOG.info(f"Configuration file {args.config} loaded successfully")
    running = True
    while running:
        try:
            avail_topic = (
                config.base.base_topic
                / config.base.workstation_name
                / config.base.availability_subtopic
            )
            client = MQTTClient(avail_topic=avail_topic, **config.mqtt.dict())
            await client.connect()
            LOG.info("Connected to MQTT server")
            services = [cfg.create_instance() for cfg in config.services.list()]
            manager = ServicesManager(client, services, **config.base.dict())
            await manager.start_all()
        except MqttError as error:
            LOG.error(f"Error: {error}")
            logging.info("Waiting and reconnecting")
            await asyncio.sleep(60)


def main():
    sys.exit(asyncio.run(async_main()))
