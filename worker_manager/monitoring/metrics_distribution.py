import asyncio
import datetime
import logging
from typing import Final

import psutil
from ciy_backend_libraries.api.cluster_access.v1.node_registrar import NodeDetails
from ciy_backend_libraries.api.scheduling.v1.metrics_report import WorkerMetrics

from worker_manager import LOGGER_NAME
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


class MetricsDistribution:
    INTERVAL_BETWEEN_METRICS_IN_SEC: Final[int] = 0.1

    def __init__(self, internal_comms_handler: InternalControllerComms):
        self._internal_comms_handler = internal_comms_handler

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
                             vm_memory_used=vm_memory_used,
                             vm_memory_available=vm_memory_available)
