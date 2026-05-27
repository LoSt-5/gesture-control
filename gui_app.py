import sys
import json
import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel,
    QDialog, QListWidget, QListWidgetItem, QHBoxLayout, QMessageBox,
    QSpinBox, QComboBox, QLineEdit, QRadioButton, QButtonGroup, QGroupBox,
    QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap
from gestures import GestureController

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    gesture_info_signal = pyqtSignal(dict)          

    def __init__(self, gesture_controller):
        super().__init__()
        self.gesture_controller = gesture_controller
        self._run_flag = True
        self.capture = cv2.VideoCapture(0)

    def run(self):
        import mediapipe as mp
        mp_holistic = mp.solutions.holistic
        holistic_model = mp_holistic.Holistic(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        mp_drawing = mp.solutions.drawing_utils

        while self._run_flag:
            ret, frame = self.capture.read()
            if not ret:
                continue

            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            results = holistic_model.process(image_rgb)
            image_rgb.flags.writeable = True
            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

            gesture_info = self.gesture_controller.process_hands(
                results.right_hand_landmarks,
                results.left_hand_landmarks,
                image_bgr
            )

            if results.right_hand_landmarks:
                mp_drawing.draw_landmarks(
                    image_bgr,
                    results.right_hand_landmarks,
                    mp_holistic.HAND_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(255,0,0), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2)
                )
            if results.left_hand_landmarks:
                mp_drawing.draw_landmarks(
                    image_bgr,
                    results.left_hand_landmarks,
                    mp_holistic.HAND_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(0,0,255), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2)
                )

            # Переворачиваем изображение для естественного отображения
            image_bgr = cv2.flip(image_bgr, 1)

            # Формируем информацию о жесте
            if gesture_info:
                direction, fingers_count = gesture_info
                if direction:
                    self.gesture_info_signal.emit({
                        'direction': direction,
                        'fingers': fingers_count,
                        'gesture_active': self.gesture_controller.is_gesture_active()
                    })
                else:
                    self.gesture_info_signal.emit({
                        'direction': None,
                        'fingers': fingers_count,
                        'gesture_active': self.gesture_controller.is_gesture_active()
                    })
            else:
                self.gesture_info_signal.emit({
                    'direction': None,
                    'fingers': 0,
                    'gesture_active': False
                })

            # Отправляем кадр
            self.change_pixmap_signal.emit(image_bgr)

        self.capture.release()
        holistic_model.close()
        cv2.destroyAllWindows()

    def stop(self):
        self._run_flag = False
        self.wait()


