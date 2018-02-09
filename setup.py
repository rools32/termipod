#!/usr/bin/env python
from setuptools import setup, find_packages

import termipod

setup(name='termipod',
      version=termipod.__version__,
      description='Manage and read podcasts and youtube'
                  'videos in your terminal',
      author='Cyril Bordage',
      long_description=open('README.md').read(),
      packages=find_packages(),
      install_requires=['feedparser', 'appdirs', 'youtube_dl', 'python-mpv'],
      url='https://github.com/rools32/termipod',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console :: Curses',
          'Intended Audience :: End Users/Desktop',
          'Programming Language :: Python :: 3',
          'Topic :: Multimedia :: Sound/Audio',
          ],
      entry_points={
          'console_scripts': [
              'termipod = termipod.termipod:main',
              ],
          },
      keywords='podcast curses terminal rss youtube')
