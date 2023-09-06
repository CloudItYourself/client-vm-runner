import psutil
import logging
import socketio
from typing import Final
from asyncio import sleep as aiosleep
from worker_manager import LOGGER_NAME
from worker_manager.monitoring.messages import WorkerMetrics


class WorkerManagersConnectionHandler(socketio.AsyncClientNamespace):
    NAMESPACE: Final[str] = '/worker_managers'
    INTERVAL_BETWEEN_METRICS_IN_SEC: Final[int] = 1

    def __init__(self):
        super().__init__(WorkerManagersConnectionHandler.NAMESPACE)
        self._logger = logging.getLogger(LOGGER_NAME)

    async def send_metrics_report(self) -> None:
        cpu_stats = psutil.cpu_percent(interval=WorkerManagersConnectionHandler.INTERVAL_BETWEEN_METRICS_IN_SEC)
        memory_stats = psutil.virtual_memory()
        current_metrics = WorkerMetrics(cpu_utilization=cpu_stats, memory_used=memory_stats.used,
                                        memory_available=memory_stats.available)
        await self.emit('metrics_report_result', current_metrics)

    async def on_metrics_report(self, _) -> None:
        await self.send_metrics_report()

    async def send_pc_utilization_request(self) -> None:
        await self.emit('metrics_report')

    @staticmethod
    async def background_task(managers_connection_handler: 'WorkerManagersConnectionHandler'):
        while True:
            await managers_connection_handler.send_metrics_report()
            await aiosleep(managers_connection_handler.INTERVAL_BETWEEN_METRICS_IN_SEC)
