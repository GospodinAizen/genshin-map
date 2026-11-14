import cv2
import numpy as np
import mss


class ScreenTracker:
    def __init__(self, reference_path, monitor_index=1):
        self.reference = cv2.imread(reference_path)
        if self.reference is None:
            raise FileNotFoundError(f"Не найдена карта-образец: {reference_path}")
        self.reference_gray = cv2.cvtColor(self.reference, cv2.COLOR_BGR2GRAY)
        self.orb = cv2.ORB_create(nfeatures=6000)
        self.reference_points, self.reference_descriptors = (
            self.orb.detectAndCompute(self.reference_gray, None)
        )
        if self.reference_descriptors is None or len(self.reference_points) < 12:
            raise ValueError("На карте-образце недостаточно деталей для распознавания")
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self.sct = mss.mss()
        if monitor_index < 1 or monitor_index >= len(self.sct.monitors):
            self.sct.close()
            raise ValueError(f"Монитор №{monitor_index} не найден")
        self.monitor = self.sct.monitors[monitor_index]

    def capture_screen(self):
        image = np.asarray(self.sct.grab(self.monitor))
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    def detect(self):
        screen = self.capture_screen()
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        points, descriptors = self.orb.detectAndCompute(gray, None)
        if descriptors is None or len(points) < 12:
            return None

        pairs = self.matcher.knnMatch(self.reference_descriptors, descriptors, k=2)
        good = [
            first for pair in pairs if len(pair) == 2
            for first, second in [pair]
            if first.distance < 0.72 * second.distance
        ]
        if len(good) < 12:
            return None

        source = np.float32([
            self.reference_points[m.queryIdx].pt for m in good
        ]).reshape(-1, 1, 2)
        destination = np.float32([
            points[m.trainIdx].pt for m in good
        ]).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(
            source, destination, cv2.RANSAC, 5.0
        )
        if homography is None or mask is None or not np.isfinite(homography).all():
            return None
        inliers = int(mask.sum())
        if inliers < 10:
            return None
        return {
            "homography": homography,
            "confidence": inliers,
            "tile_id": "default",
            "screen_size": (screen.shape[1], screen.shape[0]),
        }

    def close(self):
        self.sct.close()
