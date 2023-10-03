import logging
import os
import string
import sys
import random
import time
from typing import Final, Dict, Optional

import kubernetes
from kubernetes import client, watch
from kubernetes.client import ApiException

from internal_controller.kubernetes_handling.kube_utility_installation_functions import install_k3s
from utilities.messages import PodDetails, NamespaceDetails


class KubeHandler:
    POD_MAX_STARTUP_TIME_IN_MINUTES: Final[int] = 6
    POD_DELETION_TIME_IN_MINUTES: Final[int] = 1
    K3S_MAX_STARTUP_TIME_IN_SECONDS: Final[int] = 360
    RELEVANT_CONFIG_FILE = '/etc/rancher/k3s/k3s.yaml' if sys.platform == 'linux' else f"{os.environ['USERPROFILE']}\\.kube\\config"

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
            if os.system('kubectl --help') == 0:
                kubernetes.config.load_kube_config(config_file=KubeHandler.RELEVANT_CONFIG_FILE)
                self._kube_client = kubernetes.client.CoreV1Api()
                self._kube_ready = True
        return self._kube_ready

    @staticmethod
    def _install_kube_env() -> bool:
        return install_k3s() and \
               os.system('kubectl --help') == 0

    @staticmethod
    def reinstall_k3s() -> bool:
        os.system('/usr/local/bin/k3s-uninstall.sh')
        return KubeHandler._install_kube_env()

    def prepare_kubernetes(self) -> bool:
        if not os.system('kubectl --help') == 0:
            KubeHandler._install_kube_env()

        kubernetes.config.load_kube_config(config_file=KubeHandler.RELEVANT_CONFIG_FILE)
        self._kube_client = kubernetes.client.CoreV1Api()
        print(f"Waiting for metrics server")
        kube_initialized = self.wait_for_metrics_server_to_start()
        print(f"Kube initialized: {kube_initialized}")
        if not kube_initialized:  # this is some wacky case
            KubeHandler.reinstall_k3s()
            kubernetes.config.load_kube_config(config_file=KubeHandler.RELEVANT_CONFIG_FILE)
            self._kube_client = kubernetes.client.CoreV1Api()
            self._kube_ready = self.wait_for_metrics_server_to_start()
            return self._kube_ready
        else:
            return True

    def verify_pod_successful_startup(self, pod_name: str, namespace: str) -> bool:
        start_time = time.time()
        while time.time() - start_time < KubeHandler.POD_MAX_STARTUP_TIME_IN_MINUTES * 60:
            try:
                api_response = self._kube_client.read_namespaced_pod(pod_name, namespace=namespace)
                if api_response.status.phase != 'Pending':
                    return api_response.status.phase == "Running"
                time.sleep(0.2)
            except ApiException as e:
                logging.error(f"Exception when calling CoreV1Api->read_namespaced_pod: {e}")
                return False
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
            restart_policy='Never',
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
            namespaces = self._kube_client.list_namespace()
            if namespace in [n.metadata.name for n in namespaces.items]:
                return True

            api_response = self._kube_client.create_namespace(
                client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))
            return api_response.status == "Success"
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->create_namespace: {e}")
            return False

    def delete_pod(self, pod_name: str, namespace: str) -> bool:
        try:
            self._kube_client.delete_namespaced_pod(pod_name, namespace)
            start_time = time.time()
            while time.time() - start_time < KubeHandler.POD_DELETION_TIME_IN_MINUTES * 60:
                try:
                    self._kube_client.read_namespaced_pod(pod_name, namespace)
                    time.sleep(0.2)
                except ApiException as e:
                    return True
            return False
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->delete_namespaced_pod: {e}")
            return False

    def delete_all_pods_in_namespace(self, namespace: str) -> bool:
        try:
            self._kube_client.delete_collection_namespaced_pod(namespace)
            start_time = time.time()
            while time.time() - start_time < KubeHandler.POD_DELETION_TIME_IN_MINUTES * 60:
                pods = self._kube_client.list_namespaced_pod(namespace)
                if len(pods.items) == 0:
                    return True
                time.sleep(0.2)
            return False
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->delete_collection_namespaced_pod: {e}")
            return False

    def get_namespace_details(self, namespace: str):
        try:
            namespace_item_details = []
            custom_object_api = client.CustomObjectsApi()
            resp = custom_object_api.list_cluster_custom_object('metrics.k8s.io', 'v1beta1', 'pods')
            for item in resp['items']:
                if item['metadata']['namespace'] == namespace:
                    current_metrics = PodDetails(pod_name=item['metadata']['name'],
                                                 cpu_utilization=item['containers'][0]['usage']['cpu'],
                                                 memory_utilization=item['containers'][0]['usage']['memory'],
                                                 measurement_window=item['window'])
                    namespace_item_details.append(current_metrics)
            return NamespaceDetails(pod_details=namespace_item_details)
        except ApiException as e:
            logging.error(f"Exception when calling CoreV1Api->list_cluster_custom_object: {e}")
            return None

    def wait_for_metrics_server_to_start(self):
        start = time.time()
        while time.time() - start < KubeHandler.K3S_MAX_STARTUP_TIME_IN_SECONDS:
            try:
                if self.get_namespace_details('kube-system') is not None:
                    return True
            except Exception as e:
                time.sleep(0.5)
                pass
        return False


if __name__ == '__main__':
    xd = KubeHandler()
    xd.initialize()
    # xd.delete_pod('nginx-guveaaqtdz', 'tpc-workers')
    # xd.delete_all_pods_in_namespace('tpc-workers')
    xd.create_namespace('tpc-workers')
    # xd.run_pod("nginxss", "latest", {}, 'tpc-workers')
    print(xd.get_namespace_details('kube-system'))
    # ret = xd._kube_client.list_pod_for_all_namespaces(watch=False)
    # for i in ret.items:
    #     print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
