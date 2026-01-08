from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import cv2
import shutil
import uuid
import os
import time
import threading

app = FastAPI(title="Piero AI Video Upscaler")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

# Carpetas
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_SIZE = 100 * 1024 * 1024  # 100MB
FILE_LIFETIME = 3600  # 1 hora

# Limpieza automática
def cleanup_uploads():
    while True:
        now = time.time()
        for f in os.listdir(UPLOAD_DIR):
            path = os.path.join(UPLOAD_DIR, f)
            if os.path.isfile(path) and now - os.path.getmtime(path) > FILE_LIFETIME:
                try:
                    os.remove(path)
                except:
                    pass
        time.sleep(600)

threading.Thread(target=cleanup_uploads, daemon=True).start()


# =========================
# ESCALAR VIDEO MP4
# =========================
@app.post("/upscale")
async def upscale_video(file: UploadFile = File(...)):

    if not file.filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only MP4 videos are supported")

    input_path = os.path.join(UPLOAD_DIR, f"in_{uuid.uuid4()}.mp4")
    output_path = os.path.join(UPLOAD_DIR, f"out_{uuid.uuid4()}.mp4")

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    cap = cv2.VideoCapture(input_path)

    if not cap.isOpened():
        return {"error": "Cannot open video. Use standard MP4 (H.264)."}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    target_w, target_h = 3840, 2160
    aspect = w / h

    if aspect > 1:
        new_w = target_w
        new_h = int(target_w / aspect)
    else:
        new_h = target_h
        new_w = int(target_h * aspect)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (new_w, new_h))

    if not out.isOpened():
        cap.release()
        return {"error": "Cannot write output video"}

    frames = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        out.write(resized)
        frames += 1

    cap.release()
    out.release()

    if frames == 0:
        return {"error": "Unsupported codec. Use normal MP4 (H.264)."}

    return {"video_url": f"/download/{os.path.basename(output_path)}"}


# =========================
# DESCARGAR VIDEO
# =========================
@app.get("/download/{filename}")
def download_video(filename: str):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path, media_type="video/mp4")
