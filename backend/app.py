from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import cv2, shutil, uuid, os, time, threading

app = FastAPI(title="Piero AI Video Upscaler")

# CORS - puedes restringir en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

# Carpeta para videos temporales
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_SIZE = 50 * 1024 * 1024  # 50MB máximo
FILE_LIFETIME = 3600  # 1 hora en segundos

# Función para borrar archivos viejos
def cleanup_uploads():
    while True:
        now = time.time()
        for filename in os.listdir(UPLOAD_DIR):
            path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(path):
                if now - os.path.getmtime(path) > FILE_LIFETIME:
                    try:
                        os.remove(path)
                    except:
                        pass
        time.sleep(600)  # revisar cada 10 minutos

# Iniciar limpieza en hilo aparte
threading.Thread(target=cleanup_uploads, daemon=True).start()

@app.post("/upscale")
async def upscale_video(file: UploadFile = File(...)):
    if file.spool_max_size > MAX_SIZE:
        return {"error":"File too large"}

    input_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4()}.mp4")
    output_path = os.path.join(UPLOAD_DIR, f"out_{uuid.uuid4()}.mp4")

    # Guardar archivo
    with open(input_path,"wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened(): 
        return {"error":"Cannot open video"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Escalar a 4K manteniendo aspecto
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
        return {"error":"Cannot write video"}

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        frame_resized = cv2.resize(frame,(new_w,new_h), interpolation=cv2.INTER_CUBIC)
        out.write(frame_resized)

    cap.release()
    out.release()

    return {"video_url": f"/download/{os.path.basename(output_path)}"}

@app.get("/download/{filename}")
def download_video(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path): 
        return {"error":"File not found"}
    return FileResponse(file_path, media_type="video/mp4")
