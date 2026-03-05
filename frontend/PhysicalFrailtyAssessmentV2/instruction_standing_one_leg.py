import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

class InstructionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("One Leg Stand Test Instructions")
        self.setFixedSize(600, 400)
        self.setStyleSheet("background-color: #FFF8F0;")

        lbl = QLabel("One Leg Stand Test Instructions")
        lbl.setFont(QFont("Yu Gothic UI", 20))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #5B2C6F;")

        text = QLabel(
            "1. Stand upright with feet together\n"
            "2. Raise one leg and hold as long as you can\n"
            "3. Lower and repeat with the other leg\n"
        )
        text.setFont(QFont("Yu Gothic UI", 14))
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignTop)
        text.setStyleSheet("color: #333; margin: 20px;")

        btn = QPushButton("Back")
        btn.setFont(QFont("Yu Gothic UI", 14))
        btn.setStyleSheet("""
            QPushButton {
                        background-color: #472573;
                        color: #FFFFFF;
                        border-radius: 20px;
                    }
                    QPushButton:hover {
                        background-color: #705593;
                    }

        """
        )
        btn.clicked.connect(self.close)

        lay = QVBoxLayout(self)
        lay.addWidget(lbl)
        lay.addWidget(text)
        lay.addStretch()
        lay.addWidget(btn, alignment=Qt.AlignCenter)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = InstructionWindow()
    w.show()
    sys.exit(app.exec_())
