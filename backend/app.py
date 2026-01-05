from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import cv2
import shutil
import uuid
import os

app = FastAPI(title="Piero AI Video Upscaler")

# CORS (frontend público)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upscale")
async def upscale_video(file: UploadFile = File(...)):
    input_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4()}.mp4")
    output_path = os.path.join(UPLOAD_DIR, f"out_{uuid.uuid4()}.mp4")

    # Guardar vídeo
    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        return {"error": "Error saving video"}

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return {"error": "Cannot open video"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    # Mantener aspecto (4K)
    target_w, target_h = 3840, 2160
    aspect_ratio = w / h

    if aspect_ratio > 1:
        new_w = target_w
        new_h = int(target_w / aspect_ratio)
    else:
        new_h = target_h
        new_w = int(target_h * aspect_ratio)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (new_w, new_h))

    if not out.isOpened():
        cap.release()
        return {"error": "Cannot write output video"}

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        out.write(frame_resized)

    cap.release()
    out.release()

    # 🔥 borrar temporal
    if os.path.exists(input_path):
        os.remove(input_path)

    return {
        "video_url": f"/download/{os.path.basename(output_path)}",
        "total_frames": total_frames
    }

@app.get("/download/{filename}")
def download_video(filename: str):
    if ".." in filename or "/" in filename:
        return {"error": "Invalid filename"}

    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return {"error": "File not found"}

    return FileResponse(file_path, media_type="video/mp4")

@app.delete("/delete/{filename}")
def delete_video(filename: str):
    if ".." in filename or "/" in filename:
        return {"error": "Invalid filename"}

    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"message": "Deleted"}
    return {"error": "File not found"}
