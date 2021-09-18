#!python3

import os
import sys
from time import time, sleep
import json
import logging
import threading
from queue import Queue
from multiprocessing import Pipe, freeze_support, current_process

from PyQt5 import QtWidgets, QtCore, QtGui, uic

from neil_vst_gui.ui_logging import MainLogHandler, ProcessLogEmitter
from neil_vst_gui.ui_settings import UI_Settings
from neil_vst_gui.main_worker import MainWorker
from neil_vst_gui.job import Job
from neil_vst_gui.play_chain import PlayPluginChain
from neil_vst_gui.rects_animate import RectsAnimate
import neil_vst_gui.resources

import soundfile


__version__ = '0.5.7'


class VSTPluginWindow(QtWidgets.QWidget):

    def __init__(self, plugin, parent=None):
        super(VSTPluginWindow, self).__init__(parent)
        #
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Dialog)
        # set self window name
        self.setWindowTitle(plugin.name)
        # set self size corresponding to plugin size
        rect = plugin.edit_get_rect()
        self.resize(rect["right"], rect["bottom"])
        # open plugin GUI to self
        plugin.edit_open(int(self.winId()), self.gui_callback)
        self.plugin = plugin

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

        # Init UI
        self._ui_init()


        self.job = Job()
        self.main_worker = MainWorker(logger=self.logger)

        self.play_chain = PlayPluginChain(blocksize=1024, buffersize=10, logger=self.logger)
        self.play_chain.progress_signal.connect(self.play_progress_update)
        self.play_chain.stop_signal.connect(self.play_stop_slot)

        # ---- connect signals/slots

        self.action_open_job.triggered.connect(self._job_open)
        self.action_save_job.triggered.connect(self._job_save)
        self.action_show_logger_window.triggered.connect(self.dockWidget.show)
        self.action_exit.triggered.connect(self._close_request)
        #
        self.button_add_files.clicked.connect(self._files_open_click)
        # self.button_remove_selected_files.clicked.connect(self._files_remove_selected)
        self.button_remove_all_files.clicked.connect(self._files_remove_all)
        self.tool_button_out_folder.clicked.connect(self._files_out_folder_click)
        #
        self.button_add_vst.clicked.connect(self._plugin_add_click)
        self.button_change_vst.clicked.connect(self._plugin_change_click)
        self.table_widget_processes.itemDoubleClicked.connect(self._plugin_change_click)
        self.button_vst_up_in_chain.clicked.connect(self._plugin_up_click)
        self.button_vst_down_in_chain.clicked.connect(self._plugin_down_click)
        self.button_remove_selected_vst.clicked.connect(self._plugin_remove_selected_click)
        self.button_remove_all_vst.clicked.connect(self._plugin_remove_all)
        #
        self.button_play_start.clicked.connect(self.play_start_click)
        self.button_play_stop.clicked.connect(self.play_stop_click)
        self.table_widget_files.cellClicked.connect(self.play_selected)
        self.horizontal_slider_play.sliderPressed.connect(self.play_position_change_start)
        self.horizontal_slider_play.sliderReleased.connect(self.play_position_change_end)
        #
        self.button_start_work.clicked.connect(self.start_work_click)
        self.button_measurment.clicked.connect(self.start_work_click)
        self.button_stop_work.clicked.connect(self.stop_work_click)
        #
        self.tool_button_metadata_image.clicked.connect(self._tag_metadata_image_select_click)
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
        self.uic = uic.loadUi(os.path.dirname(__file__) + '/main.ui', self)
        # create the animate graphics before loading the UI settings
        self.anim = RectsAnimate(210, 25, QtGui.QColor.fromRgb(0, 32, 49))
        self.anim_2 = RectsAnimate(210, 25, QtGui.QColor.fromRgb(0, 32, 49))
        self.horizontalLayout_2.insertWidget(1, self.anim.window)
        self.horizontalLayout_2.insertWidget(8, self.anim_2.window)
        # load UI settings
        self._ui_load_settings()
        # avaible sound devices list
        import sounddevice
        devices_list = [d['name'] for d in sounddevice.query_devices() if d['max_output_channels'] > 1]
        self.combo_box_sound_device.addItems(devices_list)

        # show self main window
        self.show()
        # update scene background after show the window
        self.anim.scene.setBackgroundBrush(self.palette().color(QtGui.QPalette.Background))
        self.anim_2.scene.setBackgroundBrush(self.palette().color(QtGui.QPalette.Background))
        # create and start the UI thread
        self.nqueue = Queue()
        t = threading.Thread(target=self.ui_thread)
        t.daemon = True  # thread dies when main thread exits.
        t.start()

    def _ui_load_settings(self):
        # create UI settings instance
        self.ui_settings = UI_Settings(os.path.dirname(__file__) + "/ui_settings.json")
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
        # opes/save filepaths
        self._files_last_path = settings.get("files_last_path", "C://")
        self._files_out_last_path = settings.get("files_out_last_path", "C://")
        self.line_edit_out_folder.setText(self._files_out_last_path)
        self._vst_last_path = settings.get("vst_last_path", "C://")
        self._job_last_path = settings.get("job_last_path", "C://")

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
        # open/save filepaths
        settings["files_last_path"] = self._files_last_path
        settings["files_out_last_path"] = self.line_edit_out_folder.text()
        settings["vst_last_path"] = self._vst_last_path
        settings["job_last_path"] = self._job_last_path
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
        self.anim.scene.setBackgroundBrush(self.palette().color(QtGui.QPalette.Background))
        self.anim_2.scene.setBackgroundBrush(self.palette().color(QtGui.QPalette.Background))

    def _dock_window_lock_changed(self, arg):
        self.dock_window_location = arg

    def _put_start_message(self):

        import neil_vst
        import neil_vst_gui.tag_write as tag_write
        import sounddevice
        import numpy

        self._start_msg = [
            'VST2.4 Host/Plugins chain worker GUI build %s beta.' % __version__,
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
            'Ildar Muhamadullin :: Muha',
            '',
            'Special big thanks to all who supported the project.',
            '',
            "Add input audio files, add needed VST2 plugins and it's settings, set out files metadata.",
            'That all. Click the "START" and enjoy with the result ;)',
            '',
            'Wait start the working ...\n' ]
        self.nqueue.put('start_message')
        del(neil_vst)
        del(tag_write)


    # -------------------------------------------------------------------------


    def _job_open(self):
        json_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'open files',
            self._job_last_path,
            'JSON (*.json)'
        )
        if not json_file:
            return
        self._job_last_path = QtCore.QFileInfo(json_file).path()

        try:
            self.job.load(json_file)
            #
            self._plugin_remove_all()
            for v in self.job.settings["plugins_list"].values():
                plugin = self._plugin_add(v["path"])
                self.job.plugin_parameters_set(plugin, v["params"])
            #
            normalize = self.job.settings["normalize"]
            self.check_box_normalize_enable.setChecked(normalize["enable"]),
            self.line_edit_normalize_rms_level.setText( str(normalize["target_rms"]) )
            self.line_edit_normalize_error_db.setText( str(normalize["error_db"]) )
            #
            self.logger.info("JOB loaded from '%s' [ SUCCESS ]" % os.path.basename(json_file))
            title = self.windowTitle()
            self.setWindowTitle("%s [ %s ]" % (title.split("[")[0], os.path.basename(json_file)))
        except Exception as e:
            self.logger.error("JOB load from '%s' [ ERROR ], check job file for correct sctructure" % os.path.basename(json_file))
            self.logger.debug(str(e))

    def _job_save(self):
        json_file, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'save file',
            self._job_last_path,
            'JSON (*.json)'
        )
        if not json_file:
            return
        try:
            self.job.update(
                filepath=json_file,
                normilize_params=self._normilize_settings()
            )
            self.logger.info("JOB saved to - %s [ SUCCESS ], set DEBUG level for details" % json_file)
            self.logger.debug("filepath - %s, normilize_params - %s" % (json_file, self._normilize_settings()))
        except Exception as e:
            self.logger.error("JOB save to - %s  [ ERROR ], set DEBUG level for details" % json_file)
            self.logger.debug(str(e))


    # -------------------------------------------------------------------------


    def _files_open_click(self):
        in_files = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'open files',
            self._files_last_path,
            'Audio (*.aiff *.flac *.wav *ogg)'
        )
        if not len(in_files[0]):
            return
        self._files_last_path = QtCore.QFileInfo(in_files[0][0]).path()

        self.job.set_in_files(in_files[0])
        self._files_update_table(self.job.in_files)

    def _files_update_table(self, filelist):
        table = self.table_widget_files

        self._files_clear_table()

        for f in sorted(filelist ):
            if f in [table.item(r, 0).text() for r in range(table.rowCount())]:
                continue
            #
            table.setRowCount(table.rowCount() + 1)
            # pathname
            table.setItem(table.rowCount()-1, 0, QtWidgets.QTableWidgetItem(os.path.basename(f)))
            # size
            item = QtWidgets.QTableWidgetItem("%.2f MB" % (os.stat(f).st_size/(1024*1024)))
            item.setTextAlignment(QtCore.Qt.AlignHCenter)
            table.setItem(table.rowCount()-1, 1, item)
            # description
            chs = ["Mono", "Stereo", "", "4 CH"]
            load_file = soundfile.SoundFile(f, mode='r', closefd=True)
            decs_text = "%s kHz  %s  %s" % (load_file.samplerate/1000, chs[load_file.channels-1], load_file.subtype)
            item = QtWidgets.QTableWidgetItem(decs_text)
            item.setTextAlignment(QtCore.Qt.AlignHCenter)
            table.setItem(table.rowCount()-1, 2, item)

    def _files_remove_selected(self):
        indexes = self.table_widget_processes.selectedIndexes()
        if len(indexes) <= 0:
            return
        for i in indexes:
            self.job.file_remove(self.table_widget_files.item(i, 0).text())
            self.table_widget_files.removeRow(i)

    def _files_clear_table(self):
        while self.table_widget_files.rowCount():
            self.table_widget_files.removeRow(0)

    def _files_remove_all(self):
        self._files_clear_table()
        self.job.files_remove_all()

    def _files_out_folder_click(self):
        dir_name = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Open Directory",
            self._files_out_last_path,
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks
        )
        self.line_edit_out_folder.setText(dir_name)


    # -------------------------------------------------------------------------

    def play_start_click(self):
        self._play_position_change_start_flag = False
        self.play_start_thread()

    def play_start_thread(self, position=0):
        t = threading.Thread(target=self.play_start, args=(position,))
        t.daemon = True  # thread dies when main thread exits.
        t.start()

    def play_start(self, position=0):

        file_index = self.table_widget_files.currentRow()
        if file_index < 0:
            return

        self.button_play_start.setEnabled(False)
        self.button_play_stop.setEnabled(True)
        self.table_widget_files.setEnabled(False)

        self.play_start_pos_slider = self.horizontal_slider_play.value()
        play_start_pos = self.play_start_pos_slider / self.horizontal_slider_play.maximum()

        try:
            self.play_chain.start(
                filename=self.job.in_files[file_index],
                audio_device=self.combo_box_sound_device.currentText(),
                channels=2,
                vst_host=self.main_worker.host(),
                vst_plugins_chain=self.job.vst_plugins_chain,
                start=play_start_pos
            )
        except Exception as e:
            self.logger.error(str(e))
            self.play_chain.stop()


    def play_stop_click(self):
        self.play_chain.stop()

    def play_stop_slot(self):
        self.button_play_start.setEnabled(True)
        self.button_play_stop.setEnabled(False)
        self.table_widget_files.setEnabled(True)
        if self.horizontal_slider_play.value() >= self.horizontal_slider_play.maximum()-1:
            self.horizontal_slider_play.setValue(self.horizontal_slider_play.minimum())

    def play_selected(self, row, column):
        if row < 0:
            self.button_play_start.setEnable(False)
            return
        self.group_box_play.setTitle(self.group_box_play.title().split(" - ")[0] + " - [ %s ]" % os.path.basename(self.job.in_files[row]))
        self.button_play_start.setEnabled(True)
        self.horizontal_slider_play.setEnabled(True)

    def play_progress_update(self, procent_value):
        if self.play_chain.is_active() and not self._play_position_change_start_flag:
            slider_val = int(self.play_start_pos_slider + procent_value*self.horizontal_slider_play.maximum())
            self.horizontal_slider_play.setValue(slider_val)
        # print(self.horizontal_slider_play.value())

    def play_position_change_start(self):
        self._play_position_change_start_flag = True

    def play_position_change_end(self):
        if self.play_chain.is_active():
            self.play_chain.stop()
            sleep(0.25)
            self.play_start_thread()
            self._play_position_change_start_flag = False

    # -------------------------------------------------------------------------


    def _normilize_settings(self):
        return {
            "enable": self.check_box_normalize_enable.isChecked(),
            "target_rms": float(self.line_edit_normalize_rms_level.text()),
            "error_db": float(self.line_edit_normalize_error_db.text())
        }

    def _plugin_add(self, pathname):
        try:
            plugin = self.main_worker.vst_dll_load(pathname, self.logger)
            self.logger.debug(plugin.info())
        except Exception as e:
            self.logger.error('[ ERROR ] while load "%s"' % os.path.basename(pathname))
            self.logger.debug(str(e))
            return

        self.job.vst_add_to_chain(plugin)
        #
        table = self.table_widget_processes
        #
        index = table.rowCount()
        table.setRowCount(index+1)
        #
        item = QtWidgets.QTableWidgetItem(plugin.name)
        item.setTextAlignment(QtCore.Qt.AlignHCenter)
        table.setItem(index, 0, item)
        #
        self.logger.info('Add VST - "%s"' % plugin.name)
        #
        return plugin

    def _plugin_add_click(self):
        vst_dll, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'open VST plugin file',
            self._vst_last_path,
            'VST dll (*.dll)'
        )
        if not vst_dll:
            return
        self._vst_last_path = QtCore.QFileInfo(vst_dll).path()
        self._plugin_add(vst_dll)

    def _plugin_change_click(self):
        index = self.table_widget_processes.currentRow()
        w = VSTPluginWindow(self.job.vst_plugins_chain[index], parent=self)
        w.show()

    def _plugin_up_click(self):
        #
        table = self.table_widget_processes
        select_row = table.currentRow()

        if select_row <= 0:
            return

        self.job.vst_swap_in_chain(select_row, select_row - 1)

        select_item = table.takeItem(select_row, 0)
        change_item = table.takeItem(select_row - 1, 0)

        table.setItem(select_row - 1, 0, select_item)
        table.setItem(select_row, 0, change_item)

        table.setCurrentCell(select_row - 1, 0, QtCore.QItemSelectionModel.SelectCurrent)

    def _plugin_down_click(self):
        #
        table = self.table_widget_processes
        select_row = table.currentRow()

        if select_row >= table.rowCount()-1:
            return

        self.job.vst_swap_in_chain(select_row, select_row + 1)

        select_item = table.takeItem(select_row, 0)
        change_item = table.takeItem(select_row + 1, 0)

        table.setItem(select_row + 1, 0, select_item)
        table.setItem(select_row, 0, change_item)

        table.setCurrentCell(select_row + 1, 0, QtCore.QItemSelectionModel.SelectCurrent)

    def _plugin_remove_selected_click(self):
        index = self.table_widget_processes.currentRow()
        if index < 0 or index > self.table_widget_processes.rowCount()-1:
            return
        self.table_widget_processes.removeRow(index)
        self.job.vst_remove_from_chain(index)

    def _plugin_remove_all(self):
        while self.table_widget_processes.rowCount():
            self.table_widget_processes.removeRow(0)
        self.job.vst_remove_all()

    # -------------------------------------------------------------------------

    def _tag_data(self):
        return (
            self.line_edit_metadata_author.text(),
            self.line_edit_metadata_artist.text(),
            self.line_edit_metadata_sound_designer.text(),
            self.line_edit_metadata_album_book.text(),
            self.line_edit_metadata_genre.text(),
            self.line_edit_metadata_year.text(),
            self.text_edit_metadata_description.toPlainText(),
            self.line_edit_metadata_image.text()
        )

    def _tag_metadata_image_select_click(self):
        image_file, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'Open File',
            self._files_last_path,
            'Images (*.bmp *.png *.jpg)'
        )
        if not len(image_file):
            return
        self.line_edit_metadata_image.setText(image_file[0])
        try:
            pixmap = QtGui.QPixmap(image_file[0])
            coeff = pixmap.width() / 450
            self.label_metadata_image_show.setMinimumWidth(450)
            self.label_metadata_image_show.setMaximumWidth(450)
            self.label_metadata_image_show.setMinimumHeight(int(pixmap.height() / coeff))
            self.label_metadata_image_show.setMaximumHeight(int(pixmap.height() / coeff))
            self.label_metadata_image_show.setPixmap(pixmap)
        except Exception as e:
            self.logger.error("Error on draw the selected image [%s]" % str(e))

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
        if not self.button_start_work.isEnabled() or not len(self.job.in_files):
            return
        self.button_start_work.setEnabled(False)
        self.button_measurment.setEnabled(False)
        self.button_stop_work.setEnabled(True)
        self.tab_input_files.setEnabled(False)
        self.tab_vst_process.setEnabled(False)
        self.tab_metadata.setEnabled(False)
        # set animation is fastest
        self.anim.timer.setInterval(750)

        # block until all tasks are done
        self.nqueue.join()

        # update all job parameters
        self.job.update(
            normilize_params=self._normilize_settings(),
            out_folder=self.line_edit_out_folder.text(),
            tag_data=self._tag_data()
        )

        try:
            vst_buffer_size = int(self.line_edit_buffer_size_bytes.text())
        except Exception as e:
            self.logger.warning(
                "VST buffer size is incorrect!"
                "Please set numberic value in range: [ 1024..65536 ] bytes\n"
                "Set the default buffer size: [ 1024 ]"
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
        self.tab_input_files.setEnabled(True)
        self.tab_vst_process.setEnabled(True)
        self.tab_metadata.setEnabled(True)
        self.anim.timer.setInterval(2000)

    old_progr = 0
    def _progress_slot(self, progress):
        if (progress - self.old_progr) > 20:
            self.anim.timer.setInterval(600 - (progress * 5))
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
        if reply == QtWidgets.QMessageBox.No:
            event.ignore()
            return
        # save GUI state
        self._ui_save_settings()
        event.accept()

    def process_events(self):
        QtWidgets.QApplication.processEvents()


def main():
    freeze_support()
    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QApplication.setStyle(QtWidgets.QStyleFactory.create('Fusion'))
    ex = neil_vst_gui_window()
    sys.exit(app.exec_())


# program start here
if __name__ == '__main__':
    main()
