"""Helpers for reading QR codes from ROS image messages.

No ROS imports: image_to_bgr only needs an object with the sensor_msgs/Image
fields (data, height, width, step, encoding).
"""
import cv2
import numpy as np


def image_to_bgr(msg):
    """Convert a sensor_msgs/Image (rgb8, bgr8 or mono8) to a numpy array.

    Returns None for unsupported encodings.
    """
    data = np.frombuffer(msg.data, dtype=np.uint8)

    if msg.encoding in ("rgb8", "bgr8"):
        img = data.reshape(msg.height, msg.step)[:, : msg.width * 3]
        img = img.reshape(msg.height, msg.width, 3)
        if msg.encoding == "rgb8":
            img = img[:, :, ::-1]
        return np.ascontiguousarray(img)

    if msg.encoding == "mono8":
        img = data.reshape(msg.height, msg.step)[:, : msg.width]
        return np.ascontiguousarray(img)

    return None


def decode_qr(frame, detector=None):
    """Return the decoded QR text in the frame, or None if there is none."""
    if detector is None:
        detector = cv2.QRCodeDetector()
    text, _, _ = detector.detectAndDecode(frame)
    text = text.strip() if text else ""
    return text or None
