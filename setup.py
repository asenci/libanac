"""
Setup script for libanac
"""

import sys
from setuptools import setup

import libanac


install_requires = [
    'requests',
]

if sys.version_info[:2] < (2, 7):
    install_requires.append('argparse')


setup(
    name=libanac.__title__,
    description=libanac.__summary__,
    long_description=open('README.rst').read(),
    url=libanac.__url__,

    author=libanac.__author__,
    author_email=libanac.__email__,
    license=libanac.__license__,

    version=libanac.__version__,

    packages=['libanac'],
    test_suite='tests',

    platforms='any',
    keywords=['ANAC', 'SACI', 'CIV Digital'],
    classifiers=[
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: BSD',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
    ],

    install_requires=install_requires,
)
