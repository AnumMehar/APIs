from PyQt5.QtWidgets import QFrame, QVBoxLayout

class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(520)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 26px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(18)
        self.layout.setContentsMargins(40, 40, 40, 40)

