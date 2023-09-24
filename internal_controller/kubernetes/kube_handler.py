import os


class KubeHandler:
    def __init__(self):
        self._kube_ready = False

    @property
    def kube_ready(self) -> bool:
        if not self._kube_ready:
            self._kube_ready = os.system('kubectl --help') == 0
        return self._kube_ready

    @staticmethod
    def _install_k3s() -> bool:
        return os.system('curl -sfL https://get.k3s.io | sh - ') == 0 and os.system('kubectl --help') == 0

    def initialize(self):
        ret_code = os.system('kubectl --help')
        if ret_code == 0:
            self._kube_ready = True
        else:
            self._kube_ready = KubeHandler._install_k3s()

    def run_pod(self):
        pass

    def kill_pod(self):
        pass

    def get_util(self):
        pass
