#!/usr/bin/env python

import os.path
import sys

from setuptools import setup, find_packages

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

setup(
    name='pypi-data',
    version='0.1.4',
    description='PyPI metadata downloader',
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst')).read(),
    author='Nathan Reynolds',
    author_email='email@nreynolds.co.uk',
    url='https://github.com/nathforge/pypi-data',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    test_suite='tests',
    tests_require=[
        'httpretty'
    ],
    entry_points = {
        'console_scripts': [
            'pypi-data = pypi_data.__main__:main',                  
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ]
)
