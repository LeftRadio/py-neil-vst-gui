

import logging
from PyQt5 import QtCore

class MainLogHandler(logging.StreamHandler):
    """docstring for MainLogHandler"""

    def __init__(self, signal, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signal = signal

    def emit(self, record):
        if "ProcessWorker" not in record.msg:
            s = self.format(record)
        else:
            s = record.msg
        self.signal.emit(s, record.levelname)


class ProcessLogHandler(logging.StreamHandler):
    """docstring for ProcessLogHandler"""

    def __init__(self, pipe, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pipe = pipe

    def emit(self, record):
        s = self.format(record)
        self.pipe.send((s, record.levelname))


class ProcessLogEmitter(QtCore.QThread):
    """ Emitter waits for data from the capitalization
        process and emits a signal for the UI to update its text
    """
    ui_data_available = QtCore.pyqtSignal(str, str)

    def __init__(self, pipe, deamon=True):
        super().__init__()
        self.pipe = pipe
        self.deamon = deamon

    def run(self):
        while True:
            try:
                text, level = self.pipe.recv()
            except EOFError:
                break
            else:
                self.ui_data_available.emit(text, level)