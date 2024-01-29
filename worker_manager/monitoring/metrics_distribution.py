import asyncio
import datetime
import logging
from typing import Final

import aiohttp
import psutil
from ciy_backend_libraries.api.cluster_access.v1.node_registrar import NodeDetails
from ciy_backend_libraries.messaging.main_server_to_worker_manager import WorkerMetrics

from worker_manager import LOGGER_NAME
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


class MetricsDistribution:
    INTERVAL_BETWEEN_METRICS_IN_SEC: Final[int] = 1

    def __init__(self, server_url: str, node_details: NodeDetails,
                 internal_comms_handler: InternalControllerComms):
        self._server_url = server_url
        self._node_details = node_details
        self._logger = logging.getLogger(LOGGER_NAME)
        self._internal_comms_handler = internal_comms_handler
        self._should_terminate = False
        self._event_loop = asyncio.new_event_loop()
        self._should_terminate = False

    def get_metrics(self):
        cpu_stats = psutil.cpu_percent(interval=MetricsDistribution.INTERVAL_BETWEEN_METRICS_IN_SEC)
        memory_stats = psutil.virtual_memory()

        vm_cpu_utilization, vm_cpu_allocated, vm_memory_used, vm_memory_available = self._internal_comms_handler.get_vm_usage(
            interval=MetricsDistribution.INTERVAL_BETWEEN_METRICS_IN_SEC)
        return WorkerMetrics(timestamp=datetime.datetime.utcnow().timestamp(), total_cpu_utilization=cpu_stats,
                             total_memory_used=memory_stats.used / (1024 * 1024),
                             total_memory_available=memory_stats.total / (1024 * 1024),
                             vm_cpu_utilization=vm_cpu_utilization,
                             vm_cpu_allocated=vm_cpu_allocated,
                             vm_memory_used=vm_memory_used)

    async def periodically_publish_details(self):
        while True:
            try:
                current_metrics: WorkerMetrics = await self._event_loop.run_in_executor(None, self.get_metrics)
                async with aiohttp.ClientSession() as session:
                    response = await session.put(
                        url=f'{self._server_url}/api/v1/node_metrics/{str(self._node_details)}',
                        data=current_metrics.model_dump_json(),
                        headers={"Content-Type": "application/json"})
                    if response.status != 200:
                        raise RuntimeError("Node keepalive failed!")
            except Exception as e:
                self._logger.error(f"Unexpected error: {e}.... terminating")
                self._should_terminate = True

            await asyncio.sleep(MetricsDistribution.INTERVAL_BETWEEN_METRICS_IN_SEC)

    def should_terminate(self):
        return self._should_terminate
