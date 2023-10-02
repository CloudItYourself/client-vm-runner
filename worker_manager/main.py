import asyncio
import sys

import socketio
import socketio.exceptions

from worker_manager.configuration.configuration_manager import ConfigurationManager
from worker_manager.monitoring.worker_manager_handler import WorkerManagersConnectionHandler
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms
from worker_manager.execution.command_execution import CommandExecution


async def maintenance_loop(sio: socketio.AsyncClient,
                           internal_vm_comms: InternalControllerComms):
    while True:
        if internal_vm_comms.should_terminate:
            internal_vm_comms.terminate()
            await sio.disconnect()
            sys.exit(-1)
        await asyncio.sleep(5)


def ensure_connection(event_loop: asyncio.AbstractEventLoop, sio: socketio.AsyncClient, ip: str, port: int):
    while True:
        try:
            event_loop.run_until_complete(sio.connect(f'http://{ip}:{port}'))
            return
        except socketio.exceptions.ConnectionError as e:
            pass


def main():
    config = ConfigurationManager()
    sio = socketio.AsyncClient()
    event_loop = asyncio.get_event_loop()
    internal_vm_comms = InternalControllerComms(core_count=config.config.cpu_limit,
                                                memory_size=config.config.memory_limit,
                                                image_location=config.config.vm_image_location,
                                                qemu_installation_location=config.config.qemu_installation_location)
    worker_manager = WorkerManagersConnectionHandler(internal_vm_comms)
    sio.register_namespace(worker_manager)
    ensure_connection(event_loop, sio, config.config.server_ip, config.config.server_port)
    command_execution = CommandExecution(server_ip=config.config.server_ip, server_port=config.config.raw_ws_port,
                                         internal_comm_handler=internal_vm_comms,
                                         unique_id=sio.get_sid(WorkerManagersConnectionHandler.NAMESPACE))
    event_loop.run_until_complete(command_execution.wait_for_connection())
    sio.start_background_task(WorkerManagersConnectionHandler.background_task, worker_manager)
    sio.start_background_task(CommandExecution.background_task, command_execution)
    sio.start_background_task(maintenance_loop, sio, internal_vm_comms)

    event_loop.run_until_complete(sio.wait())


if __name__ == '__main__':
    main()
