import pathlib
import time
import socket
from subprocess import Popen, PIPE


class QemuInitializer:
    USER: str = 'root'
    PWD: str = 'root'
    QEMU_COMMAND = r'qemu-system-x86_64 -smp {cpu} -m {memory} -drive format=raw,file={image} -nic user,model=virtio-net-pci,hostfwd=tcp::{tcp_port}-:39019'

    def __init__(self, core_count: int, memory_size: int,
                 image_location=pathlib.Path(r"E:\FreeCloudProject\worker_manager\image_builder\staging\linux.img")):
        self._image_location = image_location
        self._core_count = core_count
        self._memory_size = memory_size
        self._vm_subprocess = None

    @staticmethod
    def get_available_port() -> int:
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        print(port)
        return port

    def run_vm(self):
        command = QemuInitializer.QEMU_COMMAND.format(cpu=self._core_count, memory=self._memory_size,
                                                      image=self._image_location, file=__file__,
                                                      tcp_port=QemuInitializer.get_available_port())
        self._vm_subprocess = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE)


if __name__ == '__main__':
    vm_manager = QemuInitializer(2, 3096)
    vm_manager.run_vm()
    input()
    print("waiting")
    time.sleep(100000)
