
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui


class WaveWidget(QtWidgets.QGraphicsView):
    """docstring for WaveWidget"""

    change_play_position_clicked = QtCore.pyqtSignal(float)


    def __init__(self, logger=None, parent=None):
        super(WaveWidget, self).__init__(parent=parent)

        self.logger = logger

        # --- size
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.verticalScrollBar().setDisabled(True)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setMaximumSize(2048, 40)

        # --- scene
        self.scene = QtWidgets.QGraphicsScene(0, 0, self.width(), self.height())
        self.scene.setBackgroundBrush( QtGui.QBrush(QtGui.QColor(192, 200, 192, 32)) )

        # --- play rect
        self.play_rect = QtWidgets.QGraphicsRectItem(0,0,1,1)
        self.play_rect.setPos(0, 0)
        brush = QtGui.QBrush(QtGui.QColor(128, 128, 255, 32))
        self.play_rect.setBrush(brush)
        # define the pen
        pen = QtGui.QPen(QtGui.QColor(192, 0, 0, 255))
        pen.setWidth(1)
        self.play_rect.setPen(pen)
        self.scene.addItem(self.play_rect)

        # --- line pen
        self.line_pen = QtGui.QPen(QtGui.QColor(16, 24, 24, 255))
        self.line_pen.setWidth(1)
        #
        self.setScene(self.scene)
        #
        self.setRenderHints(QtGui.QPainter.Antialiasing);
        #
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        #
        self.wave_data = []
        self.play_position = 0

    # -------------------------------------------------------------------------

    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.Paint:
            self.paintEvent(event)
        if event.type() == QtCore.QEvent.Resize:
            self.update_view()
        return super().viewportEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and event.pos() in self.rect():
            new_play_pos = event.pos().x() / self.width()
            self.set_play_position(new_play_pos)
            self.change_play_position_clicked.emit(new_play_pos)

    # -------------------------------------------------------------------------

    def update_view(self):
        #
        width = self.width()
        height = self.height()
        #
        [ self.scene.removeItem(item) for item in self.scene.items() if item != self.play_rect ]
        #
        self.scene.setSceneRect(0, 0, width, height)
        # self.play_rect.setRect(-1, -1, width/3, height)
        #
        if not len(self.wave_data):
            return
        #
        block_size = width
        blocks = np.array_split(self.wave_data, block_size)

        lines = []
        x = 0
        for block in blocks:
            y1 = np.min(block)
            y2 = np.max(block)

            y1 = ((height//2 - 4) * y1) + height//2
            y2 = ((height//2 - 4) * y2) + height//2

            # print(y1, y2)
            line = QtWidgets.QGraphicsLineItem(x, y1, x, y2)
            line.setPen(self.line_pen)
            self.scene.addItem( line )
            x += 1
        # update play position
        self.set_play_position(self.play_position)

    # -------------------------------------------------------------------------

    def set_wave_file(self, filepath):
        import soundfile
        try:
            data, samplerate = soundfile.read(filepath, always_2d=True)
            self.wave_data, _ = data[0::2], data[1::2]
        except Exception as e:
            self.wave_data = []
            self.logger.warning('Error open "%s" file, set the empty list data for "wave_data"' % filepath)
        self.update_view()

    def set_play_position(self, position):
        # limit
        if position <= 0:
            position = 0.0001
        elif position > 1.0:
            position = 1.0
        #
        self.play_position = position
        self.play_rect.setRect(-1, -1, self.width()*position, self.height())

    def get_play_position(self):
        return self.play_position
