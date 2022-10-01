# py-neil-vst-gui

GUI application based on py-neil-vst package (Cython-based simple VST 2.4 Host and VST Plugins wrapper)

- Supported platforms: **Windows 64bit**
- Supported python versions: **3.7**, **3.8**, **3.9**
- Supported VST Plugins: only **64-bit/VST2**

- Multiply files work on the one click.
- VST 64-bit plugin chain support - add, remove, change "on the fly".
- VST Plugins self GUI on separate windows.
- Multithreading support for proccessing, one file - one thread.
- Fast work with minimum memory required for the one working thread.
- Play any file with VST plugin chain "as is" - some as the output result.
- ASIO, WASAPI, WDM audio streams support
- Save/Open projects files in readable json format
- Optional log window with four levels (DEBUG, INFO, WARNING, ERROR)
- GUI based on PyQt5
- Full open source project


## CLI py-neil-vst package
This GUI are based on the py-neil-vst CLI package. It automaticaly installed from
the 'install_requires' in setup.py from pip repository.
You can find it code here - https://github.com/LeftRadio/py-neil-vst

## Install from git (Windows):
```
python -m venv neil-vst-venv
cd neil-vst-venv && Scripts\activate.bat
pip install Cython
python -m setup build install
```

## Install from pip (Windows):
```
python -m venv neil-vst-venv
cd neil-vst-venv && Scripts\activate.bat
python -m pip install neil-vst-gui
```

## py-neil-vst-gui some screenshots

![alt text](https://github.com/LeftRadio/py-neil-vst-gui/blob/master/img/0_1.png?raw=true)

![alt text](https://github.com/LeftRadio/py-neil-vst-gui/blob/master/img/1.png?raw=true)

![alt text](https://github.com/LeftRadio/py-neil-vst-gui/blob/master/img/2.png?raw=true)
