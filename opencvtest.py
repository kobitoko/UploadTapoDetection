#python3 -m pip install opencv-python
import cv2  # Import OpenCV lib

#https://docs.opencv.org/4.5.5/dd/d43/tutorial_py_video_display.html
# https://github.com/cisco/openh264/releases?q=1.8 for openh264-1.8.0-win64.dll
cap = cv2.VideoCapture('') # Open video source as object
fourcc = cv2.VideoWriter_fourcc(*'X264')
fps = 25
streamWidth = 2304
streamHeight = 1296
out = cv2.VideoWriter('output.mkv', fourcc, fps, (streamWidth, streamHeight))
while True: 
    ret, frame = cap.read()  # Read frame as object - numpy.ndarray, ret is a confirmation of a successfull retrieval of the frame
    out.write(frame)
    actualWidth  = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) #float width
    actualHeight = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) #float height
    if actualWidth != streamWidth and actualHeight != streamHeight:
        #log here that it isn't the same!
        break
    cv2.imshow("frame", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
out.release()
cv2.destroyAllWindows()
