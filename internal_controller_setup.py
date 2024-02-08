import pathlib

from setuptools import setup, find_packages


def parse_requirements(filename: pathlib.Path):
    """load requirements from a pip requirements file"""
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]


setup(
    name="internal_controller",
    version="0.0.1",
    packages=find_packages(),
    package_data={
        '': ['**/*.tgz'],
    },
    install_requires=parse_requirements(pathlib.Path(__file__).parent / "requirements.txt")
)
