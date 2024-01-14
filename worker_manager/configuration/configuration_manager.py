import json
import os
import sys
import pathlib
from json import JSONDecodeError
from typing import Final
from pydantic import BaseModel, ValidationError
from tpc_backend_libraries.general.singleton import Singleton


class ConfigurationData(BaseModel):
    server_ip: str
    server_port: int
    raw_ws_port: int

    server_url: str
    cpu_limit: int
    memory_limit: int
    qemu_installation_location: str
    vm_image_location: str


class ConfigurationManager(metaclass=Singleton):
    CONFIGURATION_PATH: Final[str] = '/etc/tpc-worker-manager/config.json' if sys.platform == 'linux ' else \
        f"{os.environ['USERPROFILE']}\\.tpc-worker-manager\\config.json"

    def __init__(self):
        self._configuration_path = pathlib.Path(ConfigurationManager.CONFIGURATION_PATH)
        if not self._configuration_path.is_file():
            self._set_default_configurations()
        self._config = self.get_configurations()

    @property
    def config(self):
        return self._config

    def _set_default_configurations(self):
        self._configuration_path.parent.mkdir(parents=True, exist_ok=True)
        self._configuration_path.write_text(
            ConfigurationData(server_ip='127.0.0.1', server_port=8080, raw_ws_port=9090, cpu_limit=4,
                              memory_limit=4096,
                              qemu_installation_location='undefined',
                              vm_image_location='undefined',
                              server_url='127.0.0.1').model_dump_json(indent=4))

    def get_configurations(self) -> ConfigurationData:
        try:
            return ConfigurationData(**json.loads(self._configuration_path.read_text()))
        except ValidationError as e:
            # todo log
            raise
        except JSONDecodeError as e:
            # todo log
            raise
