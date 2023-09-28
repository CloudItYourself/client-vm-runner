import os


def install_k3s() -> bool:
    return os.system('curl -sfL https://get.k3s.io | sh - ') == 0


def install_kube_state_metrics() -> bool:
    return os.system('git clone https://github.com/kubernetes/kube-state-metrics.git') == 0 and \
        os.system('kubectl apply -f kube-state-metrics/examples/standard') == 0
