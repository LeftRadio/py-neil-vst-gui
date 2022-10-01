#!python3

import os
import sys
from time import time, sleep
import json
import logging
import threading
from queue import Queue
from multiprocessing import Pipe, freeze_support, current_process

from PyQt5 import Qt, QtWidgets, QtCore, QtGui, uic

from neil_vst_gui.ui_logging import MainLogHandler, ProcessLogEmitter
from neil_vst_gui.ui_settings import UI_Settings
from neil_vst_gui.main_worker import MainWorker
from neil_vst_gui.job import Job
from neil_vst_gui.play_chain import PlayPluginChain
from neil_vst_gui.wave_widget import WaveWidget
import neil_vst_gui.resources


__version__ = '0.5.8b2'


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# unload sonddevice lib for future use in another thread
def terminate_sounddevice(sounddevice):
    sounddevice._terminate()
    del(sounddevice)
    del(sys.modules["sounddevice"])


class VSTPluginWindow(QtWidgets.QWidget):

    def __init__(self, plugin, parent=None):
        super(VSTPluginWindow, self).__init__(parent)
        #
        self.plugin = plugin
        #
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Dialog)
        # set self window name
        self.setWindowTitle(plugin.name)
        # set self size corresponding to plugin size
        rect = plugin.edit_get_rect()
        self.resize(rect["right"], rect["bottom"])
        # open plugin GUI to self
        plugin.edit_open(int(self.winId()), self.gui_callback)

    def closeEvent(self, event):
        self.plugin.edit_close(int(self.winId()))
        self.plugin = None
        event.accept()

    def gui_callback(self, event_str, plugin_p, index, value, ptr, opt):
        if event_str == "audioMasterSizeWindow":
            rect = self.plugin.edit_get_rect()
            self.resize(rect["right"], rect["bottom"])


