import asyncio

import socketio

from worker_manager.monitoring.worker_manager_handler import WorkerManagersConnectionHandler
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


def main():
    # sio = socketio.AsyncClient()
    # worker_manager_task = WorkerManagersConnectionHandler()
    # sio.register_namespace(worker_manager_task)
    # while True:
    # await sio.connect('http://localhost:8080')
    # sio.start_background_task(WorkerManagersConnectionHandler.background_task, worker_manager_task)
    # await sio.wait()
    worker_comms = InternalControllerComms(core_count=4, memory_size=4000)
    worker_manager_task = WorkerManagersConnectionHandler(worker_comms)
    while True:
        asyncio.get_event_loop().run_until_complete(asyncio.wait_for(asyncio.sleep(10), 10))

if __name__ == '__main__':
    main()
