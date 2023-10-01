import argparse
import pathlib
from typing import NamedTuple


class WorkerManagerConfigurations(NamedTuple):
    server_ip: str
    server_socket_io_port: int
    server_ws_port: int

    execution_server_ip: str
    execution_server_port: int

    image_location: pathlib.Path
    cpu_count: int
    memory_in_mb: int

def get_configurations():
    pass

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='worker manager',
        description='In charge of the worker manager and vm configuration')
    parser.add_argument('--configuration-file-path', type=str, required=True)
    return parser.parse_args().configuration_file_path
