import pyautogui
import time
from collections import deque
import cv2
import json
import os


class GestureController:



    def __init__(self, movement_threshold=80, history_length=20, action_cooldown=5, config_file='gestures_config.json'):
        """
        Инициализация контроллера жестов
        
        Args:
            config_file: Путь к JSON файлу с конфигурацией жестов
            movement_threshold: Порог движения в пикселях
            history_length: Длина истории позиций для отслеживания
            action_cooldown: Задержка между действиями в секундах
        """
        self.MOVEMENT_THRESHOLD = movement_threshold
        self.ACTION_COOLDOWN = action_cooldown
        self.HISTORY_LENGTH = history_length
        
        # Для отслеживания позиции руки
        self.hand_positions = deque(maxlen=self.HISTORY_LENGTH)
        self.gesture_active = False
        self.last_action_time = 0
        self.current_hand = None
        self.current_fingers_count = 0
        
        
        self.config_file = config_file
    
        # Загрузка конфигурации
        self.config = None
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        # Словарь для быстрого поиска действий
    






    def count_fingers(self, hand_landmarks):
        """Подсчет поднятых пальцев на руке"""
        if hand_landmarks is None:
            return 0
        
        # Индексы ключевых точек для пальцев
        finger_tips = [4, 8, 12, 16, 20]  # Кончики пальцев
        finger_pips = [3, 6, 10, 14, 18]  # Суставы
        
        finger_count = 0
        
        # Определяем активную руку (левую или правую)
        # Для этого используем позицию запястья относительно среднего пальца
        # Если запястье находится левее среднего пальца, то это правая рука, иначе левая
        wrist_x = hand_landmarks.landmark[0].x
        middle_mcp_x = hand_landmarks.landmark[9].x
        
        is_right_hand = wrist_x < middle_mcp_x
        
        
        # Большой палец - сравниваем по оси X в зависимости от руки
        if is_right_hand:
            # Для правой руки
            if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
                finger_count += 1
        else:
            # Для левой руки
            if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
                finger_count += 1
        
        # Остальные пальцы - сравниваем по оси Y (кончик выше сустава = палец поднят)
        for tip, pip in zip(finger_tips[1:], finger_pips[1:]):
            if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[pip].y:
                finger_count += 1
        
        return finger_count
    

    



    def detect_hand_and_fingers(self, right_hand_landmarks, left_hand_landmarks):
        """
        Функция 1: Определяет какая рука и сколько на ней пальцев
        
        Returns:
            dict: {"hand": "left_hand"/"right_hand", "fingers": 0-5} или None если руки не обнаружены
        """
        hand_info = {}
        
        # Проверяем правую руку
        if right_hand_landmarks:
            right_fingers = self.count_fingers(right_hand_landmarks)
            hand_info["right_hand"] = right_fingers
        
        # Проверяем левую руку
        if left_hand_landmarks:
            left_fingers = self.count_fingers(left_hand_landmarks)
            hand_info["left_hand"] = left_fingers
        
        # Если не обнаружено ни одной руки
        if not hand_info:
            return None
        
        # Возвращаем информацию о всех обнаруженных руках
        return hand_info
    







    
    def get_hand_position(self, hand_landmarks):
        """Получение средней позиции ладони"""
        if hand_landmarks is None:
            return None
        
        # Используем запястье (landmark 0) и среднюю точку ладони
        wrist = hand_landmarks.landmark[0]
        middle_mcp = hand_landmarks.landmark[9]  # Основание среднего пальца
        
        # Средняя позиция
        avg_x = (wrist.x + middle_mcp.x) / 2
        avg_y = (wrist.y + middle_mcp.y) / 2
        
        return (avg_x, avg_y)
    










    
    def detect_movement(self, positions, active_hand):
        """
        Функция 2: Определяет направление движения руки
        
        Returns:
            str: "UP", "DOWN", "LEFT", "RIGHT" или None если движения недостаточно
        """
        if len(positions) < 2:
            return None
        
        # Берем несколько последних позиций для более точного определения направления
        if len(positions) >= 5:
            old_positions = list(positions)[:5]  # Первые 5 позиций
            new_positions = list(positions)[-5:]  # Последние 5 позиций
        else:
            old_positions = [positions[0]]
            new_positions = [positions[-1]]
        
        # Вычисляем среднее изменение по X и Y
        delta_x_sum = 0
        delta_y_sum = 0
        
        for old_pos, new_pos in zip(old_positions, new_positions):
            delta_x_sum += (new_pos[0] - old_pos[0])
            delta_y_sum += (new_pos[1] - old_pos[1])
        
        # Среднее изменение
        delta_x = delta_x_sum / len(old_positions)
        delta_y = delta_y_sum / len(old_positions)
        
        # Преобразуем в абсолютное значение (пиксели)
        delta_x_pixels = delta_x * 1000
        delta_y_pixels = delta_y * 1000
        
        # Определяем направление движения
        movement_threshold = self.MOVEMENT_THRESHOLD
        
        # Увеличиваем порог для лучшего распознавания LEFT/RIGHT
        horizontal_threshold = movement_threshold * 0.8
        vertical_threshold = movement_threshold
        
        # Проверяем горизонтальное движение
        if abs(delta_x_pixels) > abs(delta_y_pixels):
            # Горизонтальное движение
            if abs(delta_x_pixels) > horizontal_threshold:
            
                # Добавленное условие для определения направления движения в зависимости от активной руки
                if active_hand == "left_hand":
                    if delta_x_pixels > 0:
                        return "RIGHT"
                    else:
                        return "LEFT"
                else:  # right_hand
                    if delta_x_pixels < 0:
                        return "RIGHT"
                    else:
                        return "LEFT"
        else:
            # Вертикальное движение
            if abs(delta_y_pixels) > vertical_threshold:
                if delta_y_pixels > 0:
                    return "DOWN"
                else:
                    return "UP"
        
        return None
    







    
    def get_action_from_config(self, hand, fingers, direction):
        """
        Функция 3: Ищет совпадение в конфигурации жестов и возвращает действие
        
        Args:
            hand: "left_hand" или "right_hand"
            fingers: количество пальцев (1-5)
            direction: "UP", "DOWN", "LEFT", "RIGHT"
        
        Returns:
            str: Действие из конфига или None если совпадение не найдено
        """
        
        """Ищет запись по name, age, email и возвращает quantity и key"""

        if self.config is None:
            return None
    
        for item in self.config:
            if (item.get('hand') == hand and 
                item.get('fingers') == fingers and 
                item.get('direction') == direction):
                return item.get('action', [])
    
        return None
    










    
        



    def perform_action(self, action_array):
        """Выполнение системного действия"""

        if len(action_array) == 1:
           return pyautogui.hotkey(action_array[0])
        elif len(action_array) == 2:
           return pyautogui.hotkey(action_array[0],action_array[1])
        elif len(action_array) == 3:
           return pyautogui.hotkey(action_array[0],action_array[1],action_array[2])
        elif len(action_array) == 4:
           return pyautogui.hotkey(action_array[0],action_array[1],action_array[2],action_array[3])
        elif len(action_array) == 5:
           return pyautogui.hotkey(action_array[0],action_array[1],action_array[2],action_array[3],action_array[4])









    
    def process_hands(self, right_hand_landmarks, left_hand_landmarks, image=None):
        """
        Основная функция обработки жестов рук
        
        Args:
            right_hand_landmarks: Landmarks правой руки
            left_hand_landmarks: Landmarks левой руки
            image: Изображение для отрисовки (опционально)
        
        Returns:
            tuple: (направление движения, количество пальцев) или None
        """
        # 1. Определяем какая рука и сколько пальцев
        hand_info = self.detect_hand_and_fingers(right_hand_landmarks, left_hand_landmarks)
        
        if not hand_info:
            self.gesture_active = False
            return None
        
        # Выбираем активную руку для отслеживания (приоритет: правая)
        active_hand = None
        active_hand_landmarks = None
        fingers_count = 0
        
        if "right_hand" in hand_info and hand_info["right_hand"] > 0:
            active_hand = "right_hand"
            active_hand_landmarks = right_hand_landmarks
            fingers_count = hand_info["right_hand"]
        elif "left_hand" in hand_info and hand_info["left_hand"] > 0:
            active_hand = "left_hand"
            active_hand_landmarks = left_hand_landmarks
            fingers_count = hand_info["left_hand"]
        else:
            self.gesture_active = False
            return None
        
        # Отображаем информацию о руках на изображении
        if image is not None:
            y_offset = 120
            for hand_type, count in hand_info.items():
                color = (0, 255, 0) if hand_type == active_hand else (200, 200, 200)
                hand_label = "r " if hand_type == "right_hand" else "l"
                cv2.putText(image, f"{hand_label}: {count} f", 
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                y_offset += 30
        
        # 2. Получаем позицию активной руки и обновляем историю
        current_position = self.get_hand_position(active_hand_landmarks)
        if current_position:
            self.hand_positions.append(current_position)
            self.gesture_active = True
            self.current_hand = active_hand
            self.current_fingers_count = fingers_count
            
            # 3. Определяем направление движения
            if len(self.hand_positions) >= self.HISTORY_LENGTH // 2:
                direction = self.detect_movement(self.hand_positions, active_hand)
                
                if direction:
                    # 4. Ищем действие в конфигурации
                    action = self.get_action_from_config(active_hand, fingers_count, direction)
                    
                    if action and len(action) > 0:
                    # Выполняем действие
                        self.perform_action(action)
                        
                        # Отображаем информацию о выполненном жесте
                        if image is not None:
                            direction_text = {
                                "UP": "UP",
                                "DOWN": "DOWN", 
                                "LEFT": "LEFT",
                                "RIGHT": "RIGHT"
                            }.get(direction, direction)
                            
                            #gesture_text = f"gesture: {direction_text}, {fingers_count} пальцев"
                            #cv2.putText(image, gesture_text, 
                            #           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    
                    # Очищаем историю после выполнения действия
                    self.hand_positions.clear()
                    self.gesture_active = False
                    
                    return direction, fingers_count
        else:
            # Сбрасываем историю, если жест не активен
            if len(self.hand_positions) > 0:
                self.hand_positions.clear()
            self.gesture_active = False
        
        return None if not self.gesture_active else (None, fingers_count)
    




    
    def is_gesture_active(self):
        """Проверка, активен ли жест в данный момент"""
        return self.gesture_active
    
    def get_current_hand(self):
        """Получение текущей активной руки"""
        return self.current_hand
    
    def get_current_fingers_count(self):
        """Получение текущего количества пальцев"""
        return self.current_fingers_count










def create_default_gesture_controller():
    """Создание контроллера жестов с настройками по умолчанию"""
    return GestureController(
        config_file="gestures_config.json",
        movement_threshold=30,
        history_length=15,  # Увеличено для более плавного отслеживания
        action_cooldown=1
    )