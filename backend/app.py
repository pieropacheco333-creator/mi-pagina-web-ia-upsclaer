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

# --- RUTAS ---
# Localizamos la raíz del proyecto (un nivel arriba de /backend)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
# Guardamos los videos dentro de una carpeta accesible
UPLOAD_DIR = os.path.join(BASE_DIR, "backend", "outputs")

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# SERVIR ARCHIVOS (El orden es vital)
# 1. Los videos procesados se verán en url.com/descargas/nombre.mp4
app.mount("/descargas", StaticFiles(directory=UPLOAD_DIR), name="outputs")
# 2. El resto del frontend (fotos, logos)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upscale")
async def upscale_video(file: UploadFile = File(...)):
    # Nombre del archivo final
    out_name = f"final_{uuid.uuid4()}.mp4"
    in_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4()}.mp4")
    out_path = os.path.join(UPLOAD_DIR, out_name)

    with open(in_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    cap = cv2.VideoCapture(in_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    
    # FORZAR 4K
    target_w, target_h = 3840, 2160
    
    # EL CODEC 'avc1' es lo que hace que la preview SE VEA en el navegador
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(out_path, fourcc, fps, (target_w, target_h))

    frames_count = 0
    while frames_count < 120: # Limite de frames para que Render no se sature
        ret, frame = cap.read()
        if not ret: break
        
        # Escalado de alta calidad
        resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        out.write(resized)
        frames_count += 1

    cap.release()
    out.release()
    
    if os.path.exists(in_path): os.remove(in_path)

    # Devolvemos la ruta que configuramos en el mount
    return {"video_url": f"/descargas/{out_name}"}