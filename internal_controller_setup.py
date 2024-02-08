from setuptools import setup, find_packages

setup(
    name="internal_controller",
    version="0.0.1",
    packages=find_packages(),
    package_data={
        '': ['**/*.tgz'],
    },install_requires=['pydantic', 'websockets', 'pycryptodome', 'requests', 'aiohttp==3.9.2']
)
