from asyncio_mqtt import Client, Will

from mqtt4w.services.common.constants import OFFLINE


class MQTTClient(Client):
    def __init__(self, hostname, port, username, password, avail_topic):
        will = Will(topic=str(avail_topic), payload=OFFLINE, retain=True)
        super().__init__(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            will=will,
        )
