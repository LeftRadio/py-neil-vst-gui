
import setuptools
from pathlib import Path
import os, sys

__version__ = '0.5.7'


this_directory = os.path.dirname(__file__)
packages = setuptools.find_packages()
print(this_directory, packages)

with open( str(this_directory) + '/README.md', "r" ) as f:
    long_description = f.read()


setuptools.setup(
    name='neil_vst_gui',
    version=__version__,
    packages=packages,
    package_data={
        # And include any *.dat files found in the "data" subdirectory
        # of the "mypkg" package, also:
        "neil_vst_gui": ["main.ui"],
    },
    license='MIT',
    description='GUI application based on py-neil-vst package',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
       'neil-vst>=0.2.7',
       'SoundFile>=0.10.3.post1',
       'sounddevice>=0.4.2',
       'numpy==1.19.0',
       'PyQt5'
    ],
    entry_points={
        "console_scripts": [
            "neil_vst_gui=neil_vst_gui.main:main",
        ]
    },
    include_package_data=True,

    author='Vladislav Kamenev',  # Type in your name
    author_email='vladislav@inorbit.com',
    url='https://github.com/LeftRadio/py-neil-vst-gui',
    keywords=['vst', 'plugin'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ]
)
