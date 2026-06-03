from setuptools import setup, find_packages

setup(
    name="ecello",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "google-cloud-storage",
    ],
)