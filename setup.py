# -*- coding: utf-8 -*-
#
# Warthog - Simple client for A10 load balancers
#
# Copyright 2014 Smarter Travel
#
# Available under the MIT license. See LICENSE for details.
#


import codecs
from setuptools import find_packages, setup
import warthog


AUTHOR = 'Smarter Travel',
EMAIL = ''
DESCRIPTION = 'Simple client for A10 load balancers'
URL = 'https://warthog.readthedocs.org/'
LICENSE = 'MIT'
CLASSIFIERS = [
    "Development Status :: 2 - Pre-Alpha",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.6",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3.3",
    "Programming Language :: Python :: 3.4",
    "Topic :: System :: Installation/Setup",
    "Topic :: System :: Software Distribution"
]

REQUIREMENTS = [
    'requests'
]

with codecs.open('README.rst', 'r', 'utf-8') as handle:
    LONG_DESCRIPTION = handle.read()

setup(
    name='warthog',
    version=warthog.__version__,
    author=AUTHOR,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author_email=EMAIL,
    classifiers=CLASSIFIERS,
    license=LICENSE,
    url=URL,
    install_requires=REQUIREMENTS,
    zip_safe=True,
    packages=find_packages())
