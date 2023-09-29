from typing import TypedDict


class WorkerMetrics(TypedDict):
    cpu_utilization: float
    memory_used: float
    memory_available: float

