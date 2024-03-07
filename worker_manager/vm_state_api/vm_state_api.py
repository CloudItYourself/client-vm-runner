import asyncio

import requests
from ciy_backend_libraries.api.cluster_access.v1.node_registrar import NodeDetails
from ciy_backend_libraries.api.scheduling.v1.metrics_report import WorkerMetrics
from fastapi import APIRouter

from worker_manager.monitoring.metrics_distribution import MetricsDistribution


class VMStateAPI:
    def __init__(self, metrics_supplier: MetricsDistribution, machine_details: NodeDetails, server_url: str):
        self._metrics_supplier = metrics_supplier
        self._node_details = machine_details
        self._server_url = server_url
        self.router = APIRouter()
        self.router.add_api_route(
            "/api/v1/vm_metrics", self.vm_metrics, methods=["GET"]
        )
        self.router.add_api_route(
            "/api/v1/gracefully_terminate", self.gracefully_terminate, methods=["POST"]
        )

    async def vm_metrics(self) -> WorkerMetrics:
        return await asyncio.get_running_loop().run_in_executor(None, self._metrics_supplier.get_metrics)

    def gracefully_terminate(self) -> bool:
        url = f'{self._server_url}/api/v1/gracefully_terminate/{self._node_details}'
        res = requests.post(url)
        return res.status_code == 200
