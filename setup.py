from setuptools import find_packages, setup


def find_required():
    with open("requirements.txt") as f:
        return f.read().splitlines()


setup(
    name="jj-spec-validator",
    version="0.0.1",
    description="jj mocks validator for openapi specs",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Sam Roz",
    author_email="rolez777@gmail.com",
    python_requires=">=3.8",
    url="https://github.com/Maestoz/jj-spec-validator",
    license="Apache-2.0",
    packages=['jj_spec_validator'],
    install_requires=find_required(),
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ]
)
