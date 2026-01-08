from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import cv2
import shutil
import uuid
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CONFIGURACIÓN DE RUTAS DINÁMICAS
# Obtenemos la ruta de la carpeta 'pagina web ia' (la raíz)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOAD_DIR = os.path.join(BASE_DIR, "backend", "uploads")

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# 1. Servir archivos del frontend (logo.png, etc)
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
# 2. Servir videos procesados
app.mount("/outputs", StaticFiles(directory=UPLOAD_DIR), name="outputs")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        return f"<h1>Error 404: No se encuentra index.html en {index_path}</h1>"
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upscale")
async def upscale_video(file: UploadFile = File(...)):
    out_name = f"out_{uuid.uuid4()}.mp4"
    in_path = os.path.join(UPLOAD_DIR, f"in_{uuid.uuid4()}.mp4")
    out_path = os.path.join(UPLOAD_DIR, out_name)

    with open(in_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    cap = cv2.VideoCapture(in_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    
    # Render Free es débil: limitamos a 1080p para asegurar que funcione. 
    # Si quieres 4K real cambia a (3840, 2160) pero puede fallar por RAM.
    target_w, target_h = 1920, 1080 
    
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(out_path, fourcc, fps, (target_w, target_h))

    count = 0
    while count < 100: # Procesamos solo unos segundos para que Render no se cuelgue
        ret, frame = cap.read()
        if not ret: break
        resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        out.write(resized)
        count += 1

    cap.release()
    out.release()
    
    if os.path.exists(in_path): os.remove(in_path)
    return {"video_url": f"/outputs/{out_name}"}