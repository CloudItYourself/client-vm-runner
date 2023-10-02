from subprocess import Popen, PIPE
from typing import Tuple

import psutil

from worker_manager.monitoring.messages import WorkerMetrics


class QemuInitializer:
    USER: str = 'root'
    PWD: str = 'root'
    QEMU_COMMAND = r'{qemu_installation_location} -smp {cpu} -m {memory} -drive format=raw,file={image} -nic user,model=virtio-net-pci,hostfwd=tcp::{tcp_port}-:39019 --accel whpx -display none'

    def __init__(self, core_count: int, memory_size: int,
                 image_location: str, qemu_installation_location: str):
        self._image_location = image_location
        self._qemu_installation_location = qemu_installation_location
        self._core_count = core_count
        self._memory_size = memory_size
        self._vm_subprocess = None
        self._ps_process = None
        self._total_cpu_count = psutil.cpu_count()

    def run_vm(self, forwarding_port: int):
        command = QemuInitializer.QEMU_COMMAND.format(qemu_installation_location=self._qemu_installation_location,
                                                      cpu=self._core_count, memory=self._memory_size,
                                                      image=self._image_location, file=__file__,
                                                      tcp_port=forwarding_port)
        self._vm_subprocess = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE)
        self._ps_process = psutil.Process(self._vm_subprocess.pid)

    def get_vm_utilization(self, interval: int) -> Tuple[float, float, float, float]:
        cpu_stats = self._ps_process.cpu_percent(interval=interval) / self._total_cpu_count
        memory_stats = self._ps_process.virtual_memory().used / (1024 * 1024)
        return cpu_stats, self._core_count, memory_stats, self._memory_size

    def kill_vm(self):
        if self._vm_subprocess is not None:
            self._vm_subprocess.kill()
