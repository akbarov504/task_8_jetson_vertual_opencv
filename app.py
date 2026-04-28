import cv2
import time
import threading

OUT_DEVICE = "/dev/video40"
IN_DEVICE  = "/dev/video41"

class CameraStream:
    def __init__(self, device, name):
        self.device = device
        self.name   = name
        self.cap    = None
        self.frame  = None
        self.lock   = threading.Lock()
        self.running = False
        self.thread  = None

        self.last_frame_time = None
        self.fps             = 0.0
        self.opened_once     = False

    def open(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass

        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)

        if not self.cap.isOpened():
            print(f"[ERROR] {self.name} ochilmadi: {self.device}")
            return False

        # YUYV format va FFmpeg bilan bir xil razmer
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.opened_once = True
        print(f"[INFO] {self.name} ochildi: {self.device}")
        return True

    def start(self):
        self.running = True
        self.thread  = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        while self.running:
            # Agar uzilib qolsa qayta ulanish
            if self.cap is None or not self.cap.isOpened():
                ok = self.open()
                if not ok:
                    time.sleep(0.5)
                    continue

            ret, frame = self.cap.read()

            if not ret:
                time.sleep(0.1)  # Kadr bo'lmasa, CPU ni qizitmaslik uchun kutamiz
                continue

            # FPS hisoblash
            now = time.time()
            if self.last_frame_time is not None:
                dt = now - self.last_frame_time
                if dt > 0:
                    instant_fps = 1.0 / dt
                    self.fps = (self.fps * 0.85) + (instant_fps * 0.15)
            self.last_frame_time = now

            # Eng yangi frame ni saqlash
            with self.lock:
                self.frame = frame

            # ==========================================================
            # SEHRLI QATOR: Protsessorni FFmpeg uchun bo'shatib beramiz!
            # ==========================================================
            time.sleep(0.01)

    def read_latest(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1)
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass

# ── Streamlarni boshlash ──────────────────────────────────────────────────────
out_cam = CameraStream(OUT_DEVICE, "OUT")
in_cam  = CameraStream(IN_DEVICE,  "IN")

out_cam.start()
in_cam.start()

print("[INFO] OUT va IN realtime mode ishlayapti. Kechikish nolga tushirildi!")
print("[INFO] Chiqish uchun 'q' bosing.")

try:
    while True:
        frame_out = out_cam.read_latest()
        frame_in  = in_cam.read_latest()

        if frame_out is not None:
            cv2.putText(
                frame_out,
                f"OUT  {out_cam.fps:.1f} fps",
                (10, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("OUT Realtime", frame_out)

        if frame_in is not None:
            cv2.putText(
                frame_in,
                f"IN   {in_cam.fps:.1f} fps",
                (10, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("IN Realtime", frame_in)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    out_cam.stop()
    in_cam.stop()
    cv2.destroyAllWindows()