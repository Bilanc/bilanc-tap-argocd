#!/usr/bin/env python
from setuptools import find_packages, setup

setup(
    name="tap-argocd",
    version="0.1.0",
    description="Singer.io tap for extracting applications and sync history from Argo CD",
    author="Bilanc",
    url="https://bilanc.co",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    python_requires=">=3.10",
    install_requires=[
        "singer-python==6.3.0",
        "requests==2.33.0",
    ],
    extras_require={"dev": ["pytest", "pylint"]},
    entry_points="""
    [console_scripts]
    tap-argocd=tap_argocd:main
    """,
    packages=find_packages(exclude=["tests"]),
    package_data={"tap_argocd": ["schemas/*.json"]},
    include_package_data=True,
)
