import os.path
from setuptools import setup, find_packages


def read_file(fn):
    with open(os.path.join(os.path.dirname(__file__), fn)) as f:
        return f.read()


setup(
    name="werewolf",
    version="0.0.1",
    description="Play the werewolf game",
    long_description=read_file("README.md"),
    author="jang",
    author_email="werewolf@ioctl.org",
    license=read_file("LICENCE.md"),
    packages=find_packages(),

    entry_points={
        'console_scripts': [
            'slackbot = werewolf.app:main',
        ],
    },

    package_data={'werewolf': '*.yaml'},
    include_package_data=True,

    install_requires=[
        'autobahn',
        'cachetools',
        'discord',
        'flask',
        'flock',
        'gunicorn',
        'markdown',
        'pyOpenSSL',
        'pyyaml',
        'recordtype',
        'requests',
        'twisted',
    ],

    tests_require=[
        "pytest",
        "flake8",
    ],
)
