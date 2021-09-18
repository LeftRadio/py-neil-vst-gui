#!python3
import sys
from PyQt5 import QtCore, QtGui, QtWidgets


class StateSwitchEvent(QtCore.QEvent):
    StateSwitchType = QtCore.QEvent.User + 256

    def __init__(self, rand=0):
        super(StateSwitchEvent, self).__init__(StateSwitchEvent.StateSwitchType)

        self.m_rand = rand

    def rand(self):
        return self.m_rand


class QGraphicsRectWidget(QtWidgets.QGraphicsWidget):
    def __init__(self, color):
        super(QGraphicsRectWidget, self).__init__()
        self.color = color

    def paint(self, painter, option, widget):
        painter.fillRect(self.rect(), self.color)


class StateSwitchTransition(QtCore.QAbstractTransition):
    def __init__(self, rand):
        super(StateSwitchTransition, self).__init__()
        self.m_rand = rand

    def eventTest(self, event):
        return (event.type() == StateSwitchEvent.StateSwitchType and
                event.rand() == self.m_rand)

    def onTransition(self, event):
        pass


class StateSwitcher(QtCore.QState):
    def __init__(self, machine):
        super(StateSwitcher, self).__init__(machine)

        self.m_stateCount = 0
        self.m_lastIndex = 0

    def onEntry(self, event):
        n = QtCore.qrand() % self.m_stateCount + 1
        while n == self.m_lastIndex:
            n = QtCore.qrand() % self.m_stateCount + 1

        self.m_lastIndex = n
        self.machine().postEvent(StateSwitchEvent(n))

    def onExit(self, event):
        pass

    def addState(self, state, animation):
        self.m_stateCount += 1
        trans = StateSwitchTransition(self.m_stateCount)
        trans.setTargetState(state)
        self.addTransition(trans)
        trans.addAnimation(animation)



class RectsAnimate(object):
    def __init__(self, x_max, y_max, back_color, parent=None):

        self.scene_rect = QtCore.QRectF(0, 0, x_max, y_max)
        self.scene = QtWidgets.QGraphicsScene(self.scene_rect, parent=parent)

        colors = [QtGui.QColor.fromRgb(54, 64, 74), QtCore.Qt.lightGray, QtGui.QColor.fromRgb(54, 64, 74), QtCore.Qt.lightGray]
        self.anim_butt = [ QGraphicsRectWidget(c) for c in colors ]
        for b in self.anim_butt:
            self.scene.addItem(b)

        self.window = QtWidgets.QGraphicsView(self.scene)
        self.window.setFrameStyle(0)
        self.window.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.window.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.window.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.window.setMaximumWidth(x_max)
        self.window.setMaximumHeight(y_max)

        self.machine = QtCore.QStateMachine()

        self.group = QtCore.QState()
        self.timer = QtCore.QTimer()
        self.timer.setInterval(2000)
        self.timer.setSingleShot(True)
        self.group.entered.connect(self.timer.start)

        # set states positions
        anim_state_rects = [ [QtCore.QRect(x_max*xp/6, y_max*yp/4, 8, 8) for xp in range(4)] for yp in range(4) ]
        self.states = [ self.createGeometryState(
                                self.anim_butt[0], anim_state_rects[0][j], self.anim_butt[1], anim_state_rects[1][j],
                                self.anim_butt[2], anim_state_rects[2][j], self.anim_butt[3], anim_state_rects[3][j],
                                self.group
                            ) for j in range(4) ]

        self.group.setInitialState(self.states[0])

        self.animationGroup = QtCore.QParallelAnimationGroup()
        self.anim = QtCore.QPropertyAnimation(self.anim_butt[3], b'geometry')
        self.anim.setDuration(1250)
        self.anim.setEasingCurve(QtCore.QEasingCurve.InBack)
        self.animationGroup.addAnimation(self.anim)

        self.subGroup = QtCore.QSequentialAnimationGroup(self.animationGroup)
        self.subGroup.addPause(100)
        self.anim = QtCore.QPropertyAnimation(self.anim_butt[2], b'geometry')
        self.anim.setDuration(1000)
        self.anim.setEasingCurve(QtCore.QEasingCurve.OutElastic)
        self.subGroup.addAnimation(self.anim)

        self.subGroup = QtCore.QSequentialAnimationGroup(self.animationGroup)
        self.subGroup.addPause(500)
        self.anim = QtCore.QPropertyAnimation(self.anim_butt[1], b'geometry')
        self.anim.setDuration(500)
        self.anim.setEasingCurve(QtCore.QEasingCurve.OutElastic)
        self.subGroup.addAnimation(self.anim)

        self.subGroup = QtCore.QSequentialAnimationGroup(self.animationGroup)
        self.subGroup.addPause(750)
        self.anim = QtCore.QPropertyAnimation(self.anim_butt[0], b'geometry')
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QtCore.QEasingCurve.OutElastic)
        self.subGroup.addAnimation(self.anim)

        self.stateSwitcher = StateSwitcher(self.machine)
        self.group.addTransition(self.timer.timeout, self.stateSwitcher)
        for j in range(4):
            self.stateSwitcher.addState(self.states[j], self.animationGroup)

        self.machine.addState(self.group)
        self.machine.setInitialState(self.group)
        self.machine.start()

    def createGeometryState(self, w1, rect1, w2, rect2, w3, rect3, w4, rect4, parent):
        result = QtCore.QState(parent)
        result.assignProperty(w1, 'geometry', rect1)
        result.assignProperty(w1, 'geometry', rect1)
        result.assignProperty(w2, 'geometry', rect2)
        result.assignProperty(w3, 'geometry', rect3)
        result.assignProperty(w4, 'geometry', rect4)
        return result

    def loadImage(self, filepath):

        self._itemImage = self._scene.addPixmap(QtGui.QPixmap(filepath))
        self._itemImage.setFlag(QGraphicsItem.ItemIsMovable)
        self._itemImage.setScale(0.1)         # Default load factor

        size = self._itemImage.pixmap().size()
        # Adjust the image in the middle
        self._itemImage.setPos(
            -size.width() * self._itemImage.scale() / 2,
            -size.height() * self._itemImage.scale() / 2
        )
