import os


def install_k3s() -> bool:
    return os.system('curl -sfL https://get.k3s.io | sh - ') == 0


def install_metrics_server() -> bool:
    return os.system('kubectl apply -f /usr/src/kube-deployments/metrics-server.yaml') == 0
