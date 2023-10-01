import psutil
import logging
import socketio
from typing import Final, Dict
from asyncio import sleep as aiosleep

from utilities.messages import ExecutionResponse, ExecutionRequest, CommandOptions
from worker_manager import LOGGER_NAME
from worker_manager.monitoring.messages import WorkerMetrics
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


class WorkerManagersConnectionHandler(socketio.AsyncClientNamespace):
    NAMESPACE: Final[str] = '/worker_managers_metrics'
    INTERNAL_WORKER_NAMESPACE: Final[str] = 'tpc-workers'
    INTERVAL_BETWEEN_METRICS_IN_SEC: Final[int] = 1

    def __init__(self, internal_comms_handler: InternalControllerComms):
        super().__init__(WorkerManagersConnectionHandler.NAMESPACE)
        self._logger = logging.getLogger(LOGGER_NAME)
        self._internal_comms_handler = internal_comms_handler
        self._request_id_to_execution_response: Dict[int, ExecutionResponse] = {}

    async def send_metrics_report(self) -> None:
        cpu_stats = psutil.cpu_percent(interval=WorkerManagersConnectionHandler.INTERVAL_BETWEEN_METRICS_IN_SEC)
        memory_stats = psutil.virtual_memory()
        current_metrics = WorkerMetrics(cpu_utilization=cpu_stats, memory_used=memory_stats.used,
                                        memory_available=memory_stats.available)
        execution_request = ExecutionRequest(id=0, command=CommandOptions.GET_POD_DETAILS,
                                             arguments={
                                                 'namespace': WorkerManagersConnectionHandler.INTERNAL_WORKER_NAMESPACE})
        response = await self._internal_comms_handler.send_request(execution_request)
        await self.emit('metrics_report_result', current_metrics)

    async def on_metrics_report(self, _) -> None:
        await self.send_metrics_report()

    async def send_pc_utilization_request(self) -> None:
        await self.emit('metrics_report')

    def handle_callback(self, request_id: int, response: ExecutionResponse):
        self._request_id_to_execution_response[request_id] = response

    @staticmethod
    async def background_task(managers_connection_handler: 'WorkerManagersConnectionHandler'):
        while True:
            await managers_connection_handler.send_metrics_report()
            await aiosleep(managers_connection_handler.INTERVAL_BETWEEN_METRICS_IN_SEC)
