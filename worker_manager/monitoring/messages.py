from typing import List

from pydantic import BaseModel


class ContainerMetrics(BaseModel):
    pod_name: str
    cpu_utilization: float
    memory_used: float


class WorkerMetrics(BaseModel):
    total_cpu_utilization: float
    total_memory_used: float
    total_memory_available: float
    container_metrics: List[ContainerMetrics]
