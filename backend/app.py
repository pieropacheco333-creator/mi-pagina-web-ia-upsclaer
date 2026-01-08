import cv2
import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()

# Configuración de rutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOAD_DIR = os.path.join(BASE_DIR, "backend", "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/descargas", StaticFiles(directory=UPLOAD_DIR), name="outputs")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open(os.path.join(FRONTEND_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upscale")
async def upscale_video(file: UploadFile = File(...)):
    out_name = f"final_{uuid.uuid4()}.mp4"
    in_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4()}.mp4")
    out_path = os.path.join(UPLOAD_DIR, out_name)

    with open(in_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    cap = cv2.VideoCapture(in_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    
    # Redimensionar a 4K (3840x2160)
    target_w, target_h = 3840, 2160
    
    # PROBAMOS CON EL CODEC MÁS COMPATIBLE PARA LINUX/RENDER
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    out = cv2.VideoWriter(out_path, fourcc, fps, (target_w, target_h))

    if not out.isOpened():
        return {"error": "Error interno: El servidor no tiene codecs de video instalados."}

    frames_count = 0
    while frames_count < 60: # Solo 2-3 segundos para probar que funcione
        ret, frame = cap.read()
        if not ret: break
        resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        out.write(resized)
        frames_count += 1

    cap.release()
    out.release()
    
    if os.path.exists(in_path): os.remove(in_path)

    # Si el archivo mide 0 bytes, es que el encoder falló
    if os.path.getsize(out_path) == 0:
        return {"error": "El video se generó vacío. Revisa opencv-contrib-python-headless."}

    return {"video_url": f"/descargas/{out_name}"}