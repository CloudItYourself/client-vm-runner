import asyncio

import socketio

from worker_manager.monitoring.metrics_reporter import WorkerManagersConnectionHandler


async def main():
    sio = socketio.AsyncClient()
    worker_manager_task = WorkerManagersConnectionHandler()
    sio.register_namespace(worker_manager_task)
    await sio.connect('http://localhost:8080')
    sio.start_background_task(WorkerManagersConnectionHandler.background_task, worker_manager_task)
    await sio.wait()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
