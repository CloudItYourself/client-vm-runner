from setuptools import setup, find_packages

setup(
    name="worker_manager",
    version="0.0.1",
    packages=find_packages(),
    install_requires=['python-socketio', 'aioboto3', 'jsonschema', 'websocket-client', 'psutil']  # Todo: load requirements.txt
)
