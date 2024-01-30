import os
import pathlib
import tarfile
from tempfile import TemporaryDirectory
from typing import Final


class EnvironmentInstaller:
    K3S_BINARY_LOCATION: Final[str] = '/usr/local/bin/k3s'
    @staticmethod
    def install_tailscale() -> bool:
        if EnvironmentInstaller.check_if_tailscale_is_installed():
            os.system('tailscale down')
            return True

        tailscale_file = pathlib.Path(__file__).parent.parent / 'resources' / 'tailscale' / 'tailscale_1.56.1_amd64.tgz'
        tailscale_file_path = pathlib.Path('/usr/bin/tailscale')
        tailscaled_file_path = pathlib.Path('/usr/sbin/tailscaled')

        os.system('systemctl unmask tailscaled.service')  # precaution

        with (TemporaryDirectory() as tmp, tarfile.open(tailscale_file, mode="r:gz") as tar):
            tmp_as_path = pathlib.Path(tmp)
            tar.extractall(path=tmp)
            tailscale_file_path.write_bytes((tmp_as_path / 'tailscale_1.56.1_amd64' / 'tailscale').read_bytes())
            tailscaled_file_path.write_bytes((tmp_as_path / 'tailscale_1.56.1_amd64' / 'tailscaled').read_bytes())
            tailscale_file_path.chmod(0o777)
            tailscaled_file_path.chmod(0o777)

            systemd_base_path = pathlib.Path(r'/etc/systemd/system/tailscaled.service')
            systemd_defaults_path = pathlib.Path(r'/etc/default/tailscaled')
            systemd_base_path.write_bytes(
                (tmp_as_path / 'tailscale_1.56.1_amd64' / 'systemd' / 'tailscaled.service').read_bytes())
            systemd_defaults_path.write_bytes(
                (tmp_as_path / 'tailscale_1.56.1_amd64' / 'systemd' / 'tailscaled.defaults').read_bytes())

            ret_value = os.system('systemctl enable tailscaled') == 0 and \
                        os.system('systemctl start tailscaled') == 0 and \
                        EnvironmentInstaller.check_if_tailscale_is_installed()

            os.system('tailscale down')
            return ret_value

    @staticmethod
    def check_if_tailscale_is_installed() -> bool:
        return os.system('systemctl is-active quiet tailscaled') == 0