# ------------------- Окно отслеживания жестов (камера) -------------------
class CameraWindow(QMainWindow):
    def __init__(self, gesture_controller):
        super().__init__()
        self.gesture_controller = gesture_controller
        self.setWindowTitle("Gesture Control - Camera")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Виджет для видео
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        layout.addWidget(self.image_label)

        # Информационная панель
        self.info_label = QLabel("Gesture: -- | Fingers: 0 | Status: INACTIVE")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        # Кнопка остановки
        self.stop_button = QPushButton("Stop & return to menu")
        self.stop_button.clicked.connect(self.stop_camera)
        layout.addWidget(self.stop_button)

        # Запуск потока
        self.thread = VideoThread(self.gesture_controller)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.gesture_info_signal.connect(self.update_gesture_info)
        self.thread.start()

    def update_image(self, cv_img):
        """Преобразует cv изображение в QPixmap и отображает"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(qt_image).scaled(
            self.image_label.width(), self.image_label.height(), Qt.AspectRatioMode.KeepAspectRatio
        ))

    def update_gesture_info(self, info):
        direction = info.get('direction')
        fingers = info.get('fingers', 0)
        active = info.get('gesture_active', False)
        dir_text = direction if direction else "--"
        status_text = "ACTIVE" if active else "INACTIVE"
        self.info_label.setText(f"Gesture: {dir_text} | Fingers: {fingers} | Status: {status_text}")

    def stop_camera(self):
        self.thread.stop()
        self.close()

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()


# ------------------- Диалог редактирования одного жеста -------------------
class GestureEditDialog(QDialog):
    def __init__(self, gesture_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Gesture" if gesture_data else "New Gesture")
        self.gesture_data = gesture_data.copy() if gesture_data else {
            "hand": "right_hand",
            "fingers": 1,
            "direction": "UP",
            "action": []
        }
        self.result_data = None

        layout = QVBoxLayout(self)

        # Выбор руки
        hand_group = QGroupBox("Hand")
        hand_layout = QHBoxLayout()
        self.left_radio = QRadioButton("Left hand")
        self.right_radio = QRadioButton("Right hand")
        hand_layout.addWidget(self.left_radio)
        hand_layout.addWidget(self.right_radio)
        if self.gesture_data["hand"] == "left_hand":
            self.left_radio.setChecked(True)
        else:
            self.right_radio.setChecked(True)
        hand_group.setLayout(hand_layout)
        layout.addWidget(hand_group)

        # Количество пальцев
        fingers_layout = QFormLayout()
        self.fingers_spin = QSpinBox()
        self.fingers_spin.setMinimum(1)
        self.fingers_spin.setMaximum(5)
        self.fingers_spin.setValue(self.gesture_data["fingers"])
        fingers_layout.addRow("Fingers:", self.fingers_spin)
        layout.addLayout(fingers_layout)

        # Направление
        direction_layout = QFormLayout()
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["UP", "DOWN", "LEFT", "RIGHT"])
        current_dir = self.gesture_data["direction"]
        idx = self.direction_combo.findText(current_dir)
        if idx >= 0:
            self.direction_combo.setCurrentIndex(idx)
        direction_layout.addRow("Direction:", self.direction_combo)
        layout.addLayout(direction_layout)

        # Действие (клавиши через запятую)
        action_layout = QFormLayout()
        self.action_edit = QLineEdit()
        self.action_edit.setText(", ".join(self.gesture_data["action"]))
        self.action_edit.setPlaceholderText("e.g. win, d")
        action_layout.addRow("Action keys:", self.action_edit)
        layout.addLayout(action_layout)

        # Кнопки диалога
        button_box = QDialogButtonBox()
        save_btn = button_box.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        delete_btn = button_box.addButton("Delete", QDialogButtonBox.ButtonRole.DestructiveRole)
        cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)

        save_btn.clicked.connect(self.save_gesture)
        delete_btn.clicked.connect(self.delete_gesture)
        cancel_btn.clicked.connect(self.reject)

        layout.addWidget(button_box)

    def save_gesture(self):
        # Считываем данные
        hand = "left_hand" if self.left_radio.isChecked() else "right_hand"
        fingers = self.fingers_spin.value()
        direction = self.direction_combo.currentText()
        action_str = self.action_edit.text().strip()
        # Преобразуем строку в список, удаляя пробелы
        action = [a.strip() for a in action_str.split(",") if a.strip()] if action_str else []
        self.result_data = {
            "hand": hand,
            "fingers": fingers,
            "direction": direction,
            "action": action
        }
        self.accept()

    def delete_gesture(self):
        # Сигнализируем удаление (возвращаем None)
        self.result_data = None
        self.accept()

    def get_gesture(self):
        return self.result_data


# ------------------- Окно редактора конфигурации -------------------
class ConfigEditorWindow(QMainWindow):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.gestures = []  # список жестов
        self.setWindowTitle("Edit Gesture Configuration")
        self.setGeometry(150, 150, 600, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Заголовок
        title = QLabel("Gestures list:")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        # Список жестов
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.edit_gesture)
        layout.addWidget(self.list_widget)

        # Кнопки
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add gesture")
        self.add_button.clicked.connect(self.add_gesture)
        self.save_button = QPushButton("Save config")
        self.save_button.clicked.connect(self.save_config)
        self.back_button = QPushButton("Back to menu")
        self.back_button.clicked.connect(self.close)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.back_button)
        layout.addLayout(button_layout)

        # Загружаем конфиг
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.gestures = json.load(f)
        else:
            self.gestures = []
        self.refresh_list()

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.gestures, f, indent=4, ensure_ascii=False)
        QMessageBox.information(self, "Saved", "Configuration saved successfully.")

    def refresh_list(self):
        self.list_widget.clear()
        for i, gesture in enumerate(self.gestures):
            # Отображаемое описание жеста
            desc = (f"{i+1}. Hand: {gesture['hand'].replace('_',' ').title()}, "
                    f"Fingers: {gesture['fingers']}, Direction: {gesture['direction']}, "
                    f"Action: {', '.join(gesture['action']) if gesture['action'] else 'None'}")
            item = QListWidgetItem(desc)
            item.setData(Qt.ItemDataRole.UserRole, i)  # храним индекс
            self.list_widget.addItem(item)

    def add_gesture(self):
        dialog = GestureEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_gesture = dialog.get_gesture()
            if new_gesture:  # не удаление
                self.gestures.append(new_gesture)
                self.refresh_list()

    def edit_gesture(self, item):
        index = item.data(Qt.ItemDataRole.UserRole)
        gesture_copy = self.gestures[index].copy()
        dialog = GestureEditDialog(gesture_copy, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_gesture()
            if result is None:  # удаление
                del self.gestures[index]
            else:
                self.gestures[index] = result
            self.refresh_list()


# ------------------- Главное меню -------------------
class MainMenu(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gesture Control App")
        self.setGeometry(300, 200, 400, 300)

        # Инициализация контроллера жестов (будет использоваться общий)
        self.gesture_controller = GestureController()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        title = QLabel("Gesture Control System")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self.start_btn = QPushButton("Start tracking")
        self.edit_btn = QPushButton("Edit config")
        self.exit_btn = QPushButton("Exit")

        self.start_btn.clicked.connect(self.start_tracking)
        self.edit_btn.clicked.connect(self.edit_config)
        self.exit_btn.clicked.connect(self.close)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.edit_btn)
        layout.addWidget(self.exit_btn)

    def start_tracking(self):
        # Перезагружаем конфиг перед запуском (на случай изменений)
        self.gesture_controller = GestureController()
        self.camera_window = CameraWindow(self.gesture_controller)
        self.camera_window.show()
        self.hide()  # скрываем главное меню
        # При закрытии окна камеры возвращаем меню
        self.camera_window.destroyed.connect(self.show)

    def edit_config(self):
        self.config_editor = ConfigEditorWindow("gestures_config.json")
        self.config_editor.show()

    def closeEvent(self, event):
        # При выходе из главного меню закрываем всё приложение
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    menu = MainMenu()
    menu.show()
    sys.exit(app.exec())