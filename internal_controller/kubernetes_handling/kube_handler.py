import logging
import os
import string
import sys
import random
import time
from typing import Final, Dict, Optional

import kubernetes
from kubernetes import client
from kubernetes.client import ApiException


class KubeHandler:
    POD_MAX_STARTUP_TIME_IN_MINUTES: Final[int] = 3
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

    def verify_pod_successful_startup(self, pod_name: str, namespace: str) -> bool:
        start_time = time.time()
        while True:
            try:
                api_response = self._kube_client.read_namespaced_pod(pod_name, namespace=namespace)
                if api_response.status.phase != 'Pending':
                    return api_response.status.phase == "Running"
                current_time = time.time()
                if current_time - start_time > KubeHandler.POD_MAX_STARTUP_TIME_IN_MINUTES * 60:
                    return False
                time.sleep(0.2)
            except ApiException as e:
                logging.error(f"Exception when calling CoreV1Api->read_namespaced_pod: {e}")
                return False

    def run_pod(self, image_name: str, version: str, environment: Dict[str, str], namespace: str) -> Optional[str]:
        generated_image_name = f'{image_name}-{self.generate_random_string(10)}'
        full_image_name = f'{image_name}:{version}'
        container = client.V1Container(
            name=generated_image_name,
            image=full_image_name,
            env=[client.V1EnvVar(name=key, value=value) for key, value in environment.items()]
        )

        pod_spec = client.V1PodSpec(
            containers=[container]
        )

        pod_manifest = client.V1Pod(
            metadata=client.V1ObjectMeta(name=generated_image_name),
            spec=pod_spec
        )

        try:
            self._kube_client.create_namespaced_pod(body=pod_manifest, namespace=namespace)
            startup_successful = self.verify_pod_successful_startup(pod_name=generated_image_name, namespace=namespace)

            if not startup_successful:
                logging.error(f"Pod creation was not successful.")
                self.delete_pod(pod_name=generated_image_name, namespace=namespace)
                return None
            return generated_image_name

        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->create_namespaced_pod: {e}")
            return None

    def create_namespace(self, namespace: str) -> bool:
        try:
            api_response = self._kube_client.create_namespace(
                client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))
            return api_response.status == "Success"
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->create_namespace: {e}")
            return False

    def delete_pod(self, pod_name: str, namespace: str) -> bool:
        try:
            api_response = self._kube_client.delete_namespaced_pod(pod_name, namespace)
            return api_response.status == "Success"
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->delete_namespaced_pod: {e}")
            return False

    def delete_all_pods_in_namespace(self, namespace: str) -> bool:
        try:
            api_response = self._kube_client.delete_collection_namespaced_pod(namespace)
            return api_response.status == "Success"
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->delete_collection_namespaced_pod: {e}")
            return False

    def get_pod_details(self, pod_name: str, namespace: str):
        # TODO check all the return values, they do not match
        # TODO ADD PROMEHEUS
        try:
            api_response = self._kube_client.read_namespaced_pod(pod_name, namespace)
            return api_response
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->read_namespaced_pod: {e}")


if __name__ == '__main__':
    xd = KubeHandler()
    xd.initialize()
    xd.delete_all_pods_in_namespace('tpc-workers')
    xd.create_namespace('tpc-workers')
    xd.run_pod("nginx", "latest", {}, 'tpc-workers')
    ret = xd._kube_client.list_pod_for_all_namespaces(watch=False)
    for i in ret.items:
        print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
