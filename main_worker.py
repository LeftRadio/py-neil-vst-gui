
import os
import logging
# import logging.config
# import logging.handlers
# import multiprocessing
from multiprocessing import Process, current_process
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread
from neil_vst import VstHost, VstPlugin, VstChainWorker
from tag_write import TagWriter
from ui_logging import ProcessLogHandler


class ProcessWorker(Process):
    """docstring for ProcessWorker"""

    def __init__(self, pipe, job_file, in_file, out_file, buffer_size, meas=False, tag_data={}, tag_only=False, daemon=True, log_level=logging.INFO):
        super().__init__()
        self.pipe = pipe
        self.job_file = job_file
        self.in_file = in_file
        self.out_file = out_file
        self.buffer_size = buffer_size
        self.meas = meas
        self.tag_data = tag_data
        self.tag_only = tag_only
        self.daemon=daemon
        self.log_level = log_level

    def run(self):
        # Create logger for process and connect it to common pipe
        self.extra = {'ThreadName': current_process().name }
        self.logger = logging.getLogger(current_process().name)
        self.logger.setLevel( self.log_level )
        # create custom handler with a higher log level
        self.handler = ProcessLogHandler(self.pipe)
        formatter = logging.Formatter( fmt='%(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S' )
        self.handler.setFormatter(formatter)
        self.logger.addHandler(self.handler)

        # TAG WRITE ONLY
        if self.tag_only:
            TagWriter(self.logger).write(self.in_file, *self.tag_data)
            return

        # VST CHAIN WORK
        self.vst_chain = VstChainWorker(buffer_size=self.buffer_size, logger=self.logger, display_info=False)
        # Process measurment or work
        try:
            if self.meas:
                _, meas_rms_db, _, peak_max_db = self.vst_chain.rms_peak_measurment(self.in_file)
                return (meas_rms_db, peak_max_db)
            else:
                self.vst_chain.procces_file(self.job_file, self.in_file, self.out_file)
                TagWriter(self.logger).write(self.out_file, *self.tag_data)
        except Exception as e:
            self.logger.error("%s - %s" % (os.path.basename(self.in_file), str(e)))




class MainWorker(object):
    """docstring for MainWorker"""

    def __init__(self, logger):
        self.processes = []

        self.vst_buffer_size = 1024*16
        self._internal_vst_host = VstHost(44100, logger=logger)

        self.terminate_work = False
        self.logger = logger

    # -------------------------------------------------------------------------

    def vst_dll_load(self, dll_path, logger):
        # load and return plugin instance if success
        return VstPlugin(
            host=self._internal_vst_host,
            vst_path_lib=dll_path,
            sample_rate=self._internal_vst_host.sample_rate,
            block_size=self._internal_vst_host.block_size,
            max_channels=4,
            self_buffers=True,
            logger=logger
        )

    # -------------------------------------------------------------------------

    def host(self):
        return self._internal_vst_host

    def start(self, pipe, job, meas, vst_buffer_size, log_level):

        if not len(job.out_folder) or not os.path.exists(job.out_folder):
            self.logger.error("The output folder are not set or invalid path! Break work.")
            return
        assert vst_buffer_size >= (1024) and vst_buffer_size <= (1024*64), \
            "VST buffer size is incorrect! Please set value in range: [ 1024..65536 ] bytes"

        # determinate in/out files
        in_files = job.in_files
        out_files = [ os.path.abspath(os.path.join(job.out_folder, os.path.basename(f))) for f in in_files ]

        # reset terminate state and processes list
        self.terminate_work = False
        self.processes = []
        # all processes
        for i in range(len(in_files)):
            # run the one process
            process = ProcessWorker(
                pipe,
                job.job_file,
                in_files[i],
                out_files[i],
                vst_buffer_size,
                meas=meas,
                tag_data=job.tag_data,
                tag_only=(len(job.settings["plugins_list"]) == 0),
                log_level=log_level)
            process.start()
            self.processes.append(process)

    def stop(self):
        for w in self.processes:
            w.terminate()
        self.terminate_work = True

