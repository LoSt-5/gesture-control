import cv2

import mediapipe as mp

from gestures import GestureController

# Grabbing the Holistic Model from Mediapipe and Initializing the Model
mp_holistic = mp.solutions.holistic
holistic_model = mp_holistic.Holistic(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Initializing the drawing utils
mp_drawing = mp.solutions.drawing_utils

# (0) in VideoCapture is used to connect to your computer's default camera
capture = cv2.VideoCapture(0)

# Initializing current time and previous time for calculating the FPS
previousTime = 0
currentTime = 0

# Initialize gesture controller
gesture_controller = GestureController()

while capture.isOpened():
    # Capture frame by frame
    ret, frame = capture.read()
    if not ret:
        break
        

    
    # Converting from BGR to RGB
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Making predictions using holistic model
    image.flags.writeable = False
    results = holistic_model.process(image)
    image.flags.writeable = True
    
    # Converting back the RGB image to BGR
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    # Process gestures using the gesture controller
    gesture_info = gesture_controller.process_hands(
        results.right_hand_landmarks,
        results.left_hand_landmarks,
        image
    )
    
    # Display gesture information if available

    
    # Status text

    
    # Drawing the Facial Landmarks

    
    # Drawing Right hand Land Marks
    if results.right_hand_landmarks:
        mp_drawing.draw_landmarks(
            image, 
            results.right_hand_landmarks, 
            mp_holistic.HAND_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(255,0,0), thickness=2, circle_radius=2),
            mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2)
        )
    
    # Drawing Left hand Land Marks
    if results.left_hand_landmarks:
        mp_drawing.draw_landmarks(
            image, 
            results.left_hand_landmarks, 
            mp_holistic.HAND_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0,0,255), thickness=2, circle_radius=2),
            mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2)
        )
    

    # Display the resulting image
    image = cv2.flip(image, 1) 

    if gesture_info:
        direction, fingers_count = gesture_info
        if direction:
            cv2.putText(image, f"Gesture: {direction}", 
                       (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        cv2.putText(image, f"Fingers: {fingers_count}", 
                   (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    status_text = "Gesture: ACTIVE" if gesture_controller.is_gesture_active() else "Gesture: INACTIVE"
    status_color = (0, 255, 0) if gesture_controller.is_gesture_active() else (0, 0, 255)
    cv2.putText(image, status_text, (10, 280), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)


    cv2.imshow("Gesture Control ", image)
    
    # Enter key 'q' to break the loop
    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

# When all the process is done
# Release the capture and destroy all windows
capture.release()
cv2.destroyAllWindows()