import os


def install_k3s() -> bool:
    return os.system('curl -sfL https://get.k3s.io | sh - ') == 0
