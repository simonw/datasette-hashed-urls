from setuptools import setup
import os

VERSION = "0.2"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="datasette-hashed-urls",
    description="Optimize Datasette performance behind a caching proxy",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Simon Willison",
    url="https://github.com/simonw/datasette-hashed-urls",
    project_urls={
        "Issues": "https://github.com/simonw/datasette-hashed-urls/issues",
        "CI": "https://github.com/simonw/datasette-hashed-urls/actions",
        "Changelog": "https://github.com/simonw/datasette-hashed-urls/releases",
    },
    license="Apache License, Version 2.0",
    classifiers=[
        "Framework :: Datasette",
        "License :: OSI Approved :: Apache Software License",
    ],
    version=VERSION,
    packages=["datasette_hashed_urls"],
    entry_points={"datasette": ["hashed_urls = datasette_hashed_urls"]},
    install_requires=["datasette"],
    extras_require={"test": ["pytest", "pytest-asyncio", "sqlite-utils"]},
    python_requires=">=3.7",
)
