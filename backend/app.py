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

# --- RUTAS ABSOLUTAS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
# Guardamos en una carpeta llamada 'outputs' dentro de backend
UPLOAD_DIR = os.path.join(BASE_DIR, "backend", "outputs")

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# SERVIR ARCHIVOS
app.mount("/descargas", StaticFiles(directory=UPLOAD_DIR), name="outputs")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
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
    
    # Redimensionamos a 4K
    target_w, target_h = 3840, 2160
    
    # CAMBIO IMPORTANTE: Usamos 'mp4v' que es más compatible con el entorno Linux de Render
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, (target_w, target_h))

    if not out.isOpened():
        cap.release()
        return {"error": "No se pudo inicializar el codificador de video en el servidor"}

    frames_count = 0
    # Procesamos solo 90 frames (3 segundos aprox) para que Render no mate el proceso
    while frames_count < 90:
        ret, frame = cap.read()
        if not ret: break
        resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        out.write(resized)
        frames_count += 1

    cap.release()
    out.release()
    
    if os.path.exists(in_path): os.remove(in_path)

    # Verificamos si el archivo se creó realmente
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        return {"error": "El video no se pudo generar correctamente"}

    return {"video_url": f"/descargas/{out_name}"}