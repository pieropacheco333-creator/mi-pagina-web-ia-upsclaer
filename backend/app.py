from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import cv2
import shutil
import uuid
import os

app = FastAPI()

# Configuración de CORS para evitar bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carpeta de archivos - Usamos ruta absoluta para Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Montar la carpeta de subidas para que el navegador pueda VER los videos
app.mount("/outputs", StaticFiles(directory=UPLOAD_DIR), name="outputs")

@app.post("/upscale")
async def upscale_video(file: UploadFile = File(...)):
    # Validar formato
    if not file.filename.lower().endswith((".mp4", ".mov", ".avi")):
        raise HTTPException(status_code=400, detail="Formato no soportado")

    # Generar nombres únicos
    input_filename = f"in_{uuid.uuid4()}_{file.filename}"
    output_filename = f"out_{uuid.uuid4()}.mp4"
    
    input_path = os.path.join(UPLOAD_DIR, input_filename)
    output_path = os.path.join(UPLOAD_DIR, output_filename)

    # Guardar archivo original
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Procesamiento con OpenCV
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return {"error": "No se pudo abrir el video"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Definir tamaño 4K (o proporcional)
    target_w, target_h = 3840, 2160
    
    # Codec h264 para que el navegador lo reproduzca (CRÍTICO)
    fourcc = cv2.VideoWriter_fourcc(*'avc1') 
    out = cv2.VideoWriter(output_path, fourcc, fps, (target_w, target_h))

    frames_processed = 0
    # Limitamos a los primeros 150 frames para evitar que Render mate el proceso por falta de RAM
    while frames_processed < 300: 
        ret, frame = cap.read()
        if not ret:
            break
        
        # Redimensionado
        resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        out.write(resized)
        frames_processed += 1

    cap.release()
    out.release()

    # Limpiar el original para ahorrar espacio en Render
    if os.path.exists(input_path):
        os.remove(input_path)

    # Devolvemos la URL relativa
    return {"video_url": f"/outputs/{output_filename}"}

# Servir el frontend al final
if os.path.exists("index.html"):
    @app.get("/")
    async def read_index():
        return FileResponse("index.html")