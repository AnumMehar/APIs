import requests
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit,
    QPushButton, QComboBox,
    QVBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from Ui_card import Card
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QHBoxLayout

# ✅ FastAPI endpoint
API_BASE = "http://127.0.0.1:8000/users"


class UserInfoScreen(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.n_id = None  # ✅ Will store backend N_ID

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        card = Card()
        root.addWidget(card)

        # ---------------- Image / Logo ----------------
        logo = QLabel()
        pixmap = QPixmap("img1.png")
        pixmap = pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignCenter)
        card.layout.addWidget(logo)

        # ---------------- Title ----------------
        title = QLabel("User Information")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #472573;")
        card.layout.addWidget(title)

        # ---------------- Inputs ----------------
        self.name = QLineEdit()
        self.name.setPlaceholderText("Full Name")
        card.layout.addWidget(self.name)

        self.age = QLineEdit()
        self.age.setPlaceholderText("Age")
        card.layout.addWidget(self.age)

        self.gender = QComboBox()
        self.gender.addItems(["Select Gender", "Male", "Female"])
        card.layout.addWidget(self.gender)

        self.cnic = QLineEdit()
        self.cnic.setPlaceholderText("CNIC")
        card.layout.addWidget(self.cnic)

        self.setStyleSheet("""
        QLineEdit, QComboBox {
            border: 2px solid #D6C7E7;
            border-radius: 18px;
            padding: 10px;
            font-size: 16px;
            background-color: #FAF7FF;
        }

        QLineEdit:focus, QComboBox:focus {
            border: 2px solid #472573;
            background-color: #FFFFFF;
        }

        QComboBox::drop-down {
            border: none;
        }

        QComboBox QAbstractItemView {
            border-radius: 10px;
        }
        """)

        # # # ---------------- Next Button ----------------
        # # next_btn = QPushButton("Next")
        # # next_btn.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        # # next_btn.clicked.connect(self.next)
        # # card.layout.addWidget(next_btn)
        # # ---------------- Buttons ----------------
        # next_btn = QPushButton("Next")
        # next_btn.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        # next_btn.clicked.connect(self.next)
        #
        #
        # cancel_btn = QPushButton("Cancel")
        # cancel_btn.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        # # cancel_btn.clicked.connect(self.close)
        # cancel_btn.clicked.connect(QApplication.quit)
        #
        # card.layout.addWidget(next_btn)
        # card.layout.addWidget(cancel_btn)

        # ---------------- Buttons ----------------
        btn_layout = QHBoxLayout()

        # next_btn = QPushButton("Next")
        # next_btn.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        # next_btn.clicked.connect(self.next)
        next_btn = QPushButton("Next")
        next_btn.setFixedHeight(45)
        next_btn.setStyleSheet("""
        QPushButton {
            background-color: #472573;
            color: white;
            border-radius: 20px;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
        }
        QPushButton:hover {
            background-color: #6A3FA0;
        }
        """)
        next_btn.clicked.connect(self.next)

        # cancel_btn = QPushButton("Cancel")
        # cancel_btn.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        # cancel_btn.clicked.connect(self.close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(45)
        cancel_btn.setStyleSheet("""
        QPushButton {
            background-color: #472573;
            color: white;
            border-radius: 20px;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
        }
        QPushButton:hover {
            background-color: #6A3FA0;
        }
        """)
        cancel_btn.clicked.connect(self.close)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(next_btn)

        card.layout.addLayout(btn_layout)

    def next(self):
        if (
            not self.name.text()
            or not self.age.text()
            or self.gender.currentIndex() == 0
            or not self.cnic.text()
        ):
            QMessageBox.warning(self, "Error", "Please complete all fields")
            return

        try:
            payload = {
                "name": self.name.text(),
                "age": int(self.age.text()),
                "gender": self.gender.currentText(),
                "national_id": self.cnic.text()
            }

            response = requests.post(API_BASE + "/", json=payload)

            if response.status_code == 200:
                data = response.json()

                # ✅ Save N_ID from backend
                self.n_id = data.get("N_ID")

                QMessageBox.information(
                    self,
                    "Success",
                    data.get("message", "User registered successfully.")
                )

                # ✅ Pass N_ID to main window
                self.main.go_to_main_menu(self.n_id)

            else:
                QMessageBox.critical(self, "Error", response.text)

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))