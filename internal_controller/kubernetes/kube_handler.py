import os
import string
import sys
import random
from typing import Final, Dict, Optional

import kubernetes
from kubernetes import client


class KubeHandler:
    LINUX_K3S_CONFIG_LOCATION: Final[str] = '/etc/rancher/k3s/k3s.yaml'
    WINDOWS_MINIKUBE_CONFIG_LOCATION: Final[str] = f"{os.environ['USERPROFILE']}\\.kube\\config"
    RELEVANT_CONFIG_FILE = LINUX_K3S_CONFIG_LOCATION if sys.platform == 'linux' else WINDOWS_MINIKUBE_CONFIG_LOCATION

    def __init__(self):
        self._kube_ready = False
        self._kube_client: Optional[kubernetes.client.CoreV1Api] = None

    @staticmethod
    def generate_random_string(length: int) -> str:
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(length))

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

        if self._kube_ready:
            kubernetes.config.load_kube_config(config_file=KubeHandler.RELEVANT_CONFIG_FILE)
            self._kube_client = kubernetes.client.CoreV1Api()

    def run_pod(self, image_name: str, version: str, environment: Dict[str, str]) -> str:
        generated_image_name = f'{image_name}-{self.generate_random_string(10)}'
        pod = client.V1Pod(metadata=client.V1ObjectMeta(name=generated_image_name), spec=client.V1PodSpec(containers=[
            client.V1Container(name=generated_image_name, image=f'{image_name}:{version}')]))

        self._kube_client.create_namespaced_pod(body=pod, namespace="default")
        return generated_image_name

    def kill_pod(self):
        pass

    def get_util(self):
        pass


if __name__ == '__main__':
    xd = KubeHandler()
    xd.initialize()
    ret = xd._kube_client.list_pod_for_all_namespaces(watch=False)
    xd.run_pod("nginx", "latest", {})
    for i in ret.items:
        print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))

