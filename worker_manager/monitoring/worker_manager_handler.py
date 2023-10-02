import json
import re
from json import JSONDecodeError

import psutil
import logging
import socketio
from typing import Final, Dict, List
from asyncio import sleep as aiosleep

from pydantic import ValidationError

from utilities.messages import ExecutionResponse, ExecutionRequest, CommandOptions, NamespaceDetails, CommandResult
from worker_manager import LOGGER_NAME
from worker_manager.monitoring.messages import WorkerMetrics, ContainerMetrics, WorkerDiscoveryMessage
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


class WorkerManagersConnectionHandler(socketio.AsyncClientNamespace):
    NAMESPACE: Final[str] = '/worker_managers_metrics'
    INTERNAL_WORKER_NAMESPACE: Final[str] = 'tpc-workers'
    INTERVAL_BETWEEN_METRICS_IN_SEC: Final[int] = 1

    def __init__(self, internal_comms_handler: InternalControllerComms, unique_id: str):
        super().__init__(WorkerManagersConnectionHandler.NAMESPACE)
        self._logger = logging.getLogger(LOGGER_NAME)
        self._internal_comms_handler = internal_comms_handler
        self._request_id_to_execution_response: Dict[int, ExecutionResponse] = {}
        self._should_terminate = False
        self._unique_id = unique_id

    @property
    def should_terminate(self):
        return self._should_terminate

    async def get_kube_metrics(self, worker_metrics: WorkerMetrics) -> None:
        execution_request = ExecutionRequest(id=0, command=CommandOptions.GET_POD_DETAILS,
                                             arguments={
                                                 'namespace': WorkerManagersConnectionHandler.INTERNAL_WORKER_NAMESPACE})
        response = await self._internal_comms_handler.send_request(execution_request)
        try:
            execution_response = ExecutionResponse(**json.loads(response))
            if execution_response.result == CommandResult.SUCCESS:
                namespace_details = NamespaceDetails(**execution_response.extra)
                for worker in namespace_details.pod_details:
                    cpu_usage = float(re.findall('(?s)([\d]+)', worker.cpu_utilization)[0]) * 10E9
                    memory_usage = float(re.findall('(?s)([\d]+)', worker.memory_utilization)[0]) / 1024
                    worker_metrics.container_metrics.append(ContainerMetrics(
                        pod_name=worker.pod_name, cpu_utilization=cpu_usage, memory_used=memory_usage
                    ))
            else:
                self._logger.warning(f'Failed to get metrics, error: {execution_response.description}')

        except JSONDecodeError as e:
            self._logger.warning(f'Failed to parse response: {response}')
        except ValidationError as e:
            self._logger.warning(f'Failed to parse response: {response}')

    async def send_metrics_report(self) -> None:
        cpu_stats = psutil.cpu_percent(interval=WorkerManagersConnectionHandler.INTERVAL_BETWEEN_METRICS_IN_SEC)
        memory_stats = psutil.virtual_memory()
        current_metrics = WorkerMetrics(cpu_utilization=cpu_stats, memory_used=memory_stats.used,
                                        memory_available=memory_stats.available, container_metrics=list())
        await self.get_kube_metrics(current_metrics)
        await self.emit('metrics_report_result', current_metrics)

    async def on_metrics_report(self, _) -> None:
        await self.send_metrics_report()

    async def send_pc_utilization_request(self) -> None:
        await self.emit('metrics_report')

    def handle_callback(self, request_id: int, response: ExecutionResponse):
        self._request_id_to_execution_response[request_id] = response

    async def on_connect(self):
        await self.emit('initialization_msg', WorkerDiscoveryMessage(worker_id=self._unique_id).model_dump_json())

    async def on_disconnect(self):
        self._should_terminate = True

    @staticmethod
    async def background_task(managers_connection_handler: 'WorkerManagersConnectionHandler'):
        while True:
            await managers_connection_handler.send_metrics_report()
            await aiosleep(managers_connection_handler.INTERVAL_BETWEEN_METRICS_IN_SEC)
