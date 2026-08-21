import os
import json
import random
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import uvicorn

# --- Firebase Admin SDK 匯入 ---
import firebase_admin
from firebase_admin import credentials, messaging

# ===================== 環境變量與路徑配置 =====================
PORT = int(os.getenv("PORT", 8000))

# 取得目前檔案 (main.py) 所在目錄 (01_BE)
BASE_DIR = Path(__file__).parent.resolve()
# 取得專案根目錄 (JackalAIoT01)
PROJECT_ROOT = BASE_DIR.parent
# 前端目錄路徑 (00_FE)
FRONTEND_DIR = PROJECT_ROOT / "00_FE"

# 資料文件路徑
ALERT_FILE = BASE_DIR / "alerts.json"
CONFIG_FILE = BASE_DIR / "config.json"
EMPLOYEES_FILE = BASE_DIR / "employees.json"
UPLOAD_DIR = BASE_DIR / "Upload"
IMAGE_PATH = BASE_DIR / "Icon_Jackal.png"

# 圖片加水印文件路徑
MASK_DIR = BASE_DIR / "Mask"
MASK_DIR.mkdir(parents=True, exist_ok=True)
WATERMARK_PATH = FRONTEND_DIR / "mask_jk.png"

# 課堂簽到路徑
CHECKIN_FILE = BASE_DIR / "checkin_rec.json"

# ===================== Firebase Admin 初始化 (支援 Render 環境變數) =====================
SERVICE_ACCOUNT_ENV = os.getenv("FIREBASE_SERVICE_ACCOUNT")
SERVICE_ACCOUNT_FILE = BASE_DIR / "serviceAccountKey.json"

try:
    if SERVICE_ACCOUNT_ENV:
        # Render 雲端部署：由 Environment Variables 載入 JSON
        cred_dict = json.loads(SERVICE_ACCOUNT_ENV)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        print("[FCM] Firebase Admin 成功透過環境變數初始化！")
    elif SERVICE_ACCOUNT_FILE.exists():
        # 本機開發：由本地 serviceAccountKey.json 載入
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_FILE))
        firebase_admin.initialize_app(cred)
        print("[FCM] Firebase Admin 成功透過本地檔初始化！")
    else:
        print("[FCM] 警示：未找到 Firebase 服務帳戶認證（環境變數與本地檔均不存在）")
except Exception as e:
    print(f"[FCM] 初始化失敗: {e}")

app = FastAPI(title="Jackal AIoT Integrated Platform")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 模型定義 ---
class CheckinRequest(BaseModel):
    employee_id: str

class FcmPushRequest(BaseModel):
    fcm_token: str
    title: str = "Jackal AIoT 系統通知"
    body: str = "這是一則來自 Python 後端的 FCM 測試推播！"

# ===================== 1. 核心 API (隨機數與資料) =====================
def add_alert(message: str):
    try:
        alerts = []
        if ALERT_FILE.exists():
            with open(ALERT_FILE, "r", encoding="utf-8") as f:
                alerts = json.load(f)
        
        new_entry = {
            "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            "msg": message
        }
        alerts.append(new_entry)
        
        with open(ALERT_FILE, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Alert writing error: {e}")

@app.get("/")
async def get_random_number():
    num = random.randint(10000000, 99999999)
    add_alert("系統請求隨機數")
    return num

@app.get("/alerts")
async def get_alerts():
    if not ALERT_FILE.exists():
        return {"alerts": []}
    with open(ALERT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"alerts": data}

@app.post("/list")
async def submit_note(data: dict = Body(...)):
    note = data.get("note")
    if not note:
        raise HTTPException(status_code=400, detail="內容不能為空")
    
    add_alert(note)
    return {"status": "success", "message": "數據已寫入警報列表"}

@app.get("/config")
async def get_config():
    if not CONFIG_FILE.exists(): return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/employees")
async def get_employees():
    if not EMPLOYEES_FILE.exists(): return []
    with open(EMPLOYEES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ===================== FCM 推播測試 API =====================
@app.post("/send-fcm")
async def send_fcm_notification(req: FcmPushRequest):
    """專門給 Python 測試呼叫發送推播的 API"""
    if not firebase_admin._apps:
        raise HTTPException(status_code=500, detail="Firebase Admin 未初始化，請檢查設定")
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=req.title,
                body=req.body,
            ),
            token=req.fcm_token,
        )
        response = messaging.send(message)
        
        add_alert(f"[FCM 推播] {req.title}: {req.body}")
        return {"status": "success", "message_id": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FCM 發送失敗: {str(e)}")

# ===================== 2. 檔案與浮水印處理 API =====================
@app.post("/upload-mask")
async def upload_mask_file(file: UploadFile = File(...)):
    temp_path = MASK_DIR / "temp.png"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        if WATERMARK_PATH.exists():
            base_img = Image.open(temp_path).convert("RGBA")
            watermark = Image.open(WATERMARK_PATH).convert("RGBA")
            
            bg_w, bg_h = base_img.size
            wm_w, wm_h = watermark.size
            
            ratio = max(bg_w / wm_w, bg_h / wm_h)
            new_wm_w = int(wm_w * ratio)
            new_wm_h = int(wm_h * ratio)
            
            watermark = watermark.resize((new_wm_w, new_wm_h), Image.Resampling.LANCZOS)
            
            offset_x = (bg_w - new_wm_w) // 2
            offset_y = (bg_h - new_wm_h) // 2
            
            combined = Image.new('RGBA', base_img.size, (0,0,0,0))
            combined.paste(base_img, (0,0))
            combined.paste(watermark, (offset_x, offset_y), mask=watermark)
            
            combined.convert("RGB").save(temp_path, "PNG")
            return {"status": "success", "message": "全幅浮水印合成完畢"}
        
        return {"status": "success", "message": "上傳成功 (未找到浮水印檔)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-mask-image")
async def get_mask_image():
    temp_path = MASK_DIR / "temp.png"
    if not temp_path.exists():
        raise HTTPException(status_code=404, detail="圖片不存在")
    return FileResponse(path=temp_path, media_type="image/png", headers={"Cache-Control": "no-cache"})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = ".png" if file.content_type.startswith("image/") else f"_{file.filename}"
    save_name = f"Icon_Jackal00{ext}" if "image" in file.content_type else file.filename
    file_path = UPLOAD_DIR / save_name
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "filename": save_name}

@app.get("/get-image")
async def get_image():
    if not IMAGE_PATH.exists():
        raise HTTPException(status_code=404, detail="圖片不存在")
    return FileResponse(path=IMAGE_PATH, media_type="image/png")

# ===================== 3. 靜態檔案掛載 (放在最後) =====================
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)