
import sys
import threading
import numpy
import logging
from queue import Queue
from PyQt5 import QtCore

# import sounddevice

# print(dir(sounddevice.OutputStream))
# exit()

class PlayPluginChain(QtCore.QObject):
    """docstring for PlayPluginChain"""

    progress_signal = QtCore.pyqtSignal(float)
    stop_signal = QtCore.pyqtSignal()

    def __init__(self, **kwargs):
        super().__init__()

        self.device = kwargs.get("device", None)
        self.filename = kwargs.get("filename", None)
        self.vst_host = kwargs.get("vst_host", None)
        self.vst_plugins_chain = kwargs.get("vst_plugins_chain", None)
        self.blocksize = kwargs.get("blocksize", None)
        self.buffersize = kwargs.get("buffersize", None)

        self.log_level = kwargs.get("log_level", logging.INFO)
        _logger = self._logger_init(kwargs.get("pipe", None))
        self.logger = kwargs.get("logger", _logger)

        self.stream = None
        self.stream_wait_data_cnt = 0

        self._is_active = False

    def _fill_queue_buffer(self, data):
        #
        if self.play_event.is_set():
            return

        if self.play_block_index >= self.buffersize:
            if not self.stream.active:
                self.logger.info("START audio stream [ %s ]" % self.sounddevice.query_devices(self.stream.device, 'output')['name'])
                self.stream.start()
            timeout = ((self.blocksize * self.buffersize) / self.vst_host.sample_rate)
            try:
                self.play_queue.put(data, timeout=timeout*2)
                self.progress_signal.emit(self.start_position + (self.play_block_index / self.play_max_block_index))
            except Exception as e:
                self.logger.debug("Audio stream buffer is full.")
        else:
            self.play_queue.put_nowait(data)

        self.play_block_index += 1

    def _play_callback(self, outdata, frames, time, status):
        # assert frames == self.blocksize
        if status.output_underflow:
            self.logger.debug('Audio stream buffer underflow: increase blocksize?')
            # raise sounddevice.CallbackAbort
        # assert not status

        try:
            data = self.play_queue.get_nowait()
            if len(data) < len(outdata):
                outdata[:len(data)] = data
                outdata[len(data):] = numpy.zeros( (len(outdata) - len(data), 2), dtype=numpy.float32 )
                # raise sounddevice.CallbackStop
            else:
                outdata[:] = data
        except Exception as e:
            self.logger.debug('Audio stream buffer is empty: increase buffersize?')
            outdata[:] = numpy.zeros( (len(outdata), 2), dtype=numpy.float32 )
            self.stream_wait_data_cnt += 1
            if self.play_event.is_set():
                self.stream.stop()
            elif self.stream_wait_data_cnt >= 10:
                self.stop()
            # raise sounddevice.CallbackAbort

    def _logger_init(self, pipe):
        # Create logger for process and connect it to common pipe
        self.logger = logging.getLogger('Audio Stream')
        self.logger.setLevel( self.log_level )
        # create custom handler with a higher log level
        self.handler = logging.StreamHandler()
        formatter = logging.Formatter( fmt='%(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S' )
        self.handler.setFormatter(formatter)
        self.logger.addHandler(self.handler)


    # -------------------------------------------------------------------------


    def start(self, filename, audio_device, channels, vst_host, vst_plugins_chain, start):
        import sounddevice
        import soundfile

        self.sounddevice = sounddevice
        self.play_queue = Queue(maxsize=self.buffersize)
        self.play_event = threading.Event()

        f = soundfile.SoundFile(filename)
        f.close()

        if self.stream is None:
            self.stream = sounddevice.OutputStream(
                samplerate=f.samplerate,
                blocksize=self.blocksize,
                device=audio_device,
                channels=channels,
                dtype='float32',
                callback=self._play_callback,
                finished_callback=self.play_event.set,
                prime_output_buffers_using_stream_callback=True
            )

        self.play_block_index = self.stream_wait_data_cnt = 0
        self.play_max_block_index = f.frames / self.blocksize
        #
        self.start_position = start
        if self.start_position > 0:
            start = (f.frames * self.start_position)

        self._is_active = True

        self.filename = filename
        self.vst_host = vst_host
        self.vst_host.process_chain_start(filename, f.channels, vst_plugins_chain, soundfile.blocks, self._fill_queue_buffer, frames=-1, start=int(start), stop=None)

    def stop(self):
        if self.vst_host is not None:
            self.vst_host.process_chain_stop()
        if self.stream is not None:
            self.stream.stop()
        self._is_active = False
        self.stop_signal.emit()
        self.logger.info("STOP audio stream")

    def is_active(self):
        return self._is_active
