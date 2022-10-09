from setuptools import find_packages, setup

from mqtt4w import NAME, VERSION

setup(
    name=NAME,
    version=VERSION,
    url="https://github.com/jumper047/mqtt4w",
    author="Dmitriy Pshonko",
    author_email="jumper047@gmail.com",
    python_requires=">=3.7",
    description="Expose your linux workstation to home automation server via MQTT",
    packages=find_packages(),
    install_requires=[
        "asyncinotify == 2.0.5", 
        "asyncio-mqtt == 0.12.1",
        "ewmh == 0.1.6", 
        "pydantic == 1.9.1", 
        "python-xlib == 0.31",
        "pyxdg == 0.28",
        "pyyaml == 6.0",
    ],
    entry_points={
        "console_scripts": [
            "mqtt4w = mqtt4w.cli:main",
        ]
    },
)