class neil_vst_gui_window(QtWidgets.QMainWindow):

    logging_signal = QtCore.pyqtSignal(str, str)
    progress_signal = QtCore.pyqtSignal(int)
    ready_signal = QtCore.pyqtSignal()

    # constructor
    def __init__(self):
        super().__init__()

        # Create the MainThread logging
        self._logger_init()
        #
        self.job = Job(logger=self.logger)
        #
        self.main_worker = MainWorker(logger=self.logger)
        #
        self.play_chain = PlayPluginChain(blocksize=1024, buffersize=8, logger=self.logger)


        # Init UI
        self._ui_init()

        # ---- connect signals/slots

        # self.play_chain.progress_signal.connect(self.play_progress_update)

        self.play_chain.stop_signal.connect(self.play_stop_slot)
        self.play_chain.progress_signal.connect(self.play_progress_update)
        self.wave_widget.change_play_position_clicked.connect(self.play_position_change_end)

        self.action_open_job.triggered.connect(self._job_open)
        self.action_save_job.triggered.connect(self._job_save)
        self.action_save_job_as.triggered.connect(self._job_save_as)
        self.action_show_logger_window.triggered.connect(self.dockWidget.show)
        self.action_exit.triggered.connect(self._close_request)
        #
        self.button_add_files.clicked.connect(self._files_open_click)
        self.button_remove_all_files.clicked.connect(self._files_remove_all)
        self.button_out_folder.clicked.connect(self._files_out_folder_click)
        self.push_button_open_out_folder.clicked.connect(self._files_out_folder_open_explorer_click)
        #
        self.button_add_vst.clicked.connect(self._plugin_add_click)
        self.button_vst_up_in_chain.clicked.connect(self._plugin_up_click)
        self.button_vst_down_in_chain.clicked.connect(self._plugin_down_click)
        self.button_remove_selected_vst.clicked.connect(self._plugin_remove_selected_click)
        self.button_remove_all_vst.clicked.connect(self._plugin_remove_all)
        self.table_widget_processes.itemDoubleClicked.connect(self._plugin_open_click)
        #
        self.button_play_start.clicked.connect(self.play_start_click)
        self.button_play_stop.clicked.connect(self.play_stop_click)
        self.table_widget_files.cellClicked.connect(self.play_selected)
        #
        self.button_start_work.clicked.connect(self.start_work_click)
        self.button_measurment.clicked.connect(self.start_work_click)
        self.button_stop_work.clicked.connect(self.stop_work_click)
        #
        self.tool_button_metadata_image.clicked.connect(self._metadata_image_select_click)
        #
        self.progress_signal.connect(self._progress_slot)
        self.ready_signal.connect(self.end_work)
        #
        self.dockWidget.dockLocationChanged.connect(self._dock_window_lock_changed)
        #
        self.combo_box_logging_level.currentIndexChanged.connect(self.logging_level_changed)
        self.combo_box_logging_level.setCurrentIndex(1)
        self.button_clear_log.clicked.connect(self.textBrowser.clear)
        # window color style
        self.actionLightStyle.triggered.connect(self._ui_style_set)
        self.actionDarkStyle.triggered.connect(self._ui_style_set)

        self._put_start_message()

    # -------------------------------------------------------------------------

    def _ui_init(self):
        # main ui from default
        self.uic = uic.loadUi(resource_path('main.ui'), self)
        self.setWindowTitle("NEIL-VST-GUI - %s - [ %s ]" % (__version__, "job default"))
        self._ui_load_settings()
        #
        self.wave_widget = WaveWidget(parent=self)
        self.horizontalLayout_5.addWidget(self.wave_widget)

        # available sound devices list
        import sounddevice
        devices = sounddevice.query_devices()
        devices_str = str(sounddevice.query_devices()).split('\n')
        for i in range(len(devices)):
            if devices[i]['max_output_channels'] > 0:
                self.combo_box_sound_device.addItem(devices_str[i], userData = devices[i]['name'])

        devices_list = [d for d in str(sounddevice.query_devices()).split('\n') if 'Output' in d]
        self.combo_box_sound_device.addItems(devices_list)
        self.combo_box_sound_device.setCurrentIndex(self.combo_box_sound_device.last_used_index)
        # unload sonddevice lib for future use in another thread
        terminate_sounddevice(sounddevice)

        # show self main window
        self.show()

        # create and start the UI thread
        self.nqueue = Queue()
        t = threading.Thread(target=self.ui_thread)
        t.daemon = True  # thread dies when main thread exits.
        t.start()

    def _ui_load_settings(self):
        # create UI settings instance
        self.ui_settings = UI_Settings(resource_path("ui_settings.json"))
        # open and parse json UI settings file
        settings = self.ui_settings.load()
        # main window
        window_size = settings.get("main_window_size", [600, 800])
        self.resize(window_size[0], window_size[1])
        # set main window position
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        pos = settings.get("main_window_position", [qr.topLeft().x(), qr.topLeft().y()])
        self.move(QtCore.QPoint(pos[0], pos[1]))
        # global color style
        self._ui_style_set(name=settings.get("theme_style", "Light"))
        # dock widget (logging window)
        self.dock_window_location = settings.get("dock_window_location", QtCore.Qt.BottomDockWidgetArea)
        if self.dock_window_location == 0:
            self.dockWidget.setFloating(True)
            # dock window position
            qr = self.dockWidget.frameGeometry()
            cp = QtWidgets.QDesktopWidget().availableGeometry().center()
            qr.moveCenter(cp)
            pos = settings.get("dock_window_position", [qr.topLeft().x(), qr.topLeft().y()])
            self.dockWidget.move(QtCore.QPoint(pos[0], pos[1]))
        else:
            self.addDockWidget(self.dock_window_location, self.dockWidget);
        # dock widget window size
        window_size = settings.get("dock_window_size", [600, 300])
        self.dockWidget.resize(window_size[0], window_size[1])
        self.resizeDocks({self.dockWidget}, {window_size[0]}, QtCore.Qt.Horizontal);
        self.resizeDocks({self.dockWidget}, {window_size[1]}, QtCore.Qt.Vertical);
        if not settings.get("dock_window_visible", True):
            self.dockWidget.close()
        # tabs tables
        columns_width = settings.get("table_files_columns", [500, 32, 100])
        for i in range(len(columns_width)):
            self.table_widget_files.setColumnWidth(i, columns_width[i])
        # log message colors
        self.textBrowser.text_colors = {
            'ERROR':    QtGui.QColor(255, 32, 32),
            'WARNING':  QtGui.QColor(220, 64, 64),
            'INFO':     QtGui.QColor(212, 224, 212),
            'DEBUG':    QtGui.QColor(212, 212, 64)
        }
        #
        self.combo_box_sound_device.__dict__["last_used_index"] = int(settings.get("sound_device_index", 0))
        # opes/save filepaths
        self.job.files().last_path = settings.get("files_last_path", "C://")
        self.job.files().out_folder = settings.get("files_out_last_path", "C://")
        self.line_edit_out_folder.setText(self.job.files().out_folder)
        self.job.vst_chain().last_path = settings.get("vst_last_path", "C://")
        self.job.last_path = settings.get("job_last_path", "C://")

    def _ui_save_settings(self):
        # create settings dict
        settings = {}
        # main window
        settings["main_window_size"] = [self.size().width(), self.size().height()]
        settings["main_window_position"] = [self.geometry().x()-1, self.geometry().y()-31]
        # global color style
        settings["theme_style"] = self.style_name
        # dock widget (logging window)
        settings["dock_window_visible"] = self.dockWidget.isVisible()
        settings["dock_window_location"] = self.dock_window_location
        settings["dock_window_size"] = [self.dockWidget.size().width(), self.dockWidget.size().height()]
        settings["dock_window_position"] = [self.dockWidget.geometry().x()-1, self.dockWidget.geometry().y()-31]
        #
        settings["table_files_columns"] = [
            self.table_widget_files.columnWidth(0),
            self.table_widget_files.columnWidth(1),
            self.table_widget_files.columnWidth(2)
        ]
        #
        settings["sound_device_index"] = self.combo_box_sound_device.currentIndex()
        # open/save filepaths
        settings["files_last_path"] = self.job.files().last_path
        settings["files_out_last_path"] = self.job.files().out_folder
        settings["vst_last_path"] = self.job.vst_chain().last_path
        settings["job_last_path"] = self.job.last_path
        # save all settings
        self.ui_settings.save(**settings)

    def _ui_style_set(self, **kwargs):
        if "name" in kwargs:
            name = kwargs["name"]
        else:
            name = self.sender().objectName()
        if 'Light' in name:
            self.style_name = 'Light'
            self.setStyleSheet("")
        elif 'Dark' in name:
            self.style_name = 'Dark'
            self.setStyleSheet("background-color: rgb(76, 76, 76);\ncolor: rgb(255, 255, 255);")
        # self.anim.scene.setBackgroundBrush(self.palette().color(QtGui.QPalette.Background))
        # self.anim_2.scene.setBackgroundBrush(self.palette().color(QtGui.QPalette.Background))

    def _dock_window_lock_changed(self, arg):
        self.dock_window_location = arg

    def _put_start_message(self):

        import neil_vst
        import neil_vst_gui.tag_write as tag_write
        import soundfile
        import sounddevice
        import numpy

        self._start_msg = [
            'VST2.4 Host/Plugins chain worker GUI build %s.' % __version__,
            '',
            'Used:',
            '[ py-neil-vst %s ]' % neil_vst.__version__,
            '[ tag-write-util %s ]' % tag_write.__version__,
            '[ soundfile %s ]' % soundfile.__version__,
            '[ sounddevice %s ]' % sounddevice.__version__,
            '[ numpy %s ]' % numpy.__version__,
            '[ PyQt5 ]',

            '',
            'The fully free and open-sourse project.',
            'Multiprocessing, minimum memory footprint, fastest work and maximum quality.',
            '',
            'The contributors:',
            'Vladislav Kamenev :: LeftRadio',
            'Special big thanks to all who supported the project.',
            '',
            'Wait start the working ...\n' ]
        # unload sonddevice lib for future use in another thread
        terminate_sounddevice(sounddevice)

        self.nqueue.put('start_message')

    # -------------------------------------------------------------------------

    def _job_open(self):
        json_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'open files',
            self.job.last_path,
            'JSON (*.json)'
        )
        if not json_file:
            return

        try:
            # load job settings
            self.job.load(json_file)
            #
            self._files_table_update(self.job.files().filelist)
            self.line_edit_out_folder.setText(self.job.files().out_folder)
            #
            # normalize = self.job.settings["normalize"]
            # self.check_box_normalize_enable.setChecked(normalize["enable"]),
            # self.line_edit_normalize_rms_level.setText( str(normalize["target_rms"]) )
            # self.line_edit_normalize_error_db.setText( str(normalize["error_db"]) )
            #
            self._plugin_table_update()
            #
            self._set_metadata(self.job.metadata().data)
            #
            self.logger.info("JOB loaded from '%s'" % os.path.basename(json_file))
            #
            self.setWindowTitle("%s [ %s ]" % (self.windowTitle().split("[")[0], os.path.basename(json_file)))
        except Exception as e:
            self.logger.error("[ ERROR ] - JOB are NOT load from '%s', check job file for correct structure" % os.path.basename(json_file))
            self.logger.error(str(e))

    def _job_save(self):
        if self.job.is_default():
            self._job_save_as()
            return
        #
        self._job_update_dump()

    def _job_save_as(self):
        json_file, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'save file',
            os.path.dirname(self.job.last_path),
            'JSON (*.json)'
        )
        if not json_file:
            return
        # else:
        #     self.json_file = json_file
        # self._job_last_path = QtCore.QFileInfo(self.json_file).path()
        #
        self._job_update_dump(json_file)

    def _job_update_dump(self, json_file=None):
        try:
            self.job.update(
                normilize_params=self._normilize_settings(),
                metadata=self._get_metadata(),
                filepath=json_file
            )
            self.logger.info("JOB saved to - %s [ SUCCESS ], set DEBUG level for details" % json_file)
            self.logger.debug("out_folder - %s, normilize_params - %s, vst_plugins_chain - %s, metadata - %s, filepath - %s" % (self.line_edit_out_folder.text(), str(self._normilize_settings()), [p.name for p in self.job.vst_chain().plugins_list], self._get_metadata(), json_file))
        except Exception as e:
            self.logger.error("JOB save to - %s  [ ERROR ], set DEBUG level for details" % json_file)
            self.logger.debug(str(e))

    # -------------------------------------------------------------------------

    def _files_open_click(self):
        in_files = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'open files',
            self.job.files().last_path,
            'Audio (*.aiff *.flac *.wav *.ogg *.mp3)'
        )
        if not len(in_files[0]):
            return
        self.job.files().add(in_files[0])
        self._files_table_update(in_files[0])

    def _files_table_clear(self):
        while self.table_widget_files.rowCount():
            self.table_widget_files.removeRow(0)

    def _files_table_update(self, filelist):
        import soundfile

        self._files_table_clear()

        for f in sorted(filelist):
            if f in [self.table_widget_files.item(r, 0).text() for r in range(self.table_widget_files.rowCount())]:
                continue
            #
            self.table_widget_files.setRowCount(self.table_widget_files.rowCount() + 1)
            # pathname
            self.table_widget_files.setItem(self.table_widget_files.rowCount()-1, 0, QtWidgets.QTableWidgetItem(os.path.basename(f)))
            # size
            item = QtWidgets.QTableWidgetItem("%.2f MB" % (os.stat(f).st_size/(1024*1024)))
            item.setTextAlignment(QtCore.Qt.AlignHCenter)
            self.table_widget_files.setItem(self.table_widget_files.rowCount()-1, 1, item)
            # description
            chs = ["Mono", "Stereo", "", "4 CH"]
            load_file = soundfile.SoundFile(f, mode='r', closefd=True)
            decs_text = "%s kHz  %s  %s" % (load_file.samplerate/1000, chs[load_file.channels-1], load_file.subtype)
            item = QtWidgets.QTableWidgetItem(decs_text)
            item.setTextAlignment(QtCore.Qt.AlignHCenter)
            self.table_widget_files.setItem(self.table_widget_files.rowCount()-1, 2, item)

    def _files_remove_all(self):
        self.job.files().clear()
        self._files_table_clear()

    def _files_out_folder_click(self):
        dir_name = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Open Directory",
            self.job.files().out_folder,
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks
        )
        self.line_edit_out_folder.setText(dir_name)
        self.job.files().out_folder_update(dir_name)

    def _files_out_folder_open_explorer_click(self):
        import subprocess
        path = os.path.normpath(self.job.files().out_folder)
        subprocess.Popen(r'explorer "%s"' % path)

    # -------------------------------------------------------------------------

    def play_start_click(self):
        self.button_play_start.setEnabled(False)
        self.button_play_stop.setEnabled(True)
        self.table_widget_files.setEnabled(False)

        self.play_start_pos = self.wave_widget.get_play_position()
        fileinex = self.table_widget_files.currentRow()
        self.play_start_thread(self.play_start_pos, fileinex)

    def play_start_thread(self, position=0, fileindex=-1):
        self.play_thread = threading.Thread(target=self.play_start, args=(position,fileidnex,))
        self.play_thread.daemon = True  # thread dies when main thread exits.
        self.play_thread.start()

    def play_start(self, position=0, fileindex=-1):
        try:
            self.play_chain.start(
                filename=self.job.files().filelist[fileindex],
                audio_device=self.combo_box_sound_device.currentData(),
                channels=2,
                vst_host=self.job.vst_chain().host(),
                vst_plugins_chain=self.job.vst_chain().plugins(),
                start=position
            )
        except IndexError as e:
            self.logger.error("Nothing to play. Please select the file first.")
            self.play_chain.stop()
        except Exception as e:
            self.logger.error(str(e))
            self.play_chain.stop()

    def play_stop_click(self):
        self.play_chain.stop()

    def play_stop_slot(self):
        self.button_play_start.setEnabled(True)
        self.button_play_stop.setEnabled(False)
        self.table_widget_files.setEnabled(True)
        #
        if self.wave_widget.get_play_position() >= 1.0:
            self.wave_widget.set_play_position(0)

    def play_selected(self, row, column):
        self.label_6.setText(self.label_6.text().split(" - ")[0] + " - [ %s ]" % os.path.basename(self.job.files().filelist[row]))
        self.wave_widget.set_wave_file(self.job.files().filelist[row])
        self.wave_widget.set_play_position(0)

    def play_progress_update(self, procent_value):
        self.wave_widget.set_play_position(procent_value)

    def play_position_change_end(self):
        if self.play_chain.is_active():
            self.play_chain.stop()
            self.play_thread.join()
            self.play_start_click()

    # -------------------------------------------------------------------------

    def _normilize_settings(self):
        return {
            "enable": self.check_box_normalize_enable.isChecked(),
            "target_rms": float(self.line_edit_normalize_rms_level.text()),
            "error_db": float(self.line_edit_normalize_error_db.text())
        }

    def _plugin_table_add(self, name):
        self.table_widget_processes.setRowCount(self.table_widget_processes.rowCount() + 1)
        item = QtWidgets.QTableWidgetItem(name)
        item.setTextAlignment(QtCore.Qt.AlignHCenter)
        self.table_widget_processes.setItem(self.table_widget_processes.rowCount() - 1, 0, item)

    def _plugin_table_clear(self):
        while self.table_widget_processes.rowCount():
            self.table_widget_processes.removeRow(0)

    def _plugin_table_update(self):
        self._plugin_table_clear()
        for plugin in self.job.vst_chain().plugins_list:
            self._plugin_table_add(plugin.name)

    def _plugin_swap(self, up):
        #
        table = self.table_widget_processes
        select_row = table.currentRow()

        if up:
            if select_row <= 0:
                return
            sign = -1
        else:
            if select_row >= table.rowCount() + 1:
                return
            sign = +1

        self.job.vst_chain().swap(select_row, select_row + sign)

        select_item = table.takeItem(select_row, 0)
        change_item = table.takeItem(select_row + sign, 0)

        table.setItem(select_row + sign, 0, select_item)
        table.setItem(select_row, 0, change_item)

        table.setCurrentCell(select_row + sign, 0, QtCore.QItemSelectionModel.SelectCurrent)

    def _plugin_add_click(self):
        vst_dll, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'open VST plugin file',
            QtCore.QFileInfo(self.job.vst_chain().last_path).path(),
            'VST dll (*.dll)'
        )
        if not vst_dll:
            return
        # load new vst plugin
        plugin = self.job.vst_chain().add(vst_dll)
        # update vst plugins table
        self._plugin_table_add(plugin.name)

    def _plugin_up_click(self):
        self._plugin_swap(up=True)

    def _plugin_down_click(self):
        self._plugin_swap(up=False)

    def _plugin_remove_selected_click(self):
        index = self.table_widget_processes.currentRow()
        if index < 0 or index > self.table_widget_processes.rowCount()-1:
            return
        self.job.vst_chain().remove(index)
        self.table_widget_processes.removeRow(index)

    def _plugin_remove_all(self):
        self.job.vst_chain().clear()
        self._plugin_table_clear()

    # -------------------------------------------------------------------------

    def _plugin_open_click(self):
        index = self.table_widget_processes.currentRow()
        w = VSTPluginWindow(self.job.vst_chain().plugin(index), parent=self)
        w.show()

    # -------------------------------------------------------------------------

    def _get_metadata(self):
        return [
            self.line_edit_metadata_author.text(),
            self.line_edit_metadata_artist.text(),
            self.line_edit_metadata_sound_designer.text(),
            self.line_edit_metadata_album_book.text(),
            self.line_edit_metadata_genre.text(),
            self.line_edit_metadata_year.text(),
            self.text_edit_metadata_description.toPlainText(),
            self.line_edit_metadata_image.text()
        ]

    def _set_metadata(self, metadata):
        self.line_edit_metadata_author.setText(metadata[0])
        self.line_edit_metadata_artist.setText(metadata[1])
        self.line_edit_metadata_sound_designer.setText(metadata[2])
        self.line_edit_metadata_album_book.setText(metadata[3])
        self.line_edit_metadata_genre.setText(metadata[4])
        self.line_edit_metadata_year.setText(metadata[5])
        self.text_edit_metadata_description.setPlainText(metadata[6])
        self.line_edit_metadata_image.clear()
        self.line_edit_metadata_image.insert(metadata[7])
        self._metadata_image_draw(metadata[7])

    def _metadata_image_draw(self, filepath):
        try:
            pixmap = QtGui.QPixmap(filepath)
            if pixmap.width() > pixmap.height():
                width = 100
                height = int(pixmap.height() / (pixmap.width() / 100))
            else:
                width = int(pixmap.height() / (pixmap.width() / 140))
                height = 140
            self.label_metadata_image_show.setMinimumWidth(width)
            self.label_metadata_image_show.setMaximumWidth(width)
            self.label_metadata_image_show.setMinimumHeight(height)
            self.label_metadata_image_show.setMaximumHeight(height)
            self.label_metadata_image_show.setPixmap(pixmap)
        except Exception as e:
            self.logger.error("Error on draw the selected image [%s]" % str(e))

    def _metadata_image_select_click(self):
        image_file, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'Open File',
            self.job.files().last_path,
            'Images (*.bmp *.png *.jpg)'
        )
        if not len(image_file):
            return
        self.line_edit_metadata_image.setText(image_file[0])
        self._metadata_image_draw(image_file[0])

    # -------------------------------------------------------------------------

    def ui_thread(self):
        """ The worker thread pulls an item from the queue and processes it """
        while True:
            item = self.nqueue.get()
            with threading.Lock():
                if item == 'start_message':
                    import random
                    for m in self._start_msg:
                        self.logger.info(m)
                        sleep(random.uniform(0.1, 0.2))
                if item == 'run':
                    start = time()
                    while any(w.is_alive() for w in self.main_worker.processes):
                        sleep(0.01)
                    if not self.main_worker.terminate_work:
                        import datetime
                        sleep(0.5)
                        self.logger.info("[ END ] - Elapsed time: [ %s ]" % str(datetime.timedelta(seconds=(time()-(start+0.5)))).split(".")[0] )
                        self.ready_signal.emit()
                if item == 'play':
                    self._play_start()

            self.nqueue.task_done()

    def start_work_click(self):
        """ START button click slot """
        sender_name = self.sender()
        if not self.button_start_work.isEnabled() or not len(self.job.files().filelist):
            return
        self.button_start_work.setEnabled(False)
        self.button_measurment.setEnabled(False)
        self.button_stop_work.setEnabled(True)
        self.files_frame.setEnabled(False)
        self.vst_frame.setEnabled(False)
        # block until all tasks are done
        self.nqueue.join()
        # update all job parameters
        self.job.update(
            normilize_params=self._normilize_settings(),
            metadata=self._get_metadata()
        )

        try:
            vst_buffer_size = int(self.line_edit_buffer_size_bytes.text())
        except Exception as e:
            self.logger.warning(
                "VST buffer size is incorrect!"
                "Please set numeric value in range: [ 1024..65536 ] bytes\n"
                "Set the default buffer size [ 1024 bytes ]"
            )
            vst_buffer_size = 1024

        # start the work
        self.main_worker.start(
            pipe=self.child_pipe,
            job=self.job,
            meas=("MEAS" in sender_name.text()),
            vst_buffer_size=vst_buffer_size,
            log_level=self.workers_logging_level
        )

        # wait while all processes are done
        self.nqueue.put('run')

    def stop_work_click(self):
        if not self.button_stop_work.isEnabled():
            return
        self.main_worker.stop()
        self.logger.warning("[TERMINATED]",)
        self.end_work()

    def end_work(self):
        self.button_start_work.setEnabled(True)
        self.button_measurment.setEnabled(True)
        self.button_stop_work.setEnabled(False)
        self.files_frame.setEnabled(True)
        self.vst_frame.setEnabled(True)

    old_progr = 0
    def _progress_slot(self, progress):
        if (progress - self.old_progr) > 20:
            # self.anim.timer.setInterval(600 - (progress * 5))
            self.old_progr = progress
        elif not progress:
            self.old_progr = progress

    # -------------------------------------------------------------------------

    def _logger_init(self):
        #
        self.extra = {'ThreadName': current_process().name }
        self.logger = logging.getLogger(current_process().name)
        self.logger.setLevel(logging.DEBUG)
        self.handler = MainLogHandler(self.logging_signal)
        self.handler.setFormatter(logging.Formatter(
            fmt='%(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
        self.logger.addHandler(self.handler)
        self.logging_signal.connect(self.text_browser_message)
        # Create the logging communication pipes and emiter for all work processes
        self.mother_pipe, self.child_pipe = Pipe()
        self.log_emitter = ProcessLogEmitter(self.mother_pipe)
        self.log_emitter.start()
        self.log_emitter.ui_data_available.connect(self.text_browser_message)

    def logging_level_changed(self, level_index):
        levels = [ logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR ]
        self.logger.setLevel(levels[level_index])
        self.handler.setLevel(levels[level_index])
        self.workers_logging_level = levels[level_index]
        self.play_chain.log_level = levels[level_index]

    def _mt_update_log(self, text):
        """ Add text to the lineedit box. """
        self.logger.info(text)

    def text_browser_message(self, msg, level):
        text_cursor = self.textBrowser.textCursor()
        text_cursor.movePosition(QtGui.QTextCursor.End)
        self.textBrowser.setTextCursor(text_cursor)

        color = self.textBrowser.text_colors.get(level, self.textBrowser.text_colors['DEBUG'])
        self.textBrowser.setTextColor(color)
        self.textBrowser.insertPlainText("%s \r\n" % msg)

        sb = self.textBrowser.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.textBrowser.repaint()

    def _log_clear(self):
        self.textBrowser.clear()

    # -------------------------------------------------------------------------

    def _close_request(self):
        self.close()

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(
            self,
            'QUIT',
            "Are you sure you want to exit the program?",
            QtWidgets.QMessageBox.Yes,
            QtWidgets.QMessageBox.No
        )
        # save GUI state
        self._ui_save_settings()
        #
        if reply == QtWidgets.QMessageBox.No:
            event.ignore()
            return
        event.accept()

    def process_events(self):
        QtWidgets.QApplication.processEvents()


def main():
    freeze_support()
    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QApplication.setStyle(QtWidgets.QStyleFactory.create('Fusion'))
    # QtWidgets.QApplication.setStyle(QtWidgets.QStyleFactory.create('Cleanlooks'))
    ex = neil_vst_gui_window()
    sys.exit(app.exec_())


# program start here
if __name__ == '__main__':
    main()
