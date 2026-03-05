
# test_main.py
import os
from User_form import UserInfoScreen  # import your form

# Fix Qt plugin conflict: OpenCV bundles its own Qt which clashes with PyQt5.
# Clear the plugin path so PyQt5's own plugins are used instead.
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QGridLayout, QFrame, QHBoxLayout
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSizePolicy
from walking_speed_test_window import WalkingSpeedWindow
from functional_reach_window import *
from seated_forward_bend_window import SeatedForwardBendWindow
from time_up_and_go_test_window import TimeUpAndGoWindow
from standing_one_leg_window import StandingOnOneLegWindow

from KinectNumberWindow import *

from instruction_walking_speed import InstructionWindow as InstrWS
from instruction_functional_reach import InstructionWindow as InstrFR
from instruction_seated_forward_bend import InstructionWindow as InstrSFB
from instruction_time_up_and_go import InstructionWindow as InstrTUG
from instruction_standing_one_leg import InstructionWindow as InstrSOL
from instruction_grip_strength import InstructionWindow as InstrGS

class MainWindow(QWidget):
    def __init__(self, n_id, parent=None):
        super().__init__(parent)
        self.n_id = n_id
        self.selector = parent  # parent = main_window.MainWindow
        self._open_windows = []

        self.setWindowTitle("Main Menu")
        self.resize(1000, 800)
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background-color: #FFF8F0;")

        # === Top row: logos + center subtitle ===
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(12)

        left_logo = QLabel()
        left_logo.setPixmap(
            QPixmap(os.path.join(BASE_DIR, "ncai.png")).scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        left_logo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        center_subtitle = QLabel("Physical Frailty Assessment")
        center_subtitle.setAlignment(Qt.AlignCenter)
        center_subtitle.setFont(QFont("Yu Gothic UI", 48))
        center_subtitle.setStyleSheet("color: #5B2C6F;")
        center_subtitle.setContentsMargins(8, 0, 8, 0)

        right_logo = QLabel()
        right_logo.setPixmap(
            QPixmap(os.path.join(BASE_DIR, "tokyo.png")).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        right_logo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        logo_layout.addWidget(left_logo, 0, Qt.AlignLeft | Qt.AlignVCenter)
        logo_layout.addStretch()
        logo_layout.addWidget(center_subtitle, 0, Qt.AlignCenter)
        logo_layout.addStretch()
        logo_layout.addWidget(right_logo, 0, Qt.AlignRight | Qt.AlignVCenter)

        # === Main title ===
        title = QLabel("Select the Test")
        title.setFont(QFont("Yu Gothic UI", 45))
        title.setStyleSheet("color: #5B2C6F;")
        title.setAlignment(Qt.AlignCenter)
        title.setContentsMargins(0, 8, 0, 8)

        # === Grid of test cards ===
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(24)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setAlignment(Qt.AlignTop)

        for c in range(3):
            grid.setColumnStretch(c, 1)
        for r in range(2):
            grid.setRowStretch(r, 1)

        tests = [
            ("Walking Speed", WalkingSpeedWindow, InstrWS),
            ("Functional Reach", FunctionalReachWindow, InstrFR),
            ("Seated Forward Bend", SeatedForwardBendWindow, InstrSFB),
            ("Timed Up and Go", TimeUpAndGoWindow, InstrTUG),
            ("Standing On \nOne Leg", StandingOnOneLegWindow, InstrSOL),
            ("Grip Strength", KinectNumberWindow, InstrGS),
        ]

        test_images = {
            "Walking Speed": os.path.join(BASE_DIR, "speed.png"),
            "Functional Reach": os.path.join(BASE_DIR, "reach.png"),
            "Seated Forward Bend": os.path.join(BASE_DIR, "seated.png"),
            "Timed Up and Go": os.path.join(BASE_DIR, "ability.png"),
            "Standing On \nOne Leg": os.path.join(BASE_DIR, "standing.png"),
            "Grip Strength": os.path.join(BASE_DIR, "grip.png"),
        }

        for i, (name, test_cls, instr_cls) in enumerate(tests):
            card = QFrame()
            card.setStyleSheet("""
                background-color: #FFFFFF;
                border: 2px solid #472573;
                border-radius: 10px;
            """)
            card.setMinimumHeight(300)

            h_layout = QHBoxLayout(card)
            h_layout.setContentsMargins(16, 16, 16, 16)
            h_layout.setSpacing(16)

            # Image
            image_label = QLabel()
            pixmap = QPixmap(test_images.get(name, "speed.png"))
            image_label.setPixmap(pixmap)
            image_label.setScaledContents(True)
            image_label.setFixedWidth(250)
            image_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            h_layout.addWidget(image_label)

            # Right side: name + (pushed-down) buttons
            v_wrapper = QVBoxLayout()
            v_wrapper.setSpacing(12)

            lbl = QLabel(name)
            lbl.setFont(QFont("Yu Gothic UI", 20))
            lbl.setStyleSheet("border: none;")
            lbl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            v_wrapper.addWidget(lbl, alignment=Qt.AlignHCenter | Qt.AlignTop)

            v_wrapper.addStretch(1)

            title_width = lbl.sizeHint().width() + 20

            btn_start = QPushButton("Start")
            btn_demo = QPushButton("Demo")
            for b in (btn_start, btn_demo):
                b.setFont(QFont("Yu Gothic UI", 18))
                b.setFixedHeight(56)
                b.setFixedWidth(title_width)
                b.setStyleSheet("""
                    QPushButton {
                      background-color: #9a84b7;
                      color: #000;
                      border-radius: 24px;
                    }
                    QPushButton:hover {
                      background-color: #472573;
                      color: #fff;
                    }
                """)

            btn_start.clicked.connect(lambda _, c=test_cls: self.launch_test(c))
            btn_demo.clicked.connect(lambda _, c=instr_cls: self.launch_demo(c))

            button_container = QVBoxLayout()
            button_container.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
            button_container.setSpacing(10)
            button_container.addWidget(btn_start)
            button_container.addWidget(btn_demo)

            v_wrapper.addLayout(button_container)
            v_wrapper.addSpacing(4)

            h_layout.addLayout(v_wrapper)
            grid.addWidget(card, i // 3, i % 3)

        # === Back button ===
        back_btn = QPushButton("Back")
        back_btn.setFont(QFont("Yu Gothic UI", 14))
        back_btn.setFixedSize(120, 40)
        back_btn.setStyleSheet("""
            QPushButton {
              background-color: #9a84b7; color: white; border-radius: 20px;
            }
            QPushButton:hover {
              background-color: #472573;
            }
        """)
        back_btn.clicked.connect(self._go_back)

        # === Page assembly with uniform outer padding ===
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)
        layout.addLayout(logo_layout)
        layout.addWidget(title)
        layout.addLayout(grid)
        layout.addWidget(back_btn, alignment=Qt.AlignCenter)

    def launch_test(self, cls):
        self.hide()
        # win = cls(self)
        win = cls(self.n_id, self)
        self._open_windows.append(win)
        win.showFullScreen()

    def launch_demo(self, cls):
        demo = cls()
        self._open_windows.append(demo)
        demo.show()

    def _go_back(self):
        self.hide()
        if self.selector:
            self.selector.showFullScreen()

    def closeEvent(self, event):
        try:
            if self.selector and not self.selector.isVisible():
                self.selector.showFullScreen()
        finally:
            super().closeEvent(event)


# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     mw = MainWindow()
#     mw.showFullScreen()
#     sys.exit(app.exec_())



class AppController(QWidget):
    def __init__(self):
        super().__init__()
        self.user_screen = UserInfoScreen(self)
        self.main_menu = None

    def go_to_main_menu(self, n_id):
        self.user_screen.hide()
        self.main_menu = MainWindow(n_id)
        self.main_menu.showFullScreen()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = AppController()
    controller.user_screen.showFullScreen()
    sys.exit(app.exec_())