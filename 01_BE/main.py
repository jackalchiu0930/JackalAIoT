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

# ===================== 環境變量與路徑配置 =====================
PORT = int(os.getenv("PORT", 8000))

# 取得目前檔案 (main.py) 所在目錄 (00_BE)
BASE_DIR = Path(__file__).parent.resolve()
# 取得專案根目錄 (JackalAIoT)
PROJECT_ROOT = BASE_DIR.parent
# 前端目錄路徑 (00_FE)
FRONTEND_DIR = PROJECT_ROOT / "00_FE"

# 資料文件路徑
ALERT_FILE = BASE_DIR / "alerts.json"
CONFIG_FILE = BASE_DIR / "config.json"
EMPLOYEES_FILE = BASE_DIR / "employees.json"
UPLOAD_DIR = BASE_DIR / "Upload"
IMAGE_PATH = BASE_DIR / "Icon_Jackal.png"

# 圖片加水印文件路徑 (用於 class.html 驗證)
MASK_DIR = BASE_DIR / "Mask"
MASK_DIR.mkdir(parents=True, exist_ok=True)
WATERMARK_PATH = FRONTEND_DIR / "mask_jk.png"

#課堂簽到路徑
CHECKIN_FILE = BASE_DIR / "checkin_rec.json"

app = FastAPI(title="Jackal AIoT Integrated Platform")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 新增簽到相關模型 ---
class CheckinRequest(BaseModel):
    employee_id: str

# ===================== 1. 核心 API (隨機數與資料) =====================
# 協助寫入警報的通用函數
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

# 您提到的：請求隨機數的 API (根路由)
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
    
    # 核心修正：將提交的數據寫入 alerts.json
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

# ===================== 2. 檔案與浮水印處理 API =====================

# 專門給 class.html 使用的全幅浮水印上傳
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
            
            # Cover 邏輯：確保浮水印佈滿全圖，超出部分裁切
            ratio = max(bg_w / wm_w, bg_h / wm_h)
            new_wm_w = int(wm_w * ratio)
            new_wm_h = int(wm_h * ratio)
            
            watermark = watermark.resize((new_wm_w, new_wm_h), Image.Resampling.LANCZOS)
            
            # 居中計算
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

# 原有的通用上傳 API
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

# 課堂簽到API

@app.get("/check-employee/{employee_id}")
async def check_employee(employee_id: str):
    """檢查工號是否存在於 employees.json"""
    if not EMPLOYEES_FILE.exists():
        raise HTTPException(status_code=500, detail="員工資料庫不存在")
    
    with open(EMPLOYEES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if employee_id in data.get("employees", []):
        return {"status": "success", "course": data.get("course_name", "AIoT 課程")}
    else:
        return {"status": "error", "message": "非註冊學員，請前往申請後再重試"}

@app.post("/submit-checkin")
async def submit_checkin(req: CheckinRequest):
    """提交簽到記錄並存入 checkin_rec.json"""
    if not EMPLOYEES_FILE.exists():
        raise HTTPException(status_code=500, detail="員工資料庫不存在")
        
    with open(EMPLOYEES_FILE, "r", encoding="utf-8") as f:
        emp_data = json.load(f)
    
    if req.employee_id not in emp_data.get("employees", []):
        raise HTTPException(status_code=400, detail="非註冊學員")

    # 讀取或初始化簽到記錄
    records_data = {"course_name": emp_data.get("course_name", ""), "checkin_records": []}
    if CHECKIN_FILE.exists():
        with open(CHECKIN_FILE, "r", encoding="utf-8") as f:
            records_data = json.load(f)

    # 建立新紀錄
    new_record = {
        "employee_id": req.employee_id,
        "timestamp": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "course": emp_data.get("course_name", "")
    }
    records_data["checkin_records"].append(new_record)

    with open(CHECKIN_FILE, "w", encoding="utf-8") as f:
        json.dump(records_data, f, indent=2, ensure_ascii=False)

    return {"status": "success", "message": "簽到成功", "record": new_record}

@app.get("/get-checkin-records/{employee_id}")
async def get_checkin_records(employee_id: str):
    """取得特定員工的簽到紀錄"""
    if not CHECKIN_FILE.exists():
        return {"course_name": "", "checkin_records": []}
        
    with open(CHECKIN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 過濾出該員工的紀錄
    user_records = [r for r in data.get("checkin_records", []) if r["employee_id"] == employee_id]
    return {"course_name": data.get("course_name", ""), "checkin_records": user_records}


# ===================== 3. 靜態檔案掛載 (放在最後) =====================

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)