# setup.py
from setuptools import setup, find_packages

setup(
    name="ldi_model",
    version="0.1.0",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=[],
)
