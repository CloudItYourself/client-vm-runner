import asyncio

from ciy_backend_libraries.api.scheduling.v1.metrics_report import WorkerMetrics
from fastapi import APIRouter

from worker_manager.monitoring.metrics_distribution import MetricsDistribution


class VMStateAPI:
    def __init__(self, metrics_supplier: MetricsDistribution):
        self._metrics_supplier = metrics_supplier
        self.router = APIRouter()
        self.router.add_api_route(
            "/api/v1/vm_metrics", self.vm_metrics, methods=["GET"]
        )

    async def vm_metrics(self) -> WorkerMetrics:
        return await asyncio.get_running_loop().run_in_executor(None, self._metrics_supplier.get_metrics)
