import os
import cv2
import sys
import numpy as np
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))
OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

MODEL_FOTO = os.path.join(BASE_DIR, 'models', 'EDSR_x4.pb')
MODEL_VIDEO = os.path.join(BASE_DIR, 'models', 'FSRCNN_x4.pb')

app = Flask(__name__, template_folder=FRONTEND_DIR, static_folder=FRONTEND_DIR)

for folder in [OUTPUTS_DIR, UPLOADS_DIR]:
    os.makedirs(folder, exist_ok=True)

sr_foto = cv2.dnn_superres.DnnSuperResImpl_create()
sr_video = cv2.dnn_superres.DnnSuperResImpl_create()

def cargar_modelos():
    if os.path.exists(MODEL_FOTO):
        sr_foto.readModel(MODEL_FOTO)
        sr_foto.setModel("edsr", 4)
    if os.path.exists(MODEL_VIDEO):
        sr_video.readModel(MODEL_VIDEO)
        sr_video.setModel("fsrcnn", 4)

cargar_modelos()

def mejorar_calidad_profunda(img):
    """
    Esta función engaña al ojo inyectando nitidez artificial 
    donde la IA escaló los píxeles.
    """
    # 1. Corrección de Contraste Adaptativo (hace que los detalles resalten)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    img_contrast = cv2.merge((cl,a,b))
    img_contrast = cv2.cvtColor(img_contrast, cv2.COLOR_LAB2BGR)

    # 2. Unsharp Masking (Genera esa 'fuerza' en los bordes para que parezca 4K real)
    gaussian_3 = cv2.GaussianBlur(img_contrast, (0, 0), 2.0)
    final = cv2.addWeighted(img_contrast, 1.5, gaussian_3, -0.5, 0)
    
    return final

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upscale', methods=['POST'])
def upscale():
    try:
        file = request.files['file']
        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOADS_DIR, filename)
        file.save(input_path)

        output_filename = f"PREMIER_4K_{filename}"
        output_path = os.path.join(OUTPUTS_DIR, output_filename)

        if filename.lower().endswith(('png', 'jpg', 'jpeg')):
            print(f"🚀 PROCESANDO IMAGEN CON DETALLE EXTRA...", flush=True)
            img = cv2.imread(input_path)
            # Escalado IA
            upscaled = sr_foto.upsample(img)
            # Inyección de nitidez
            result = mejorar_calidad_profunda(upscaled)
            cv2.imwrite(output_path, result, [cv2.IMWRITE_JPEG_QUALITY, 100])
            file_type = "image"
        
        else:
            print(f"🎬 MEJORANDO VIDEO FRAME A FRAME...", flush=True)
            cap = cv2.VideoCapture(input_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * 4)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * 4)
            
            out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

            count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret: break
                
                # Paso 1: IA genera los píxeles
                ia_frame = sr_video.upsample(frame)
                # Paso 2: Post-procesado genera la NITIDEZ
                sharp_frame = mejorar_calidad_profunda(ia_frame)
                
                out.write(sharp_frame)
                count += 1
                if count % 5 == 0:
                    print(f"⏳ Calidad: {(count/total_frames)*100:.1f}%", end='\r', flush=True)
            
            cap.release()
            out.release()
            file_type = "video"

        return jsonify({"status": "success", "file_url": f"/outputs/{output_filename}", "type": file_type})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/outputs/<path:filename>')
def serve_output(filename):
    return send_from_directory(OUTPUTS_DIR, filename)

if __name__ == '__main__':
    # Render asigna un puerto dinámico, esto lo captura:
    port = int(os.environ.get("PORT", 5000))
    # Host 0.0.0.0 es obligatorio para que sea visible en internet
    app.run(host='0.0.0.0', port=port)