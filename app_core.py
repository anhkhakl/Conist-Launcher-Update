import flet as ft
import os
import sys
import json
import requests
from bs4 import BeautifulSoup
import re
import threading
import time
import webbrowser
import winreg as reg
import winsound
import random
from PIL import Image
import shutil
import asyncio
import ctypes
import time
import concurrent.futures 













def get_base_path():
    """Hàm lấy đường dẫn gốc (Dual Mode)"""
    # 1. Nếu là file EXE đã đóng gói (Frozen)
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    
    # 2. Nếu là chạy Code (VS Code/Terminal)
    else:
        # [QUAN TRỌNG] Lấy đường dẫn của chính file code này
        return os.path.dirname(os.path.abspath(__file__))


# [UPGRADE] Định nghĩa lại cấu trúc API chuẩn xác hơn
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_relative_cursor_pos(window_title):
    """Tính tọa độ chuột dựa trên Client Area (Bỏ qua viền/bóng cửa sổ)"""
    try:
        # 1. Tìm cửa sổ
        hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
        if not hwnd: return 0, 0

        # 2. Lấy vị trí chuột trên toàn màn hình
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

        # 3. [QUAN TRỌNG] Chuyển đổi từ tọa độ Màn hình sang tọa độ Nội dung (Client)
        # Hàm này tự động trừ đi thanh tiêu đề, viền, bóng đổ...
        ctypes.windll.user32.ScreenToClient(hwnd, ctypes.byref(pt))
        
        return pt.x, pt.y
    except:
        return 0, 0





# ==========================================
# 1. KHAI BÁO HÀM HỆ THỐNG (ĐẶT TRÊN CÙNG)
# ==========================================
def cleanup_old_versions():
    """
    [Chiến thuật: NGƯỜI KẾ THỪA] - Giai đoạn 2: Dọn dẹp
    Hàm này chạy khi App MỚI khởi động. Nó sẽ tìm và xóa xác của App cũ (.trash).
    """
    if not getattr(sys, 'frozen', False): return

    try:
        current_exe = sys.executable
        current_dir = os.path.dirname(current_exe)
        
        # Quét thư mục tìm file .trash
        for filename in os.listdir(current_dir):
            if filename.endswith(".trash"):
                full_path = os.path.join(current_dir, filename)
                try:
                    # Chờ 1 chút để App cũ kịp tắt hẳn
                    time.sleep(1) 
                    os.remove(full_path)
                    print(f"[CLEANUP] Đã dọn xác cũ: {filename}")
                except Exception as e:
                    print(f"[CLEANUP] Chưa thể xóa {filename} (có thể nó chưa tắt kịp): {e}")
                    
    except Exception as e:
        print(f"[CLEANUP] Lỗi dọn dẹp: {e}")



def handle_self_update(new_exe_path):
    """
    [Chiến thuật: NGƯỜI KẾ THỪA] - Giai đoạn 1: Chuyển giao
    1. App Cũ tự đổi tên mình thành .trash (Windows cho phép đổi tên file đang chạy!).
    2. Đưa App Mới vào vị trí chính thức.
    3. App Cũ bật App Mới lên.
    4. App Cũ tự sát.
    """
    import subprocess
    import sys
    import os
    import shutil
    
    print(f"[UPDATE] Bắt đầu chuyển giao quyền lực: {new_exe_path}")
    
    if getattr(sys, 'frozen', False):
        current_exe = sys.executable # Đường dẫn file đang chạy (V1)
    else:
        print("[DEV] Đang chạy source code, không thể update.")
        return

    try:
        current_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe) # VD: ConistLauncher.exe
        
        # 1. Định danh cho xác chết (VD: ConistLauncher.exe.trash)
        trash_path = os.path.join(current_dir, f"{exe_name}.trash")
        
        # Xóa trash cũ nếu lỡ còn sót
        if os.path.exists(trash_path):
            try: os.remove(trash_path)
            except: pass

        # 2. [MẤU CHỐT] Đổi tên chính mình thành rác (Windows CHO PHÉP làm điều này khi đang chạy)
        os.rename(current_exe, trash_path)
        print(f"[UPDATE] Đã đổi tên bản cũ thành: {trash_path}")
        
        # 3. Đưa bản mới vào ngai vàng (Vị trí file exe gốc)
        # new_exe_path là file vừa tải về (VD: ConistLauncher_v2.0.exe)
        shutil.move(new_exe_path, current_exe)
        print("[UPDATE] Bản mới đã vào vị trí.")
        
        # 4. Kích hoạt bản mới (Lúc này nó tên là ConistLauncher.exe chuẩn)
        subprocess.Popen([current_exe])
        print("[UPDATE] Đã bật bản mới. Tạm biệt!")
        
        # 5. Bản cũ tự sát ngay lập tức
        sys.exit(0)
        
    except Exception as e:
        print(f"[UPDATE] Lỗi nghiêm trọng: {e}")
        # Hồi phục: Nếu lỗi thì cố đổi tên lại như cũ để không hỏng App
        try:
            if os.path.exists(trash_path) and not os.path.exists(current_exe):
                os.rename(trash_path, current_exe)
        except: pass




def create_desktop_shortcut(target_path, icon_path):
    """Tạo shortcut ra Desktop bằng VBScript (Không cần thư viện ngoài)"""
    try:
        desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        link_name = "Conist Launcher.lnk"
        shortcut_path = os.path.join(desktop, link_name)
        #
        # Nếu shortcut đã tồn tại thì bỏ qua
        if os.path.exists(shortcut_path): return

        working_dir = os.path.dirname(target_path)
        vbs_content = f"""
        Set oWS = WScript.CreateObject("WScript.Shell")
        sLinkFile = "{shortcut_path}"
        Set oLink = oWS.CreateShortcut(sLinkFile)
        oLink.TargetPath = "{target_path}"
        oLink.IconLocation = "{icon_path}"
        oLink.WorkingDirectory = "{working_dir}"
        oLink.Description = "Conist Link Launcher v2.0"
        oLink.Save
        """
        vbs_path = os.path.join(working_dir, "create_shortcut.vbs")
        with open(vbs_path, "w") as f: f.write(vbs_content)
        
        os.system(f'cscript /nologo "{vbs_path}"')
        if os.path.exists(vbs_path): os.remove(vbs_path)
    except: pass















# Tên thư mục dữ liệu
DATA_DIR_NAME = "Launcher_Data"

# Đường dẫn tài nguyên (Trỏ thẳng vào thư mục đã được Vỏ giải nén)
BASE_DATA_PATH = os.path.join(get_base_path(), DATA_DIR_NAME)


# ==========================================
# 2. CẤU HÌNH & BIẾN TOÀN CỤC (DÙNG SAU KHI ĐÃ CÓ HÀM)
# ==========================================


CURRENT_VERSION = "2.0.2"


# Gọi hàm tính đường dẫn (Lúc này hàm đã được tạo ở trên rồi -> Không lỗi nữa)
BASE_DATA_PATH = os.path.join(get_base_path(), DATA_DIR_NAME)
if not os.path.exists(BASE_DATA_PATH): os.makedirs(BASE_DATA_PATH, exist_ok=True)

CONFIG_FILE = os.path.join(BASE_DATA_PATH, "launcher_config.json")
CACHE_FILE = os.path.join(BASE_DATA_PATH, "games_cache.json")
ICON_FOLDER = os.path.join(BASE_DATA_PATH, "icons")

os.makedirs(ICON_FOLDER, exist_ok=True)

APP_CONFIG = {"background": None, "download_dir": None} # [SỬA] Thêm download_dir mặc định là None
GAME_LIST = []
ACTIVE_DOWNLOADS = {} # Lưu trạng thái: { "GameName": {"paused": False, "cancelled": False} }
COMPLETED_GAMES = []  # Lưu tên game đã tải xong












# --- [NEW] HỆ THỐNG THÔNG BÁO XẾP CHỒNG (ROLLING STACK) ---
notification_stack = ft.Column(
    left=20, top=20, # Vị trí góc trên trái (đè lên Header)
    spacing=5,       # Khoảng cách giữa các thông báo
    alignment=ft.MainAxisAlignment.START,
)

# --- [V4.1 FINAL] HỆ THỐNG THÔNG BÁO (3 MÀU + GHIM UPDATE) ---
def show_push_notification(message, type="info", duration=4000, on_click_action=None, key=None):
    # 1. Chống Spam
    if key:
        for control in notification_stack.controls:
            if control.data == key: return

    # 2. Cấu hình 3 MÀU CHUẨN (Blue - Green - Red)
    config = {
        "info": {"color": "#2196F3", "icon": ft.icons.INFO},
        "success": {"color": "#4CAF50", "icon": ft.icons.CHECK},      # GREEN: Bắt đầu tải
        "warning": {"color": "#FFC107", "icon": ft.icons.WARNING},
        "error": {"color": "#F44336", "icon": ft.icons.ERROR},         # RED: Lỗi
        "update": {"color": "#D32F2F", "icon": ft.icons.CLOUD_DOWNLOAD},
        "loading": {"color": "#1976D2", "icon": ft.icons.DOWNLOADING}, # BLUE: Đang lấy tin
    }
    style = config.get(type, config["info"])
    
    banner_ref = [None]

    def close_banner(e=None):
        if banner_ref[0]:
            try:
                # Hiệu ứng đóng
                target_w = 30
                current_w = banner_ref[0].width
                while current_w > target_w + 5:
                    current_w += (target_w - current_w) * 0.2
                    banner_ref[0].width = current_w
                    banner_ref[0].opacity -= 0.1
                    if banner_ref[0].opacity < 0: banner_ref[0].opacity = 0
                    banner_ref[0].update()
                    time.sleep(0.02)

                if banner_ref[0] in notification_stack.controls:
                    notification_stack.controls.remove(banner_ref[0])
                    notification_stack.update()
            except: pass

    def handle_click(e):
        if on_click_action: on_click_action()
        close_banner()

    icon_box = ft.Container(
        content=ft.Icon(style["icon"], color="white", size=16),
        width=30, height=30, bgcolor=style["color"],
        border_radius=15, alignment=ft.alignment.center,
        rotate=ft.Rotate(0, alignment=ft.alignment.center),
    )

    text_content = ft.Container(
        content=ft.Text(message, color="white", size=11, weight="bold", no_wrap=True),
        padding=ft.padding.only(left=5, right=10),
        opacity=0, animate_opacity=300 
    )

    banner = ft.Container(
        data=key,
        content=ft.Row([icon_box, text_content], spacing=0),
        bgcolor=style["color"],
        width=30, height=30, border_radius=30,
        opacity=1,
        on_click=handle_click,
        on_long_press=close_banner,
    )
    
    banner_ref[0] = banner

    # --- [LOGIC GHIM UPDATE LÊN ĐẦU BẢNG] ---
    update_index = -1
    for i, ctrl in enumerate(notification_stack.controls):
        if ctrl.data == "update_alert":
            update_index = i
            break
    
    # Nếu có Update -> Chèn xuống dưới nó (Index 1)
    # Nếu bản thân thông báo này là Update -> Chèn lên đầu (Index 0)
    if update_index != -1 and type != "update":
        notification_stack.controls.insert(update_index + 1, banner)
    else:
        notification_stack.controls.insert(0, banner)
        
    notification_stack.update()

    # Animation chậm rãi
    def animate_physics():
        try:
            time.sleep(0.05)
            target_width = 280
            current_w = 30
            text_shown = False
            
            while abs(target_width - current_w) > 1:
                current_w += (target_width - current_w) * 0.08 # Hệ số chậm 0.08
                
                banner.width = current_w
                progress = (current_w - 30) / 250
                icon_box.rotate.angle = progress * -6.28
                
                if current_w > 180 and not text_shown:
                    text_content.opacity = 1
                    text_content.update()
                    text_shown = True
                
                banner.update()
                icon_box.update()
                time.sleep(0.016)
            
            banner.width = target_width
            icon_box.rotate.angle = -6.28
            if not text_shown: 
                text_content.opacity = 1
                text_content.update()
            banner.update()
            icon_box.update()

            if duration:
                time.sleep(duration / 1000)
                close_banner()
        except: pass

    threading.Thread(target=animate_physics, daemon=True).start()

















# Load Config
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f: 
            APP_CONFIG.update(json.load(f))
    except: pass

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f: 
            json.dump(APP_CONFIG, f, indent=4)
    except: pass

import ast # Thư viện giúp đọc list Python từ file text (đọc được None)

# ==========================================
# [NEW] HỆ THỐNG DATA TỰ ĐỘNG (FORMAT PYTHON RAW)
# ==========================================

# 1. Cấu hình đường dẫn (BẠN THAY LINK GITHUB CỦA BẠN VÀO ĐÂY)
# Link phải là dạng RAW (Bấm nút Raw trên Github rồi copy link)
URL_VERSION_FILE = "https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/data_version.txt"
URL_RAW_DATA_FILE = "https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/raw_games.txt"

# File lưu cục bộ trên máy người dùng
LOCAL_DATA_PATH = os.path.join(BASE_DATA_PATH, "local_games.txt")
LOCAL_VERSION_PATH = os.path.join(BASE_DATA_PATH, "data_version.txt")

# Dữ liệu mặc định (Backup khi không có mạng và chưa từng chạy)
RAW_GAME_DATA = [
    # Bạn có thể để 1 game mẫu hoặc để trống []
    {"name": "R.E.P.O", "version": "0.3.0", "lnd_url": "https://linkneverdie.net/game/r-e-p-o-b-9514", "download_link": "https://google.com", "viet_link": None, "subtitle": "Game sinh tồn, phiêu lưu thế giới mở"},
]

# --- [LOGIC DATA MỚI - TÁCH BIỆT] ---

# 1. Hàm tải trực tiếp (Dùng để bắt App chờ khi chưa có data)
def download_data_direct():
    try:
        timestamp = int(time.time())
        print(f"[DATA] Đang tải data gốc từ Github...")
        
        # Tải file Raw Games
        res = requests.get(f"{URL_RAW_DATA_FILE}?t={timestamp}", timeout=15)
        
        if res.status_code == 200:
            raw_content = res.text
            # Kiểm tra cú pháp (nếu sai cú pháp nó sẽ báo lỗi và nhảy xuống except)
            ast.literal_eval(raw_content) 
            
            # Lưu file vào máy
            with open(LOCAL_DATA_PATH, "w", encoding="utf-8") as f:
                f.write(raw_content)
            return True
        else:
            print(f"[DATA] Lỗi tải: {res.status_code}")
            return False
    except Exception as e:
        print(f"[DATA] Lỗi ngoại lệ khi tải: {e}")
        return False

# 2. Hàm check update ngầm (Chỉ chạy khi đã vào được App rồi)
def background_check_update():
    try:
        timestamp = int(time.time())
        # Check xem Github đang là version mấy
        res_ver = requests.get(f"{URL_VERSION_FILE}?t={timestamp}", timeout=5)
        
        if res_ver.status_code == 200:
            remote_ver = int(res_ver.text.strip())
            
            # Xem version trong máy là mấy
            local_ver = 0
            if os.path.exists(LOCAL_VERSION_PATH):
                with open(LOCAL_VERSION_PATH, "r") as f: local_ver = int(f.read().strip())
            
            print(f"[DATA] Local: {local_ver} | Server: {remote_ver}")

            # Nếu Server mới hơn -> Tải lại ngầm
            if remote_ver > local_ver:
                print(f"[DATA] Phát hiện bản mới. Đang cập nhật ngầm...")
                if download_data_direct(): # Tải xong
                    # Cập nhật số version trong máy
                    with open(LOCAL_VERSION_PATH, "w") as f: f.write(str(remote_ver))
                    print("[DATA] Đã cập nhật xong. (Cần khởi động lại để thấy game mới)")
    except Exception as e:
        print(f"[DATA] Lỗi check update ngầm: {e}")

def clean_name_for_slug(name):
    s = name.lower().replace(' ', '_').replace('.', '_').replace(':', '')
    s = re.sub(r'[^a-z0-9_]+', '', s)
    return s.strip('_')















# --- [FINAL CLEAN] SO SÁNH VERSION (KHÔNG DEBUG) ---
def is_version_match_smart(ver_online, ver_local):
    # Nếu dữ liệu lỗi -> Coi như khớp (Không báo update)
    if not ver_online or not ver_local or ver_online in ["Error", "Unknown", "N/A"]: 
        return True 

    # Hàm tách lấy danh sách số: "v1.2.3b" -> ['1', '2', '3']
    def get_nums(s): return re.findall(r'\d+', str(s))

    nums_web = get_nums(ver_online)
    nums_local = get_nums(ver_local)

    # [ĐÃ XÓA DÒNG PRINT DEBUG Ở ĐÂY]

    # Nếu cả 2 đều tìm thấy số -> So sánh từng cặp
    if nums_web and nums_local:
        min_len = min(len(nums_web), len(nums_local))
        match_count = 0
        for i in range(min_len):
            if int(nums_web[i]) == int(nums_local[i]):
                match_count += 1
            else:
                break 
        
        # Logic chấp nhận khớp
        if match_count == len(nums_local): return True
        if match_count == len(nums_web): return True
        
        return False

    # So sánh chuỗi thường nếu không có số
    return str(ver_local).lower().strip() in str(ver_online).lower().strip()

















def check_startup_status():
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, reg.KEY_READ)
        reg.QueryValueEx(key, "ConistLauncher")
        reg.CloseKey(key)
        return True
    except: return False

def toggle_startup(is_enabled):
    try:
        app_path = os.path.realpath(sys.argv[0])
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, reg.KEY_WRITE)
        if is_enabled:
            reg.SetValueEx(key, "ConistLauncher", 0, reg.REG_SZ, f'"{app_path}"')
        else:
            try: reg.DeleteValue(key, "ConistLauncher")
            except: pass
        reg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Lỗi Registry: {e}")
        return False

# --- [REPLACE TẠI DÒNG 49-53] ---
def fetch_lnd_version(lnd_url):
    if not lnd_url: return "N/A"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(lnd_url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        raw_ver = None
        
        # CÁCH 1: Tìm trong thẻ Info
        ver_p = soup.find('p', class_='data-label', string=re.compile(r'Phiên bản', re.I))
        if ver_p:
            ver_info = ver_p.find_next_sibling('p', class_='info')
            if ver_info: raw_ver = ver_info.get_text(strip=True)

        # CÁCH 2: Tìm trong Tiêu đề (BẮT MỌI LOẠI SỐ)
        if not raw_ver:
            title = soup.title.string if soup.title else ""
            # Regex mới: Bắt cụm "v" hoặc "Build" hoặc "Update" + Số bất kỳ
            # VD: "v1.0", "Build 123", "Update 5"
            match = re.search(r'(?:v|ver|build|update)\.?\s*(\d+(?:\.\d+)*)', title, re.I)
            if match:
                raw_ver = match.group(1)
            else:
                # Nếu không có chữ v/build, tìm cụm số có dấu chấm (1.0.2)
                match_dot = re.search(r'(\d+(?:\.\d+)+)', title)
                if match_dot: raw_ver = match_dot.group(1)
        
        return raw_ver if raw_ver else "Unknown"
    except Exception as e:
        print(f"Lỗi fetch LND: {e}")
        return "Error"

def get_lnd_image(lnd_url):
    """Hàm lấy ảnh bìa LND: Ưu tiên ID 'wallpaper_img' chuẩn xác"""
    if not lnd_url: return None
    try:
        # Headers giả lập Chrome để tránh bị chặn khi cào web
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://linkneverdie.net/'
        }
        response = requests.get(lnd_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- CÁCH 1 (ƯU TIÊN): Tìm theo ID 'wallpaper_img' ---
        # HTML: <img id="wallpaper_img" src="/Assets/Imgs/Post/..." >
        target_img = soup.find('img', id='wallpaper_img')
        
        if target_img:
            src = target_img.get('src')
            if src:
                # Nếu link dạng tương đối (/Assets/...) -> Ghép thêm domain
                if src.startswith("/"):
                    return "https://linkneverdie.net" + src
                return src

        # --- CÁCH 2 (DỰ PHÒNG): Tìm theo Meta Tag ---
        meta = soup.find('meta', property='og:image')
        if meta: return meta.get('content')
        
    except Exception as e: 
        print(f"[GET IMG ERROR] {e}")
    return None

def download_icon(img_url, save_path):
    try:
        # [QUAN TRỌNG] Luôn ép đuôi file thành .jpg
        if save_path.endswith(".png"):
            save_path = save_path.replace(".png", ".jpg")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://linkneverdie.net/'
        }
        
        response = requests.get(img_url, headers=headers, stream=True, timeout=10)
        
        if response.status_code == 200:
            img = Image.open(response.raw)
            
            # Xử lý ảnh
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            
            w, h = img.size
            min_d = min(w, h)
            left, top = (w - min_d)//2, (h - min_d)//2
            img = img.crop((left, top, left+min_d, top+min_d))
            img = img.resize((150, 150), Image.Resampling.LANCZOS)
            
            # Lưu đè file cũ
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            img.save(save_path, "JPEG", quality=85)
            return True
        return False
    except Exception as e: 
        # print(f"Lỗi tải: {e}")
        return False

def fetch_full_details(url):
    if not url: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        data = {}

        # 1. [FIX QUAN TRỌNG] Gọi hàm fetch_lnd_version để lấy version chuẩn
        # (Thay vì tự cào thủ công hay bị lỗi như code cũ)
        data['web_version'] = fetch_lnd_version(url)

        # 2. Lấy Cấu hình (Giữ nguyên)
        req_str = ""
        cols = [('game_area_sys_req_leftCol', 'TỐI THIỂU'), ('game_area_sys_req_rightCol', 'KHUYẾN NGHỊ')]
        for cls, title in cols:
            col = soup.find('div', class_=cls)
            if col:
                req_str += f"\n--- {title} ---\n"
                for li in col.find_all('li'):
                    req_str += li.get_text(strip=True) + "\n"
        data['requirements'] = req_str.strip() if req_str else "Không tìm thấy thông tin cấu hình."

        # 3. Lấy Album ảnh (Giữ nguyên logic 3 lớp)
        images = []
        # Lớp 1: Gallery
        screenshot_div = soup.find('div', id='screenshots_div')
        if screenshot_div:
            target_imgs = screenshot_div.find_all('img')
            for img in target_imgs:
                src = img.get('src') or img.get('data-src')
                if src:
                    if src.startswith("/"): src = "https://linkneverdie.net" + src
                    if src not in images: images.append(src)
        # Lớp 2: Ảnh nội dung
        if not images:
            content_imgs = soup.find_all('img', class_=re.compile(r'(fr-dib|fr-draggable)'))
            for img in content_imgs:
                src = img.get('src') or img.get('data-src')
                if src:
                    if src.startswith("/"): src = "https://linkneverdie.net" + src
                    if src not in images: images.append(src)
        # Lớp 3: Ảnh bìa
        if not images:
            meta_img = soup.find('meta', property='og:image')
            if meta_img: images.append(meta_img.get('content'))

        data['album'] = images[:10]

        return data
    except Exception as e:
        print(f"Lỗi scrap: {e}")
        return None

def play_click_sound():
    try:
        sound_path = "click_sound.wav"
        if os.path.exists(sound_path):
            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except: pass

# Khởi tạo dữ liệu



# ==========================================
# 2. CÁC CLASS HIỆU ỨNG
# ==========================================

class ParticleSystem:
    def __init__(self, page):
        self.page = page
        self.particles = []
        self.is_running = False
        self.icons = ["❄️", "🎄", "🎁", "🔔", "🎅", "🦌", "🍪", "⛄", "✨"]
        self.colors = ["#FF4444", "#4CAF50", "#2196F3", "#FFD700", "#FFFFFF", "#E040FB"]
        
        self.canvas = ft.Stack(expand=True)
        self.page.overlay.append(
            ft.TransparentPointer(
                ft.Container(content=self.canvas, expand=True)
            )
        )

    def spawn_particle(self, x, y, is_explosion=False):
        txt = ft.Text(
            random.choice(self.icons), 
            size=random.randint(14, 24),
            color=random.choice(self.colors),
            opacity=1.0
        )
        p_obj = ft.Container(content=txt, left=x, top=y)
        self.canvas.controls.append(p_obj)
        
        self.page.update()

        vx = random.uniform(-2, 2) if is_explosion else random.uniform(-0.5, 0.5)
        vy = random.uniform(-5, -2) if is_explosion else random.uniform(2, 5)
        self.particles.append([p_obj, x, y, vx, vy])

        if not self.is_running:
            self.is_running = True
            self.page.run_task(self.game_loop)

    async def game_loop(self):
        while self.particles:
            h = self.page.window.height
            to_remove = []
            for p in self.particles:
                p[4] += 0.2 
                p[1] += p[3] 
                p[2] += p[4] 
                p[0].left = p[1]
                p[0].top = p[2]
                p[0].rotate = ft.Rotate((p[2] / 10), alignment=ft.alignment.center)
                if p[2] > h + 50: to_remove.append(p)

            for p in to_remove:
                self.particles.remove(p)
                try: self.canvas.controls.remove(p[0])
                except: pass
            
            self.page.update()
            await __import__("asyncio").sleep(0.016)
        self.is_running = False


class SplashLoader:
    def __init__(self, page, on_finished):
        self.page = page
        self.on_finished = on_finished
        base_dir = get_base_path()
        
        # Đường dẫn ảnh splash
        splash_dir = os.path.join(base_dir, DATA_DIR_NAME, "splash_imgs")
        img_src = "https://via.placeholder.com/1920x1080?text=Conist+Launcher" # Ảnh mặc định
        
        if os.path.exists(splash_dir):
            valid = [f for f in os.listdir(splash_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            if valid:
                img_src = os.path.join(splash_dir, random.choice(valid))

        self.msg_txt = ft.Text("Loading resources...", color="white", size=12, italic=True)
        self.progress_bar = ft.ProgressBar(width=400, color="cyan", bgcolor="#30FFFFFF", height=4, border_radius=2)
        
        self.container = ft.Container(
            expand=True,
            bgcolor=None,
            alignment=ft.alignment.center,
            content=ft.Column([
                ft.Image(
                    src=img_src,
                    width=600,
                    height=350,   
                    fit=ft.ImageFit.CONTAIN,
                    border_radius=15,
                ),
                ft.Container(height=10),
                self.progress_bar,
                ft.Container(height=5),
                self.msg_txt,
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            animate_opacity=500, 
        )
        self.page.overlay.append(self.container)
        splash_icon = os.path.join(BASE_DATA_PATH, "app_icon.ico")
        if os.path.exists(splash_icon):
            self.page.window.icon = splash_icon 
            self.page.update()


    def start(self):
        self.page.run_task(self.animate_loading)

    async def animate_loading(self):
        # --- [FIX QUAN TRỌNG: KÍCH THƯỚC ẢO ĐỂ ÉP WINDOWS VẼ LẠI] ---
        # 1. Hiện cửa sổ
        self.page.window.visible = True
        
        # 2. Thay đổi kích thước +10px để ép layout cập nhật (Fix lỗi bẹp dí/màn đen)
        self.page.window.width = 1280 + 10
        self.page.window.height = 720 + 10
        self.page.update()
        
        # 3. Nghỉ cực ngắn để Windows kịp xử lý
        await asyncio.sleep(0.1)

        # 4. Trả về kích thước chuẩn ngay lập tức
        self.page.window.width = 1280
        self.page.window.height = 720
        self.page.window.center() # [FIX] Thêm .window vào giữa
        self.page.update()
        # -----------------------------------------------------------

        # Chạy thanh Loading
        flavors = ["Đang triệu hồi...", "Đang hack NASA...", "Chờ xíu...", "Sắp xong rồi..."]
        for i in range(101):
            current = i / 100.0
            self.progress_bar.value = current
            if i % 30 == 0: self.msg_txt.value = random.choice(flavors)
            if i % 5 == 0: self.page.update()
            await asyncio.sleep(0.015) 

        # Kết thúc Loading
        if self.on_finished: self.on_finished()
        
        # Hiệu ứng mờ dần và xóa Splash
        await asyncio.sleep(0.5)
        self.container.opacity = 0
        self.page.update()
        
        await asyncio.sleep(0.5)
        try:
            if self.container in self.page.overlay:
                self.page.overlay.remove(self.container)
        except: pass
        
        self.page.bgcolor = "transparent"
        self.page.update()

# ==========================================
# 3. GIAO DIỆN CHÍNH (MAIN APP)
# ==========================================

def main(page: ft.Page):
    cleanup_old_versions()
    
    # 1. Lấy đường dẫn gốc (Lúc này nó sẽ trỏ đúng về Desktop/Conist Link)
    base_dir = get_base_path()
    
    # Debug xem nó đã trỏ đúng chưa
    print(f"[PATH] Base Dir: {base_dir}")

    # 2. Định nghĩa các đường dẫn quan trọng
    icon_path = os.path.join(base_dir, "Launcher_Data", "app_icon.ico")
    
    # Định nghĩa exe_path (để tránh lỗi undefined phía dưới)
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = sys.executable 

    # 3. SET ICON CỬA SỔ
    if os.path.exists(icon_path):
        page.window.icon = icon_path
        print(f"[ICON] Đã tìm thấy: {icon_path}")
    else:
        # Thử tìm file icon nằm lẻ bên ngoài (dự phòng)
        fallback = os.path.join(base_dir, "app_icon.ico")
        if os.path.exists(fallback):
            page.window.icon = fallback
            print(f"[ICON] Dùng icon dự phòng: {fallback}")
        else:
            print(f"[ICON ERROR] Vẫn chưa thấy icon đâu cả!")

    # 4. SET APP ID (Taskbar)
    try:
        myappid = 'conist.link.launcher.v2.live' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except: pass
    

    # 3. SET ICON CHO CỬA SỔ APP
    if os.path.exists(icon_path):
        page.window.icon = icon_path
    else:
        # Dự phòng: Nếu chưa có trong Data thì tìm ngay cạnh file chạy
        fallback = os.path.join(base_dir, "app_icon.ico")
        if os.path.exists(fallback):
            page.window.icon = fallback
        print(f"[ICON] Đang dùng icon: {page.window.icon}")

    # 4. TẠO SHORTCUT (Chỉ chạy khi là file EXE)
    try:
        if getattr(sys, 'frozen', False):
            # Nếu có icon ảnh thì dùng, không thì dùng icon của file EXE
            shortcut_icon = icon_path if os.path.exists(icon_path) else exe_path
            
            # Gọi hàm tạo shortcut (đã sửa ở bước trước)
            create_desktop_shortcut(exe_path, shortcut_icon)
            print(f"[SHORTCUT] Đã kiểm tra/tạo shortcut.")
    except Exception as e:
        print(f"[SHORTCUT] Lỗi tạo shortcut: {e}")

    # --- TIẾP TỤC CODE CŨ (Xóa bớt phần check icon thừa phía dưới) ---
    
    global APP_CONFIG, file_picker, GAME_LIST
    
    # XÓA DANH SÁCH CŨ
    GAME_LIST.clear() 

    # ... (Các phần sau giữ nguyên)

    # --- [FIX QUAN TRỌNG] HÀM NẠP LẠI DỮ LIỆU & VẼ LẠI GRID ---
    def refresh_data_and_grid():
        GAME_LIST.clear()
        
        # 1. Đọc cache trạng thái (Đã cài/Chưa cài)
        cached_data = {}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_data = {g['name']: g for g in json.load(f)}
            except: pass

        # 2. Convert từ RAW Data sang Game Object
        for raw in RAW_GAME_DATA:
            slug = clean_name_for_slug(raw['name'])
            icon_path = os.path.join(ICON_FOLDER, f"{slug}.png")
            saved = cached_data.get(raw['name'], {})
            
            # Kiểm tra icon
            final_icon = icon_path if os.path.exists(icon_path) else raw.get('icon') or f"https://via.placeholder.com/150/000000/FFFFFF/?text={raw['name'][0]}"
            
            game_obj = {
                "name": raw['name'],
                "subtitle": raw.get('subtitle', ''),
                "version": raw['version'],
                "lnd_url": raw['lnd_url'],
                "download_link": raw['download_link'],
                "viet_link": raw.get('viet_link'),
                "icon": final_icon,
                "status": saved.get('status', 'CHƯA KIỂM TRA'),
                "requirements": saved.get('requirements', 'Đang cập nhật...'),
                "album_images": saved.get('album_images', [])
            }
            GAME_LIST.append(game_obj)

        # 3. Vẽ lại Grid (Nếu grid đã được khởi tạo)
        try:
            if grid:
                grid.controls.clear()
                for g in GAME_LIST: grid.controls.append(GameCard(g))
                grid.update()
        except: pass

    # Gọi lần đầu (Lúc này có thể chỉ có 1 game mặc định, kệ nó)
    refresh_data_and_grid()

    def save_cache():
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(GAME_LIST, f, indent=4, ensure_ascii=False)
        except: pass
    
# --- SETUP CỬA SỔ ---
    page.window.visible = False 
    page.window.always_on_top = True
    page.title = f"Conist Link Launcher v{CURRENT_VERSION}" 
    page.window.title_bar_hidden = True
    page.window.frameless = True
    page.window.bgcolor = ft.colors.TRANSPARENT
    page.bgcolor = ft.colors.TRANSPARENT 
    page.window.width = 1280
    page.window.height = 720
    page.window.center()
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.fonts = {"Segoe UI": "Segoe UI"}
    page.theme = ft.Theme(font_family="Segoe UI")
    page.update()

    # --- CÁC HÀM XỬ LÝ SỰ KIỆN (ĐÃ ĐƯỢC THỤT LỀ CHUẨN) ---
    
    def on_startup_change(e): 
        toggle_startup(e.control.value)

    def window_drag(e): 
        page.window.start_dragging()








# --- [FIX 1] KHAI BÁO BIẾN CỜ Ở ĐÂY ---
    is_scanning_updates = False 

    # Hàm xử lý chạy ngầm
    def process_game_updates_thread():
        # [QUAN TRỌNG] Dùng nonlocal để chỉnh sửa biến bên trong hàm main
        nonlocal is_scanning_updates 
        
        if is_scanning_updates: return
        is_scanning_updates = True
        
        count_update = 0
        total = len(GAME_LIST)
        print(f"[AUTO UPDATE] Bắt đầu quét {total} game...")
        
        # Chỉ hiện loading nếu là quét thủ công (hoặc lần đầu)
        if not APP_CONFIG.get("auto_update_games", False):
             show_push_notification("Đang kiểm tra cập nhật game ngầm...", "loading")

        try:
            for i, game in enumerate(GAME_LIST):
                # Kiểm tra xem switch còn bật không
                if not APP_CONFIG.get("auto_update_games", False):
                    break

                # Chỉ check game có link LND
                if game.get('lnd_url') and len(str(game.get('lnd_url'))) > 10:
                    try:
                        # Lấy version online
                        online_ver = fetch_lnd_version(game['lnd_url'])
                        local_ver = game['version']

                        if online_ver != "Error" and online_ver != "Unknown":
                            status_msg = ""
                            # --- [SỬA LOGIC SO SÁNH] ---
                        if online_ver != "Error" and online_ver != "Unknown":
                            status_msg = ""
                            
                            # Dùng hàm so sánh thông minh thay vì so sánh !=
                            is_match = is_version_match_smart(online_ver, local_ver)
                            
                            if not is_match:
                                # Nếu hàm bảo KHÔNG KHỚP -> Mới báo update
                                status_msg = f"CÓ BẢN MỚI: {online_ver}"
                                game['status'] = status_msg
                                count_update += 1
                                print(f"[UPDATE] {game['name']}: Local='{local_ver}' != Web='{online_ver}'")
                            else:
                                # Nếu hàm bảo KHỚP -> Báo đã cập nhật (dù string có thể hơi khác)
                                status_msg = "ĐÃ CẬP NHẬT"
                                game['status'] = status_msg
                                game['status'] = status_msg
                            
                            # Cập nhật UI Thẻ Game
                            try:
                                for card in grid.controls:
                                    if card.game['name'] == game['name']:
                                        card.status_txt.value = status_msg
                                        card.status_txt.color = "red" if "CÓ BẢN MỚI" in status_msg else "green"
                                        card.status_txt.update()
                                        break
                            except: pass
                    except: pass
                
                time.sleep(0.05) # Nghỉ xíu
            
            save_cache()
            
            if count_update > 0:
                show_push_notification(f"Quét xong: {count_update} game có bản mới!", "warning")
            elif APP_CONFIG.get("auto_update_games", False):
                # Chỉ báo khi quét xong đợt đầu
                pass 
                
        except Exception as e:
            print(f"Lỗi Auto Scan: {e}")
        
        is_scanning_updates = False








# --- [DÁN ĐOẠN NÀY VÀO NGAY SAU process_game_updates_thread] ---
    
    def on_auto_update_switch(e):
        is_on = e.control.value
        APP_CONFIG["auto_update_games"] = is_on
        save_config()
        
        if is_on:
            show_push_notification("Đã BẬT tự động cập nhật", "info")
            # Kích hoạt quét ngay lập tức
            threading.Thread(target=process_game_updates_thread, daemon=True).start()
        else:
            show_push_notification("Đã TẮT tự động cập nhật", "info")

    # ----------------------------------------------------------------








    def toggle_settings_drawer(e=None):
        if settings_drawer.offset.x > 0: # --- MỞ SETTINGS ---
            settings_drawer.visible = True
            settings_drawer.update()
            time.sleep(0.02)
            settings_drawer.offset = ft.Offset(0, 0)
            blur_overlay.visible = True
            blur_overlay.opacity = 1
            
            # [FIX] Ẩn nút Download ngay khi mở Settings
            dl_trigger_zone.visible = False 
            dl_trigger_zone.update()
            
        else: # --- ĐÓNG SETTINGS ---
            settings_drawer.offset = ft.Offset(1.1, 0)
            blur_overlay.opacity = 0
            
            # [FIX] Hiện lại nút Download khi về màn hình chính
            dl_trigger_zone.visible = True
            dl_trigger_zone.update()
            
            def hide_overlay():
                time.sleep(0.6)
                settings_drawer.visible = False
                blur_overlay.visible = False
                page.update()
            threading.Thread(target=hide_overlay, daemon=True).start()
        page.update()

    def on_search(e):
        val = search_box.value.lower() if e and e.control else ""
        filtered = [g for g in GAME_LIST if val in g['name'].lower()]
        grid.controls.clear()
        for g in filtered: grid.controls.append(GameCard(g))
        grid.update()

    def hover_search(e):
        is_expand = e.data == "true" or search_box.value != ""
        search_container.width = 320 if is_expand else 45
        search_container.bgcolor = "#90000000" if is_expand else "#33FFFFFF"
        search_container.update()

    # --- KHỞI TẠO SEARCH BOX ---
    search_box = ft.TextField(
        hint_text="Tìm kiếm...", border_width=0, bgcolor="transparent", 
        height=40, content_padding=ft.padding.only(left=10, bottom=5), text_size=14, 
        on_change=on_search, expand=True 
    )

    search_container = ft.Container(
        width=45, height=45, bgcolor="#33FFFFFF",
        border_radius=15, alignment=ft.alignment.center_right,
        padding=ft.padding.only(right=5),
        animate=ft.Animation(800, "easeOutBack"), 
        on_hover=hover_search,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=ft.Row([
            search_box,
            ft.Container(content=ft.Icon(ft.icons.SEARCH, color="white", size=20), padding=5)
        ], spacing=0)
    )


    # --- [THÊM LOGIC CHỌN ẢNH] ---
    # --- 2. KHỞI TẠO BIẾN ---
    particle_sys = ParticleSystem(page)
    
    grid = ft.GridView(
        expand=True, runs_count=5, max_extent=180, child_aspect_ratio=0.7,
        spacing=20, run_spacing=20, padding=20,
    )

    # --- 3. UI CLASSES ---

    class AnimatedLogo(ft.Container):
        def __init__(self):
            super().__init__()
            self.height = 35 
            self.padding = ft.padding.symmetric(horizontal=8, vertical=0)
            self.border_radius = 6 
            self.bgcolor = "transparent"
            self.clip_behavior = ft.ClipBehavior.HARD_EDGE 
            self.animate = ft.Animation(300, "easeOut") 
            self.on_hover = self.hover_effect
            self.alignment = ft.alignment.center_left 
            
            self.shine_beam = ft.Container(
                width=30, 
                height=35, 
                gradient=ft.LinearGradient(
                    colors=["#00FFFFFF", "#60FFFFFF", "#00FFFFFF"], 
                    begin=ft.alignment.center_left, end=ft.alignment.center_right,
                ),
                rotate=ft.Rotate(0.5),
                offset=ft.Offset(-2, 0), 
                animate_offset=ft.Animation(800, "easeOut"), 
            )

            self.text_content = ft.Container(
                padding=ft.padding.only(bottom=3), 
                content=ft.Row([
                    ft.Text("Conist Link Launcher", size=20, weight="bold", color="white", font_family="Segoe UI"),
                    ft.Container(width=6), 
                    
                    # [SỬA] Dùng f-string để lấy biến CURRENT_VERSION
                    ft.Text(f"v{CURRENT_VERSION}", size=12, color="#AAAAAA", italic=True, weight="bold")
                ], 
                spacing=0, 
                vertical_alignment=ft.CrossAxisAlignment.END 
                )
            )

            self.content = ft.Stack([
                self.shine_beam,
                self.text_content
            ], alignment=ft.alignment.center_left)

        def hover_effect(self, e):
            is_hover = e.data == "true"
            if is_hover:
                self.bgcolor = "#20FFFFFF" 
                self.border = ft.border.all(1, "#40FFFFFF")
                self.shine_beam.offset = ft.Offset(15, 0) 
                self.shine_beam.opacity = 1
            else:
                self.bgcolor = "transparent"
                self.border = None
                self.shine_beam.offset = ft.Offset(-2, 0)
                self.shine_beam.opacity = 0
            
            self.update()
            self.shine_beam.update()

    
    # -------------------------------------------------------

    class GameCard(ft.Container):
        def __init__(self, game_data):
            super().__init__()
            self.game = game_data 
            self.width = 160
            self.height = 230
            self.border_radius = 15
            self.default_bg = "#80000000" 
            self.bgcolor = self.default_bg 
            self.padding = 10
            self.animate_scale = ft.Animation(200, "easeOut")
            self.animate = ft.Animation(200, "easeOut") 
            self.on_click = lambda e: (play_click_sound(), self.open_detail(e))
            self.on_hover = self.hover_card
            
            stt = self.game['status']
            stt_col = "green" if "ĐÃ CẬP NHẬT" in stt else ("orange" if "CÓ BẢN MỚI" in stt else "grey")
            
            self.status_txt = ft.Text(stt, size=10, color=stt_col, weight="bold", no_wrap=True)
            self.img_control = ft.Image(src=self.game['icon'], width=140, height=140, border_radius=10, fit=ft.ImageFit.COVER)
            
            self.content = ft.Column([
            self.img_control,
                ft.Text(self.game['name'], size=14, weight="bold", no_wrap=True, text_align="center", width=140),
                ft.Text(self.game['subtitle'][:20], size=10, italic=True, color="grey", no_wrap=True),
                ft.Container(content=self.status_txt, alignment=ft.alignment.center)
            ], 
            spacing=5, 
            alignment=ft.MainAxisAlignment.START, 
            horizontal_alignment=ft.CrossAxisAlignment.CENTER) # <--- [FIX] THÊM DÒNG NÀY ĐỂ CĂN GIỮA

        def hover_card(self, e):
            is_hover = e.data == "true"
            self.scale = 1.05 if is_hover else 1.0
            self.bgcolor = "#33FFFFFF" if is_hover else self.default_bg 
            self.update()

        def open_detail(self, e): show_game_detail_dialog(self.game, self)
        
        def refresh_ui(self):
            self.img_control.src = self.game['icon']
            stt = self.game['status']
            self.status_txt.value = stt
            self.status_txt.color = "green" if "ĐÃ CẬP NHẬT" in stt else "orange"
            self.img_control.update()
            self.status_txt.update()

    # [HÀM NÀY NẰM BÊN TRONG MAIN - THỤT VÀO 1 TAB SO VỚI def main()]
    def download_file_with_state(url, dest_path, progress_callback, control_state, game_name=None):
        try:
            print(f"🔗 CMD: Đang xử lý link: {url}") # Log cho CMD
            
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Connection': 'keep-alive',
            }

            # --- GIAI ĐOẠN 1: XỬ LÝ LINK GOOGLE DRIVE ---
            file_id = None
            match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
            if match: file_id = match.group(1)
            else:
                match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
                if match: file_id = match.group(1)

            final_response = None
            
            if not file_id:
                final_response = session.get(url, headers=headers, stream=True)
            else:
                URL_EXPORT = "https://docs.google.com/uc?export=download"
                response = session.get(URL_EXPORT, params={'id': file_id}, headers=headers, stream=True)
                
                if "text/html" in response.headers.get("Content-Type", "").lower():
                    soup = BeautifulSoup(response.text, 'html.parser')
                    form = soup.find('form', id='download-form')
                    if form:
                        action_url = form.get('action')
                        inputs = form.find_all('input')
                        params = {}
                        for inp in inputs:
                            if inp.get('name'): params[inp.get('name')] = inp.get('value')
                        final_response = session.get(action_url, params=params, headers=headers, stream=True)
                    else: 
                        download_btn = soup.find('a', id='uc-download-link')
                        if download_btn:
                            href = download_btn.get('href')
                            if href:
                                if href.startswith("/"): href = "https://docs.google.com" + href
                                final_response = session.get(href, headers=headers, stream=True)
                        else:
                            final_response = response
                else:
                    final_response = response

            # --- GIAI ĐOẠN 2: "BẮT" TÍN HIỆU TỪ CMD ĐỂ HIỆN THÔNG BÁO ---
            
            # TRƯỜNG HỢP 1: Lỗi mạng hoặc Link chết (Status Code None hoặc 404, 500...)
            if not final_response or final_response.status_code != 200:
                err_code = final_response.status_code if final_response else 'Mất kết nối'
                print(f"CMD: Lỗi tải - Status Code {err_code}")
                
                # [THÔNG BÁO ĐỎ]
                show_push_notification(f"Lỗi tải: Mã {err_code} (Link hỏng?)", "error")
                return False

            # TRƯỜNG HỢP 2: Link trả về trang Web (HTML) thay vì File Game
            if "text/html" in final_response.headers.get("Content-Type", "").lower():
                print("CMD: Lỗi tải - Link chưa direct")
                
                # [THÔNG BÁO ĐỎ]
                show_push_notification("Lỗi: Link yêu cầu đăng nhập hoặc xác minh!", "error")
                return False

            total_size = int(final_response.headers.get('Content-Length', 0))

            # TRƯỜNG HỢP 3: MỌI THỨ OK -> BẮT ĐẦU TẢI
            if game_name:
                print(f"CMD: Bắt đầu tải {game_name}")
                # [THÔNG BÁO XANH LÁ]
                show_push_notification(f"Kết nối thành công! Đang tải {game_name}...", "success")

            # --- GIAI ĐOẠN 3: GHI FILE (Giữ nguyên) ---
            block_size = 1024 * 1024 
            wrote = 0
            last_time = time.time()
            last_wrote = 0
            
            with open(dest_path, "wb") as f:
                for data in final_response.iter_content(block_size):
                    if control_state["cancelled"]:
                        f.close()
                        return False
                    
                    while control_state["paused"]:
                        if control_state["cancelled"]: 
                            f.close()
                            return False
                        time.sleep(1)
                        
                    if data:
                        wrote += len(data)
                        f.write(data)
                        
                        current_time = time.time()
                        if current_time - last_time > 0.5:
                            duration = current_time - last_time
                            bytes_diff = wrote - last_wrote
                            speed = (bytes_diff / 1024 / 1024) / duration
                            speed_str = f"{speed:.1f} MB/s"
                            if progress_callback:
                                if total_size > 0: progress_callback(wrote / total_size, speed_str)
                                else: progress_callback(0, speed_str)
                            last_time = current_time
                            last_wrote = wrote
            
            return True

        except Exception as e:
            print(f"CMD: Lỗi ngoại lệ: {e}")
            # [THÔNG BÁO ĐỎ] Bắt lỗi Crash
            show_push_notification(f"Lỗi hệ thống: {str(e)[:20]}...", "error")
            return False
        




















        def on_startup_change(e): toggle_startup(e.control.value)
        def window_drag(e): page.window.start_dragging()
        
        def toggle_settings_drawer(e=None):
            if settings_drawer.offset.x > 0: # Mở
                settings_drawer.visible = True
                settings_drawer.update()
                time.sleep(0.02)
                settings_drawer.offset = ft.Offset(0, 0)
                blur_overlay.visible = True
                blur_overlay.opacity = 1
            else: # Đóng
                settings_drawer.offset = ft.Offset(1.1, 0)
                blur_overlay.opacity = 0
                def hide_overlay():
                    time.sleep(0.6)
                    settings_drawer.visible = False
                    blur_overlay.visible = False
                    page.update()
                threading.Thread(target=hide_overlay, daemon=True).start()
            page.update()

        def on_search(e):
            val = search_box.value.lower() if e and e.control else ""
            filtered = [g for g in GAME_LIST if val in g['name'].lower()]
            grid.controls.clear()
            for g in filtered: grid.controls.append(GameCard(g))
            grid.update()

    # --- 5. ANIMATION ICON ---
    icon_setting = ft.Icon(
        ft.icons.SETTINGS, color="white", size=24,
        rotate=ft.Rotate(0, alignment=ft.alignment.center),
        animate_rotation=ft.Animation(500, "easeOutBack"),
    )
    icon_home = ft.Icon(
        ft.icons.HOME, color="white", size=24,
        offset=ft.Offset(0, 0),
        animate_offset=ft.Animation(300, "bounceOut"),
    )

    def animate_setting_btn(e):
        # [FIX] Lấy trực tiếp Icon đang nằm trong nút (Content)
        # Thay vì gọi biến 'icon_setting' từ bên ngoài (dễ bị lag nhịp đầu)
        icon = e.control.content 
        
        # Xoay icon
        icon.rotate.angle = 3.14 if e.data == "true" else 0
        icon.update()
        
        # Làm mờ nút chứa icon
        e.control.opacity = 1.0 if e.data == "true" else 0.5
        e.control.update()

    def animate_home_btn(e):
        icon_home.offset.y = -0.3 if e.data == "true" else 0
        icon_home.update()
        e.control.opacity = 1.0 if e.data == "true" else 0.5
        e.control.update()

    # --- 6. GIAO DIỆN & OVERLAY ---
    blur_overlay = ft.Container(
        expand=True,
        bgcolor="#0DFFFFFF",
        blur=ft.Blur(30, 30, ft.BlurTileMode.MIRROR),
        animate_opacity=400, opacity=0, visible=False,
        on_click=toggle_settings_drawer
    )
# --- [PHẦN 1] LOGIC VÀ NÚT BẤM (Đặt TRƯỚC settings_drawer) ---




























    # Trong app_core.py

    def start_self_update(url, version):
        try:
            url_code = "https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/app_core.py"
            show_push_notification("Đang tải bản cập nhật lõi...", "loading")
            
            res = requests.get(url_code)
            
            if res.status_code == 200:
                new_code = res.text
                
                # Xác định đường dẫn
                base_dir = get_base_path()
                core_path = os.path.join(base_dir, "Launcher_Data", "icons", "app_core.py")
                
                # 1. Ghi đè code mới
                import ctypes
                FILE_ATTRIBUTE_NORMAL = 0x80
                try: ctypes.windll.kernel32.SetFileAttributesW(core_path, FILE_ATTRIBUTE_NORMAL)
                except: pass

                with open(core_path, "w", encoding="utf-8") as f:
                    f.write(new_code)
                
                try: ctypes.windll.kernel32.SetFileAttributesW(core_path, 0x06)
                except: pass
                
                # 2. Lưu version
                try:
                    v_path = os.path.join(base_dir, "Launcher_Data", "version.json")
                    with open(v_path, "w") as f:
                        f.write(json.dumps({"latest_version": version}))
                except: pass

                show_push_notification("Cập nhật xong! Đang nạp lại...", "success")
                time.sleep(1)

                # --- [THAY ĐỔI QUAN TRỌNG: SOFT RESTART] ---
                # 3. Tạo tín hiệu Restart cho file Vỏ
                restart_signal = os.path.join(base_dir, "Launcher_Data", "restart.signal")
                with open(restart_signal, "w") as f:
                    f.write("RESTART")

                # 4. Đóng cửa sổ hiện tại
                # Việc này sẽ kết thúc hàm ft.app() bên file bootstrap.py
                # bootstrap.py sẽ thấy file restart.signal và chạy lại vòng lặp
                page.window.close()
                
            else:
                show_push_notification("Lỗi tải bản cập nhật", "error")
                
        except Exception as e:
            print(f"Lỗi update code: {e}")
            show_push_notification(f"Lỗi: {str(e)}", "error")


















    def manual_check_update(e):
        # Cập nhật giao diện nút bấm
        btn_system_check.text = "Đang kết nối..."
        btn_system_check.disabled = True
        page.update()

        def check_thread():
            try:
                import time
                timestamp = int(time.time())
                # Link version
                RAW_URL = f"https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/version.json?t={timestamp}"
                
                res = requests.get(RAW_URL, timeout=5)
                data = res.json()
                
                server_ver = data["latest_version"].strip()
                local_ver = CURRENT_VERSION.strip()
                download_url = data.get("download_url", "") 

                # LOGIC KIỂM TRA
                if server_ver != local_ver:
                    btn_system_check.text = "Đã phát hiện bản mới!"
                    
                    if download_url:
                        show_push_notification(
                            f"Đã có phiên bản mới v{server_ver}", 
                            type="update", 
                            duration=None, 
                            key="update_alert", # [FIX] Thêm dòng này để chống trùng
                            on_click_action=lambda: start_self_update(download_url, server_ver)
                        )
                    else:
                        show_push_notification("Lỗi: Bản mới chưa có Link tải!", "error")
                else:
                    btn_system_check.text = "Bạn đang ở bản mới nhất!"
                    show_push_notification("Hệ thống đã cập nhật", "success")

            except Exception as e:
                print(f"Lỗi update: {e}")
                btn_system_check.text = "Lỗi kết nối Server!"
                show_push_notification("Lỗi kết nối máy chủ", "error")
            
            # Reset trạng thái nút sau 2 giây
            time.sleep(2)
            try:
                btn_system_check.disabled = False
                btn_system_check.text = "Kiểm tra cập nhật"
                btn_system_check.update()
            except: pass

        threading.Thread(target=check_thread, daemon=True).start()
        
        # Reset nút bấm
        time.sleep(2)
        btn_system_check.disabled = False
        if btn_system_check.text != "Kiểm tra cập nhật":
             time.sleep(2)
             btn_system_check.text = "Kiểm tra cập nhật"
        btn_system_check.update()


















    # Tạo nút bấm
    btn_system_check = ft.ElevatedButton(
        "Kiểm tra cập nhật", 
        icon=ft.icons.CLOUD_SYNC, 
        bgcolor="#222222", 
        color="white",
        height=45,
        width=300,
        on_click=manual_check_update
    )
    # --- [ADD] CÔNG CỤ DÒ TỌA ĐỘ (DEV TOOL) ---
    # --- [NEW] CÔNG CỤ DÒ TỌA ĐỘ (RELATIVE) ---
    coord_text = ft.Text("x:0 y:0", size=10, color="white", font_family="Consolas", weight="bold")
    
    coord_container = ft.Container(
        content=coord_text,
        bgcolor="#90000000",
        padding=ft.padding.symmetric(horizontal=5, vertical=2),
        border_radius=3,
        right=5, bottom=5,
        visible=False, 
        animate_opacity=200
    )

    # --- [NEW] CÔNG CỤ DÒ TỌA ĐỘ V2 (PRO MAX) ---
    coord_text = ft.Text("", size=11, color="#00FF00", font_family="Consolas", weight="bold")
    
    coord_container = ft.Container(
        content=coord_text,
        bgcolor="#E6000000", # Nền đen đậm hơn để dễ đọc
        padding=10,
        border_radius=5,
        border=ft.border.all(1, "green"), # Viền xanh cho ngầu
        right=10, bottom=10,
        visible=False, 
        animate_opacity=200
    )

    def start_coord_tracking(is_on):
        coord_container.visible = is_on
        coord_container.update()

        if is_on:
            def tracking_loop():
                TARGET_TITLE = f"Conist Link Launcher v{CURRENT_VERSION}"
                
                import math 
                
                while coord_container.visible:
                    # ... (code bên dưới giữ nguyên)
                    x, y = get_relative_cursor_pos(TARGET_TITLE)
                    
                    # 1. Tính khoảng cách tới đáy (Hữu ích khi đặt nút ở dưới)
                    to_bottom = 720 - y
                    
                    # 2. Tính đường chéo (Diagonal)
                    diagonal = int(math.sqrt(x**2 + y**2))
                    
                    if 0 <= x <= 1280 and 0 <= y <= 720:
                        # Format hiển thị đa thông tin
                        info = (
                            f"📍 POS: X={x} | Y={y}\n"
                            f"⬇️ BTM: {to_bottom}px (Cách đáy)\n"
                            f"📐 DIAG: {diagonal}px"
                        )
                        coord_text.color = "#00FF00"
                        coord_container.border = ft.border.all(1, "green")
                    else:
                        info = f"OUT: {x}, {y}"
                        coord_text.color = "red"
                        coord_container.border = ft.border.all(1, "red")

                    coord_text.value = info
                    coord_text.update()
                    time.sleep(0.05) # 20 FPS
            
            threading.Thread(target=tracking_loop, daemon=True).start()

























    # --- [PHẦN 2] GIAO DIỆN SIDEBAR ---
    settings_drawer = ft.Container(
        width=380, # [Update] Thu nhỏ bề ngang lại chút cho đẹp (Cũ là 770 quá to)
        bgcolor="#CC1E1E1E", # Màu tối hơn chút
        blur=ft.Blur(20, 20, ft.BlurTileMode.MIRROR),
        right=0, top=0, bottom=0,
        offset=ft.Offset(1.1, 0), 
        visible=False,
        animate_offset=ft.Animation(600, "easeOutQuart"), 
        padding=30, shadow=ft.BoxShadow(blur_radius=50, color="#000000"),
        
        content=ft.Column([
            ft.Row([
                ft.Text("CÀI ĐẶT", size=24, weight="bold"), # Chữ nhỏ lại xíu
                ft.Container(expand=True),
                ft.IconButton(ft.icons.CLOSE, on_click=toggle_settings_drawer)
            ]),
            ft.Divider(height=10, color="grey"), 
            
            # --- CỤM CÔNG TẮC (GOM GỌN) ---
            ft.Column([
                ft.Switch(label="Khởi động cùng Windows", value=check_startup_status(), on_change=on_startup_change),
                ft.Container(height=5), # Khoảng cách nhỏ 5px
                
                ft.Switch(label="Âm thanh hiệu ứng", value=True),
                ft.Container(height=5), 

                # Nút Update mới thêm vào (Nằm ngay dưới)
                ft.Switch(
                    label="Tự động check Update Game", 
                    value=APP_CONFIG.get("auto_update_games", False), 
                    on_change=on_auto_update_switch
                ),
                ft.Container(height=5), 

                ft.Switch(
                    label="Hiện tọa độ chuột (Dev)", 
                    value=False, 
                    on_change=lambda e: start_coord_tracking(e.control.value)
                ),
            ], spacing=0),
            
            ft.Container(height=20), # Cách ra 1 đoạn để đến nút bấm

            # --- CỤM NÚT BẤM ---
            ft.ElevatedButton(
                "Đổi Hình Nền Launcher", 
                icon=ft.icons.IMAGE, 
                bgcolor="#333333", color="white",
                height=45, width=300, 
                on_click=lambda _: file_picker.pick_files(allowed_extensions=["png", "jpg", "jpeg"])
            ),

            ft.Container(height=10),
            
            btn_system_check, # Nút kiểm tra cập nhật App

            btn_system_check, # Nút kiểm tra cập nhật App

            ft.Container(expand=True), 
            
            # [SỬA] Dùng f-string để hiển thị đúng version
            ft.Text(f"Conist Link Launcher v{CURRENT_VERSION}", italic=True, color="grey", size=12)
        ])
    )
    # --- SEARCH BOX ---
    def hover_search(e):
        is_expand = e.data == "true" or search_box.value != ""
        search_container.width = 320 if is_expand else 45
        search_container.bgcolor = "#90000000" if is_expand else "#33FFFFFF"
        search_container.update()

    search_box = ft.TextField(
        hint_text="Tìm kiếm...", border_width=0, bgcolor="transparent", 
        height=40, content_padding=ft.padding.only(left=10, bottom=5), text_size=14, 
        on_change=on_search, expand=True 
    )

    search_container = ft.Container(
        width=45,
        height=45,
        bgcolor="#33FFFFFF",
        border_radius=15,
        alignment=ft.alignment.center_right,
        padding=ft.padding.only(right=5),
        animate=ft.Animation(800, "easeOutBack"), 
        on_hover=hover_search,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=ft.Row([
            search_box,
            ft.Container(content=ft.Icon(ft.icons.SEARCH, color="white", size=20), padding=5)
        ], spacing=0)
    )

    # --- HEADER ---
    # [ĐÃ SỬA] Header có tính năng kéo thả cửa sổ
    # --- 1. KHAI BÁO BANNER UPDATE ---
    
# 1. HÀM ĐÓNG THÔNG BÁO (Thêm cái này ngay trước banner)
    # 1. HÀM ĐÓNG THÔNG BÁO (Click vào nút X tròn)
    # 1. HÀM ĐÓNG & MỞ LINK



    # 2. ĐỊNH NGHĨA "BÁNH XE" (Cục tròn đỏ chứa chữ X)

    # 3. ĐỊNH NGHĨA THANH BANNER CHÍNH
    
   # --- [SỬA LẠI] ICON BAY CHO GIỐNG NÚT DƯỚI ---
    # --- [FIX LÊN CAO] ANIMATION (X:67 - START Y:530) ---
    dl_arrow_icon = ft.Icon(ft.icons.ARROW_DOWNWARD, color="white", size=32)
    
    dl_anim_box = ft.Container(
        content=dl_arrow_icon,
        width=65, height=65,
        bgcolor="transparent", 
        border_radius=5,
        border=None,           
        
        # [FIX] Xuất phát: X=67, Y=530 (Bay xuống 620)
        left=67, top=530,
        
        visible=False, 
        animate_position=ft.Animation(800, "easeOutBack"), 
        animate_opacity=ft.Animation(300, "easeIn"),
    )

    # Hàm chạy kịch bản Animation (V11.0 - Đích Y:620)
    async def run_download_anim():
        # 1. Reset về vị trí xuất phát (530)
        dl_anim_box.top = 530
        dl_anim_box.opacity = 1
        dl_anim_box.visible = True
        dl_anim_box.border = None
        dl_anim_box.bgcolor = None 
        dl_anim_box.update()
        
        await asyncio.sleep(0.1)
        
        # 2. Bay xuống đích (620)
        dl_anim_box.top = 620 
        dl_anim_box.update()
        
        # Chờ bay xong (0.8s)
        await asyncio.sleep(0.8)
        
        # 3. Biến mất
        dl_anim_box.opacity = 0
        dl_anim_box.update()
        
        await asyncio.sleep(0.3)
        dl_anim_box.visible = False
        dl_anim_box.update()









        
        # [Mẹo] Kích hoạt nút thật hiện lên 1 chút để báo hiệu
        dl_btn_visible.opacity = 1
        dl_btn_visible.update()
        await asyncio.sleep(0.5)
        dl_btn_visible.opacity = 0 # Lại tàng hình
        dl_btn_visible.update()

    # --- [ADD] 2. LOGIC CHỌN THƯ MỤC & TẢI ---
    def on_dir_result(e: ft.FilePickerResultEvent):
        if e.path:
            # Lưu đường dẫn vào Config ngay
            APP_CONFIG["download_dir"] = e.path
            save_config()
            
            # Gọi lại hàm tải game (Lúc này đã có đường dẫn)
            if hasattr(dir_picker, "pending_game_data"):
                trigger_download_process(dir_picker.pending_game_data)

    dir_picker = ft.FilePicker(on_result=on_dir_result)
    page.overlay.append(dir_picker)














# --- [V7.3] LOGIC GIẢI NÉN & CHẠY GAME (AUTO ADMIN RIGHTS) ---
    def handle_play_game(game_name, e, spinner, status_txt, btn_play, progress_overlay):
        # Setup UI
        btn_play.visible = False
        spinner.visible = True
        status_txt.value = "Đang xử lý..."
        status_txt.color = "white"
        progress_overlay.width = 0 
        
        btn_play.update()
        spinner.update()
        status_txt.update()
        progress_overlay.update()

        def extract_thread():
            import zipfile
            import subprocess
            import time
            import ctypes # Cần thư viện này để xin quyền Admin
            
            save_path = APP_CONFIG.get("download_dir")
            slug = clean_name_for_slug(game_name)
            archive_file = os.path.join(save_path, f"{slug}.zip")
            extract_folder = os.path.join(save_path, slug)

            try:
                # --- GIAI ĐOẠN 1: GIẢI NÉN ---
                if os.path.exists(archive_file):
                    status_txt.value = "Đang giải nén..."
                    status_txt.update()
                    
                    is_extracted = False
                    
                    # CÁCH 1: ZIPFILE
                    if zipfile.is_zipfile(archive_file):
                        try:
                            with zipfile.ZipFile(archive_file, 'r') as zf:
                                file_list = zf.infolist()
                                total_size = sum([f.file_size for f in file_list])
                                extracted_size = 0
                                for file in file_list:
                                    zf.extract(file, extract_folder, pwd=b"linkneverdie.com")
                                    extracted_size += file.file_size
                                    
                                    ratio = extracted_size / max(total_size, 1)
                                    progress_overlay.width = 380 * ratio 
                                    progress_overlay.update()
                            is_extracted = True
                        except: pass 
                    
                    # CÁCH 2: WINRAR
                    if not is_extracted:
                        status_txt.value = "WinRAR đang chạy..."
                        status_txt.update()
                        
                        winrar_exe = r"C:\Program Files\WinRAR\WinRAR.exe"
                        if not os.path.exists(winrar_exe):
                            winrar_exe = r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
                        
                        if os.path.exists(winrar_exe):
                            cmd = [
                                winrar_exe, "x", "-pLinkNeverDie.Com", "-plinkneverdie.com", "-ibck", "-y", 
                                archive_file, extract_folder + "\\"
                            ]
                            
                            process = subprocess.Popen(cmd, shell=True)
                            fake_width = 0
                            while process.poll() is None:
                                if fake_width < 340:
                                    fake_width += 5
                                    progress_overlay.width = fake_width
                                    progress_overlay.update()
                                time.sleep(0.1)
                            
                            progress_overlay.width = 380
                            progress_overlay.update()
                            is_extracted = True
                        else:
                            raise Exception("Cần cài WinRAR để giải nén file này!")

                    try: os.remove(archive_file)
                    except: pass
                
                # --- GIAI ĐOẠN 2: TÌM FILE GAME ---
                status_txt.value = "Đang tìm file chạy..."
                status_txt.update()
                
                target_exe = None
                black_list = ["unitycrashhandler", "uninstall", "update", "dxsetup", "vcredist", "cleanup", "redist"]
                
                candidates = [] 

                for root, dirs, files in os.walk(extract_folder):
                    for file in files:
                        if file.lower().endswith(".exe"):
                            full_path = os.path.join(root, file)
                            lower_name = file.lower()
                            
                            if any(x in lower_name for x in black_list): continue
                            
                            score = 0
                            if lower_name.endswith("lnd game launcher.exe"): score = 10000
                            
                            clean_game = clean_name_for_slug(game_name).replace("_", "")
                            clean_file = lower_name.replace(".exe", "").replace("_", "").replace(".", "").replace(" ", "")
                            if clean_game in clean_file: score += 100
                            
                            if "launcher" in lower_name: score += 50
                            
                            candidates.append((score, full_path))

                if candidates:
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    print(f"🎯 List ứng viên: {[(os.path.basename(c[1]), c[0]) for c in candidates]}")
                    target_exe = candidates[0][1]

                # --- GIAI ĐOẠN 3: CHẠY GAME (FIX ERROR 740) ---
                if target_exe:
                    status_txt.value = "Đang khởi động..."
                    status_txt.color = "green"
                    status_txt.update()
                    
                    working_dir = os.path.dirname(target_exe)
                    
                    try:
                        # Cách 1: Thử chạy bình thường
                        subprocess.Popen([target_exe], cwd=working_dir)
                        
                    except OSError as err:
                        # Nếu gặp lỗi 740 (Thiếu quyền Admin)
                        if err.winerror == 740:
                            print("⚠️ Cần quyền Admin, đang yêu cầu UAC...")
                            status_txt.value = "Đang yêu cầu quyền Admin..." # [ĐÃ SỬA]
                            status_txt.update()
                            
                            # Cách 2: Dùng ShellExecute để chạy với quyền 'runas' (Admin)
                            ctypes.windll.shell32.ShellExecuteW(
                                None, 
                                "runas", # Tham số quan trọng để kích hoạt Admin
                                target_exe, 
                                None, 
                                working_dir, 
                                1
                            )
                            show_push_notification(f"Đã yêu cầu quyền Admin...", "warning")
                        else:
                            raise err # Nếu là lỗi khác thì ném ra ngoài
                else:
                    status_txt.value = "Không tìm thấy file EXE!"
                    status_txt.color = "red"
                    show_push_notification("Không tìm thấy file game!", "error")
                    os.startfile(extract_folder)

            except Exception as e:
                status_txt.value = f"Lỗi: {str(e)[:15]}..."
                status_txt.color = "red"
                print(f"Lỗi: {e}")
                try: os.startfile(save_path)
                except: pass
            
            # Reset UI
            time.sleep(3)
            btn_play.visible = True
            spinner.visible = False
            progress_overlay.width = 0 
            status_txt.value = "Sẵn sàng chơi"
            status_txt.color = "#AAAAAA"
            
            btn_play.update()
            spinner.update()
            status_txt.update()
            progress_overlay.update()

        threading.Thread(target=extract_thread, daemon=True).start()







# --- [FIX FINAL] QUẢN LÝ UI DOWNLOAD (REALTIME) ---

    # 1. Hai danh sách chứa thẻ (Biến toàn cục để hàm khác gọi được)
    # [QUAN TRỌNG] Phải khai báo 2 biến này trước khi dùng trong downloads_drawer
    download_list_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    finished_list_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

    # 2. Hàm tìm Icon chuẩn từ GAME_LIST
    def get_real_game_icon(game_name):
        for g in GAME_LIST:
            if g['name'] == game_name:
                return g['icon']
        return "https://via.placeholder.com/50"
# 3. Hàm tạo Card Đang Tải (BẠN ĐANG THIẾU HÀM NÀY)
    def create_downloading_card_ui(game_name, icon_src, on_pause_click, on_cancel_click):
        pb = ft.ProgressBar(value=0, color="cyan", bgcolor="#444444", height=4, border_radius=2)
        txt_percent = ft.Text("Đang kết nối...", size=10, color="cyan")
        txt_speed = ft.Text("0 MB/s", size=10, color="#AAAAAA")
        
        btn_pause = ft.IconButton(ft.icons.PAUSE_CIRCLE_FILLED, icon_color="yellow", icon_size=24, tooltip="Tạm dừng/Tiếp tục", on_click=on_pause_click)
        btn_cancel = ft.IconButton(ft.icons.CANCEL, icon_color="red", icon_size=24, tooltip="Hủy tải xuống", on_click=on_cancel_click)
        img_icon = ft.Image(src=icon_src, width=50, height=50, border_radius=8, fit=ft.ImageFit.COVER)

        card = ft.Container(
            bgcolor="#20FFFFFF", padding=10, border_radius=12,
            animate_scale=ft.Animation(200, "easeOut"),
            on_hover=lambda e: (setattr(e.control, 'scale', 1.02 if e.data=='true' else 1.0) or e.control.update()),
            content=ft.Row([
                img_icon,
                ft.Column([
                    ft.Row([
                        ft.Text(game_name, color="white", weight="bold", size=13),
                        ft.Container(expand=True),
                        ft.Row([btn_pause, btn_cancel], spacing=0)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    pb,
                    ft.Row([txt_percent, txt_speed], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=3, expand=True)
            ])
        )
        return card, pb, txt_percent, txt_speed, btn_pause
# --- [UPGRADE] UI CARD VỚI NÚT ĐIỀU KHIỂN ---
    # 4. Hàm tạo Card "Đã xong" (FIX: Nút Play căn giữa tuyệt đối)
    def create_finished_card(name, icon_src, version, on_play_click):
        # 1. Màn che tiến độ (Overlay)
        progress_overlay = ft.Container(
            width=0, 
            height=70, # [FIX] Khớp với chiều cao thẻ
            bgcolor="#BB000000", 
            border_radius=12,
            animate=ft.Animation(300, "easeOut"), 
        )

        # 2. Spinner & Nút Play
        spinner = ft.ProgressRing(width=25, height=25, stroke_width=3, color="white", visible=False)
        
        status_txt = ft.Text("Sẵn sàng chơi", size=10, color="#AAAAAA", italic=True)
        
        btn_play = ft.IconButton(
            ft.icons.PLAY_ARROW_ROUNDED, 
            icon_color="green", 
            icon_size=30, 
            tooltip="Chơi ngay",
            on_click=lambda e: on_play_click(e, spinner, status_txt, btn_play, progress_overlay)
        )

        return ft.Container(
            height=70, # [QUAN TRỌNG] Khóa chiều cao cố định để căn giữa không bị lệch
            bgcolor="#20FFFFFF", padding=0, border_radius=12,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Stack([
                # LAYER 1: Nội dung nền (Căn trái)
                ft.Container(
                    padding=10,
                    alignment=ft.alignment.center_left, # Căn giữa dọc cho nội dung
                    content=ft.Row([
                        ft.Image(src=icon_src, width=50, height=50, border_radius=8, fit=ft.ImageFit.COVER),
                        ft.Column([
                            ft.Text(name, color="#88FF88", weight="bold", size=13),
                            ft.Text(f"Phiên bản: {version}", size=11, color="grey"),
                            status_txt, 
                        ], spacing=2, alignment=ft.MainAxisAlignment.CENTER), # Căn giữa dọc text
                        ft.Container(width=50) # Khoảng trống đệm cho nút Play
                    ])
                ),

                # LAYER 2: Màn che
                ft.Container(content=progress_overlay, alignment=ft.alignment.center_left),

                # LAYER 3: Nút Play (Căn CHÍNH GIỮA BÊN PHẢI)
                ft.Container(
                    expand=True, # [QUAN TRỌNG] Bung hết chiều cao thẻ
                    padding=ft.padding.only(right=15), # Cách lề phải 15px
                    alignment=ft.alignment.center_right, # Căn giữa dọc + Căn phải ngang
                    content=ft.Stack([
                        btn_play,
                        spinner
                    ], alignment=ft.alignment.center) # Spinner đè đúng lên vị trí nút Play
                )
            ], expand=True) 
        )


    # 1. Overlay làm tối nền khi mở tab Download
    dl_overlay_blur = ft.Container(
        expand=True,
        bgcolor="#0D000000", # Đen mờ nhẹ
        blur=ft.Blur(10, 10, ft.BlurTileMode.MIRROR),
        opacity=0, visible=False,
        animate_opacity=300,
        on_click=lambda e: close_downloads_drawer() # Bấm ra ngoài là đóng
    )

    # 2. Logic Đóng/Mở Tab (ĐÃ FIX LỖI THU VỀ KHÔNG HẾT)
    def open_downloads_drawer(e=None):
        downloads_drawer.left = 0 # Trượt ra sát mép trái
        downloads_drawer.update()
        
        dl_overlay_blur.visible = True
        dl_overlay_blur.opacity = 1
        dl_overlay_blur.update()

    def close_downloads_drawer(e=None):
        # [FIX] Tab rộng 380, phải giấu về -400 thì mới mất hẳn (tính cả bóng)
        downloads_drawer.left = -400 
        downloads_drawer.update()
        
        dl_overlay_blur.opacity = 0
        dl_overlay_blur.update()
        









    # 5. Giao diện Tab Download (Đã gắn biến danh sách thật, KHÔNG CÒN GỌI HÀM CŨ)
    downloads_drawer = ft.Container(
        width=380, height=720, 
        bgcolor="#CC121212", blur=ft.Blur(15, 15, ft.BlurTileMode.MIRROR), 
        border_radius=ft.border_radius.only(top_right=30, bottom_right=30),
        left=-400, top=0, padding=0, 
        animate_position=ft.Animation(600, "easeOutQuint"), 
        shadow=ft.BoxShadow(blur_radius=60, color=ft.colors.with_opacity(0.6, "black"), offset=ft.Offset(15, 0)),
        
        content=ft.Column([
            ft.Container(
                padding=20,
                content=ft.Row([
                    ft.Icon(ft.icons.DOWNLOAD_ROUNDED, color="cyan", size=28),
                    ft.Text("KHO TẢI XUỐNG", size=18, weight="bold", color="white", font_family="Segoe UI"),
                    ft.Container(expand=True),
                    ft.IconButton(ft.icons.CLOSE, icon_color="white", on_click=close_downloads_drawer)
                ])
            ),
            ft.Tabs(
                selected_index=0,
                animation_duration=300,
                indicator_color="cyan", label_color="cyan", unselected_label_color="grey", divider_color="transparent",
                tabs=[
                    # [FIX] Chỉ chứa biến danh sách, không gọi hàm tạo thẻ giả nữa
                    ft.Tab(text="TIẾN ĐỘ", content=ft.Container(padding=15, bgcolor="#30000000", content=download_list_col)), 
                    ft.Tab(text="ĐÃ XONG", content=ft.Container(padding=15, bgcolor="#30000000", content=finished_list_col)), 
                ],
                expand=True
            )
        ])
    )


    # --- [UPGRADE] NÚT KÍCH HOẠT "FRAMELESS" ---
    
    # --- [FIX] NÚT HIỂN THỊ (SIZE 65 - VỊ TRÍ 55 - KHỚP 100%) ---
    
    # 1. Giao diện nút
    dl_btn_visible = ft.Container(
        content=ft.Icon(
            ft.icons.ARROW_DOWNWARD, 
            color="white",           
            size=32, # Icon 32 cân đối trong khung 65
        ),
        width=65, height=65, # [FIX] Size 65
        bgcolor=None, 
        border=None, 
        alignment=ft.alignment.center,
        shadow=None, 
        
        opacity=0, 
        scale=0.8, 
        animate_opacity=300,
        animate_scale=ft.Animation(400, "easeOutBack"),
    )

    # 2. Logic cảm ứng
    def hover_dl_zone(e):
        is_hover = e.data == "true"
        dl_btn_visible.opacity = 1 if is_hover else 0
        dl_btn_visible.scale = 1.1 if is_hover else 0.8
        dl_btn_visible.update()

   # 3. Vùng chứa nút (Đã nâng lên 25px -> Y:620)
    dl_trigger_zone = ft.Container(
        content=dl_btn_visible,
        width=65, height=65, 
        bgcolor=None,
        alignment=ft.alignment.center,
        
        # [FIX] Tọa độ: X=67, Y=620
        left=67, top=620, 
        
        on_hover=hover_dl_zone,
        on_click=open_downloads_drawer,
        tooltip="Quản lý tải xuống"
    )





    # [FIX] Thêm tham số is_update mặc định là False
    def trigger_download_process(game_data, is_update=False):
        game_name = game_data['name']
        
        # Nếu là update thì tải về cùng thư mục với file exe hiện tại
        if is_update:
            save_path = get_base_path()
        else:
            save_path = APP_CONFIG.get("download_dir")
        
        if not save_path:
            dir_picker.pending_game_data = game_data 
            dir_picker.get_directory_path("Chọn nơi lưu Game")
            return

        slug = clean_name_for_slug(game_name)
        
        # Đặt tên file
        if is_update:
            file_name = f"Conist Launcher v{game_data['version']}.exe"
            file_path = os.path.join(save_path, file_name)
        else:
            file_path = os.path.join(save_path, f"{slug}.zip")

        if game_name in ACTIVE_DOWNLOADS:
            show_push_notification(f"Đang tải {game_name}...", "warning")
            open_downloads_drawer()
            return
            
        if os.path.exists(file_path): 
             try: os.remove(file_path)
             except: pass

        ctrl_state = {"paused": False, "cancelled": False}
        ACTIVE_DOWNLOADS[game_name] = ctrl_state
        
        # Chạy animation bay icon (nếu muốn)
        page.run_task(run_download_anim)

        real_icon = game_data['icon']
        
        # --- [FIX QUAN TRỌNG] LOGIC NÚT DỪNG & HỦY ---
        
        def toggle_pause(e):
            # Chỉ cho pause nếu chưa bị hủy
            if not ctrl_state["cancelled"]:
                ctrl_state["paused"] = not ctrl_state["paused"]
                # Đổi icon: Nếu đang pause thì hiện nút Play, ngược lại hiện Pause
                e.control.icon = ft.icons.PLAY_CIRCLE_FILLED if ctrl_state["paused"] else ft.icons.PAUSE_CIRCLE_FILLED
                e.control.icon_color = "green" if ctrl_state["paused"] else "yellow"
                e.control.tooltip = "Tiếp tục" if ctrl_state["paused"] else "Tạm dừng"
                e.control.update()

        def cancel_download(e):
            # 1. Gửi tín hiệu hủy cho luồng tải (để nó dừng ghi file)
            ctrl_state["cancelled"] = True
            
            # 2. [FIX ZOMBIE] Xóa NGAY LẬP TỨC thẻ khỏi giao diện
            # Không chờ luồng phản hồi (vì lỡ luồng chết rồi thì sao?)
            try:
                if card_ui in download_list_col.controls:
                    download_list_col.controls.remove(card_ui)
                    download_list_col.update()
            except: pass

            # 3. Dọn dẹp dữ liệu
            if game_name in ACTIVE_DOWNLOADS: del ACTIVE_DOWNLOADS[game_name]
            
            # 4. Xóa file rác nếu đang tải dở
            try:
                if os.path.exists(file_path): os.remove(file_path)
            except: pass
            
            show_push_notification(f"Đã xóa {game_name}", "error")

        # Tạo UI Card
        card_ui, pb, txt_pct, txt_spd, btn_pause_ref = create_downloading_card_ui(
            game_name, real_icon, toggle_pause, cancel_download
        )
        download_list_col.controls.insert(0, card_ui) 
        download_list_col.update()

        def update_progress_ui(ratio, speed_str="0 MB/s"):
            if ctrl_state["cancelled"]: return
            pb.value = ratio
            txt_pct.value = f"{int(ratio * 100)}%"
            txt_spd.value = speed_str
            pb.update()
            txt_pct.update()
            txt_spd.update()

        def download_thread():
            try:
                success = download_file_with_state(
                    game_data['download_link'], 
                    file_path, 
                    update_progress_ui,
                    ctrl_state,
                    game_name
                )
                
                # --- TRƯỜNG HỢP 1: TẢI THÀNH CÔNG ---
                if success and not ctrl_state["cancelled"]:
                    show_push_notification(f"Hoàn tất {game_name}!", "success")
                    winsound.MessageBeep()
                    
                    # Tự động xóa thẻ tải
                    if card_ui in download_list_col.controls:
                        download_list_col.controls.remove(card_ui)
                        download_list_col.update()
                    
                    if game_name in ACTIVE_DOWNLOADS: del ACTIVE_DOWNLOADS[game_name]

                    if is_update:
                        handle_self_update(file_path)
                    else:
                        finished_card = create_finished_card(
                            game_name, real_icon, game_data['version'],
                            lambda e, i, t, b, p: handle_play_game(game_name, e, i, t, b, p)
                        )
                        finished_list_col.controls.insert(0, finished_card)
                        finished_list_col.update()
                        COMPLETED_GAMES.append(game_name)

                # --- TRƯỜNG HỢP 2: BỊ HỦY (Đã xử lý ở nút Cancel rồi, nhưng cứ check cho chắc) ---
                elif ctrl_state["cancelled"]:
                    pass 
                
                # --- TRƯỜNG HỢP 3: LỖI TẢI (MẠNG/LINK HỎNG) ---
                else:
                    txt_pct.value = "LỖI TẢI - HÃY XÓA"
                    txt_pct.color = "red"
                    txt_spd.value = "Check Link/Mạng"
                    pb.bgcolor = "#550000"
                    
                    # Ẩn nút Pause đi vì lỗi rồi pause gì nữa
                    btn_pause_ref.visible = False
                    btn_pause_ref.update()
                    
                    txt_pct.update()
                    txt_spd.update()
                    pb.update()
                    
                    # [QUAN TRỌNG] Xóa khỏi danh sách active để không kẹt logic
                    if game_name in ACTIVE_DOWNLOADS: del ACTIVE_DOWNLOADS[game_name]

            except Exception as e:
                print(f"Lỗi Thread: {e}")
                # Gặp lỗi ngoại lệ cũng báo lên UI
                try:
                    txt_pct.value = "CRASH LỖI"
                    txt_pct.color = "red"
                    btn_pause_ref.visible = False
                    btn_pause_ref.update()
                    txt_pct.update()
                except: pass
                
                if game_name in ACTIVE_DOWNLOADS: del ACTIVE_DOWNLOADS[game_name]

        threading.Thread(target=download_thread, daemon=True).start()














    # 4. HEADER (Giữ nguyên cấu trúc, chỉ đảm bảo update_banner được đặt đúng chỗ)
    header = ft.Container(
        height=70, 
        padding=ft.padding.symmetric(horizontal=20),
        bgcolor="#44000000", 
        border=ft.border.only(bottom=ft.border.BorderSide(1, "#20FFFFFF")),
        content=ft.Row([
            ft.GestureDetector(
                on_pan_start=window_drag,
                on_tap_down=lambda e: particle_sys.spawn_particle(e.global_x, e.global_y, True),
                content=AnimatedLogo()
            ),
            ft.WindowDragArea(ft.Container(bgcolor="transparent", expand=True), expand=True),
            search_container, 
            ft.Container(width=10),
            ft.IconButton(ft.icons.MINIMIZE, on_click=lambda e: setattr(page.window, 'minimized', True) or page.update()),
            ft.IconButton(ft.icons.CLOSE, icon_color="red", on_click=lambda e: page.window.close())
        ])
    )

    # --- [NEW] 1. CÁC NÚT TRÊN THANH SIDEBAR ---
    # Nút Cài đặt (Icon xoay khi hover)
    btn_setting_sidebar = ft.Container(
        content=icon_setting, # Dùng lại icon đã khai báo ở trên
        width=50, height=50, 
        bgcolor="#33FFFFFF", border_radius=15, 
        alignment=ft.alignment.center,
        on_click=toggle_settings_drawer, 
        tooltip="Cài đặt hệ thống",
        on_hover=animate_setting_btn # Hàm animate đã có sẵn ở trên
    )

    # Nút Trang chủ (Icon nảy lên khi hover)
    btn_home_sidebar = ft.Container(
        content=icon_home, # Dùng lại icon đã khai báo ở trên
        width=50, height=50, 
        bgcolor="#33FFFFFF", border_radius=15, 
        alignment=ft.alignment.center,
        on_click=lambda e: on_search(None), # Về trang chủ là reset tìm kiếm
        tooltip="Về trang chủ",
        on_hover=animate_home_btn # Hàm animate đã có sẵn ở trên
    )
# --- [NEW FIXED] CÁC NÚT SIDEBAR & ANIMATION ---
    
    # --- [FULL FIX SIDEBAR - REPLACE ALL] ---

    # 1. Hàm xử lý Animation cho nút (Đã Fix lỗi lần đầu)
    def animate_sidebar_btn(e):
        icon = e.control.content
        is_hover = e.data == "true"
        
        # Logic xoay icon Cài đặt
        if icon.name == ft.icons.SETTINGS:
            icon.rotate.angle = 3.14 if is_hover else 0
            
        # Logic nảy icon Home
        elif icon.name == ft.icons.HOME:
            icon.offset.y = -0.3 if is_hover else 0

        # Hiệu ứng mờ & zoom
        e.control.opacity = 1.0 if is_hover else 0.5 
        e.control.scale = 1.1 if is_hover else 1.0   
        
        icon.update()
        e.control.update()

    # 2. Định nghĩa các nút (Có opacity=0.5 để kích hoạt animation)
    btn_setting_sidebar = ft.Container(
        content=ft.Icon(
            ft.icons.SETTINGS, color="white", size=24,
            rotate=ft.Rotate(0, alignment=ft.alignment.center),
            animate_rotation=ft.Animation(400, "easeOutBack"),
        ),
        width=50, height=50, 
        bgcolor="#33FFFFFF", border_radius=15, 
        alignment=ft.alignment.center,
        opacity=0.5, animate_opacity=200, animate_scale=ft.Animation(200, "easeOut"),
        on_click=toggle_settings_drawer, 
        tooltip="Cài đặt hệ thống",
        on_hover=animate_sidebar_btn
    )

    btn_home_sidebar = ft.Container(
        content=ft.Icon(
            ft.icons.HOME, color="white", size=24,
            offset=ft.Offset(0, 0),
            animate_offset=ft.Animation(300, "bounceOut"),
        ),
        width=50, height=50, 
        bgcolor="#33FFFFFF", border_radius=15, 
        alignment=ft.alignment.center,
        opacity=0.5, animate_opacity=200, animate_scale=ft.Animation(200, "easeOut"),
        on_click=lambda e: on_search(None),
        tooltip="Về trang chủ",
        on_hover=animate_sidebar_btn
    )

    # 3. [MISSING] Lớp mờ nền (Biến mà bạn đang bị báo lỗi thiếu)
    sidebar_blur_layer = ft.Container(
        expand=True,
        bgcolor="#1A000000",
        blur=ft.Blur(5, 5, ft.BlurTileMode.MIRROR),
        opacity=0,
        animate_opacity=300,
        visible=False 
    )

    # 4. Logic ẩn hiện Sidebar (Chống xung đột)
    sidebar_state = {"trigger": False, "sidebar": False}

    def sidebar_logic(e):
        is_hover = e.data == "true"
        if e.control.data == "trigger":
            sidebar_state["trigger"] = is_hover
        elif e.control.data == "sidebar":
            sidebar_state["sidebar"] = is_hover

        should_open = sidebar_state["trigger"] or sidebar_state["sidebar"]

        if should_open:
            sidebar_container.offset = ft.Offset(0, 0)
            sidebar_blur_layer.visible = True
            sidebar_blur_layer.opacity = 1
            sidebar_container.update()
            sidebar_blur_layer.update()
        else:
            def close_sequence():
                time.sleep(0.1) 
                if not (sidebar_state["trigger"] or sidebar_state["sidebar"]):
                    sidebar_container.offset = ft.Offset(1.1, 0)
                    sidebar_blur_layer.opacity = 0
                    sidebar_container.update()
                    sidebar_blur_layer.update()
                    
                    time.sleep(0.3)
                    if sidebar_container.offset.x > 0.5:
                        sidebar_blur_layer.visible = False
                        try: page.update()
                        except: pass
            threading.Thread(target=close_sequence, daemon=True).start()

    # 5. Khung Sidebar chính
    sidebar_container = ft.Container(
        data="sidebar",
        width=200, 
        bgcolor="#44000000", 
        top=0, bottom=0, right=0,
        border_radius=ft.border_radius.only(top_left=20, bottom_left=20),
        offset=ft.Offset(1.1, 0),
        animate_offset=ft.Animation(300, "easeOut"), 
        on_hover=sidebar_logic, 
        padding=ft.padding.only(bottom=30),
        content=ft.Column([
            ft.WindowDragArea(ft.Container(bgcolor="transparent", expand=True), expand=True),
            ft.Row([btn_setting_sidebar], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=20),
            ft.Row([btn_home_sidebar], alignment=ft.MainAxisAlignment.CENTER),
        ], alignment=ft.MainAxisAlignment.END)
    )

    # 6. Vùng cảm ứng (Trigger)
    trigger_zone = ft.Container(
        data="trigger",
        width=60, 
        top=70, bottom=0, right=0,
        bgcolor=None,
        on_hover=sidebar_logic 
    )
# --- [FIX LOGIC] BIẾN TRẠNG THÁI ĐỂ TRÁNH XUNG ĐỘT ---
    # Biến này giúp nhớ xem chuột đang ở Trigger hay đang ở Sidebar
    sidebar_state = {"trigger": False, "sidebar": False}

    def sidebar_logic(e):
        # 1. Cập nhật trạng thái chuột (Dựa vào thẻ data mình gắn bên dưới)
        is_hover = e.data == "true"
        if e.control.data == "trigger":
            sidebar_state["trigger"] = is_hover
        elif e.control.data == "sidebar":
            sidebar_state["sidebar"] = is_hover

        # 2. Logic quyết định: Chỉ cần chuột ở 1 trong 2 nơi là MỞ
        should_open = sidebar_state["trigger"] or sidebar_state["sidebar"]

        if should_open:
            # MỞ SIDEBAR NGAY LẬP TỨC
            sidebar_container.offset = ft.Offset(0, 0)
            sidebar_blur_layer.visible = True
            sidebar_blur_layer.opacity = 1
            sidebar_container.update()
            sidebar_blur_layer.update()
        else:
            # 3. Delay nhẹ 0.1s: Để chuột kịp nhảy từ Trigger sang Sidebar mà không bị đóng
            def close_sequence():
                time.sleep(0.1) 
                # Check lại lần chốt: Nếu chuột không ở cả 2 nơi thì mới đóng
                if not (sidebar_state["trigger"] or sidebar_state["sidebar"]):
                    sidebar_container.offset = ft.Offset(1.1, 0)
                    sidebar_blur_layer.opacity = 0
                    sidebar_container.update()
                    sidebar_blur_layer.update()
                    
                    # Đợi Sidebar thụt vào xong (0.3s) mới tắt hẳn layer mờ
                    time.sleep(0.3)
                    if sidebar_container.offset.x > 0.5:
                        sidebar_blur_layer.visible = False
                        try: page.update()
                        except: pass
            
            threading.Thread(target=close_sequence, daemon=True).start()

    # --- [NEW] 3. CONTAINER CHÍNH CỦA SIDEBAR ---
    sidebar_container = ft.Container(
        data="sidebar", # [QUAN TRỌNG] Đánh dấu tên để Logic nhận diện
        width=200, 
        bgcolor="#44000000", 
        top=0, bottom=0, right=0,
        border_radius=ft.border_radius.only(top_left=20, bottom_left=20),
        offset=ft.Offset(1.1, 0),
        animate_offset=ft.Animation(300, "easeOut"), 
        on_hover=sidebar_logic, 
        padding=ft.padding.only(bottom=30),
        content=ft.Column([
            ft.WindowDragArea(ft.Container(bgcolor="transparent", expand=True), expand=True),
            ft.Row([btn_setting_sidebar], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=20),
            ft.Row([btn_home_sidebar], alignment=ft.MainAxisAlignment.CENTER),
        ], alignment=ft.MainAxisAlignment.END)
    )

    # --- [NEW] 4. VÙNG CẢM ỨNG (TRIGGER ZONE) ---
    # Đây là vùng trong suốt sát mép phải để chuột chạm vào là Sidebar hiện ra
    trigger_zone = ft.Container(
        data="trigger", # [QUAN TRỌNG] Phải có dòng này thì logic mới chạy
        width=60, 
        top=70, bottom=0, right=0,
        bgcolor=None, # Trong suốt hoàn toàn
        on_hover=sidebar_logic 
    )
# --- [ADD] TAB QUẢN LÝ DOWNLOAD ---

    # 1. Overlay làm tối nền khi mở tab Download
    dl_overlay_blur = ft.Container(
        expand=True,
        bgcolor="#0D000000", # Đen mờ nhẹ
        blur=ft.Blur(10, 10, ft.BlurTileMode.MIRROR),
        opacity=0, visible=False,
        animate_opacity=300,
        on_click=lambda e: close_downloads_drawer() # Bấm ra ngoài là đóng
    )

    # 2. Logic Đóng/Mở Tab (ĐÃ FIX LỖI THU VỀ KHÔNG HẾT)
    def open_downloads_drawer(e=None):
        downloads_drawer.left = 0 # Trượt ra sát mép trái
        downloads_drawer.update()
        
        dl_overlay_blur.visible = True
        dl_overlay_blur.opacity = 1
        dl_overlay_blur.update()

    def close_downloads_drawer(e=None):
        # [FIX] Tab rộng 380, phải giấu về -400 thì mới mất hẳn (tính cả bóng)
        downloads_drawer.left = -400 
        downloads_drawer.update()
        
        dl_overlay_blur.opacity = 0
        dl_overlay_blur.update()
        
        def delay_hide_overlay():
            time.sleep(0.4) # Chờ animation chạy xong (khớp với thời gian animation bên dưới)
            dl_overlay_blur.visible = False
            page.update()
        threading.Thread(target=delay_hide_overlay, daemon=True).start()


















            # --- [FINAL V2] SHINE BUTTON (TO ĐẸP & CLICKABLE) ---
# =================================================================
    # 1. CLASS SHINE BUTTON (NÚT UPDATE)
    # =================================================================
    class ShineButton(ft.Container):
        def __init__(self, text="Kiểm tra Update", width=200, height=50, on_click_action=None):
            super().__init__()
            self.width = width
            self.height = height
            self.border_radius = 8
            self.bgcolor = "#444444" 
            self.clip_behavior = ft.ClipBehavior.HARD_EDGE
            self.on_click = on_click_action 
            self.is_loading = False

            # Tia sáng
            self.shine = ft.Container(
                width=120, height=height * 3, 
                gradient=ft.LinearGradient(
                    colors=["#00FFFFFF", "#20FFFFFF", "#80FFFFFF", "#20FFFFFF", "#00FFFFFF"], 
                    begin=ft.alignment.center_left, end=ft.alignment.center_right,
                ),
                rotate=ft.Rotate(0.5),
                offset=ft.Offset(-2, 0),
                opacity=0, 
                animate_offset=ft.Animation(0), 
            )

            # Nội dung
            self.icon_control = ft.Icon(ft.icons.CLOUD, color="white", size=20)
            self.text_control = ft.Text(text, color="white", weight="bold", size=13)
            
            self.content = ft.Stack([
                self.shine,      
                ft.Row([self.icon_control, self.text_control], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
            ], alignment=ft.alignment.center)

        def start_loading(self):
            if self.is_loading: return
            self.is_loading = True
            self.text_control.value = "Đang kiểm tra..."
            self.bgcolor = "#555555"
            self.icon_control.name = ft.icons.CLOUD_SYNC
            self.disabled = True 
            self.update()

            def loop_anim():
                while self.is_loading:
                    # Reset
                    self.shine.animate_offset = ft.Animation(0) 
                    self.shine.offset = ft.Offset(-2, 0)
                    self.shine.opacity = 0 
                    self.shine.update()
                    time.sleep(0.05)
                    if not self.is_loading: break

                    # Run
                    self.shine.animate_offset = ft.Animation(1000, "easeOut") 
                    self.shine.offset = ft.Offset(3, 0)
                    self.shine.opacity = 0.8
                    self.shine.update()
                    time.sleep(1.2)
                
                # Cleanup
                self.shine.opacity = 0
                self.shine.offset = ft.Offset(-2, 0)
                self.shine.update()

            threading.Thread(target=loop_anim, daemon=True).start()

        def set_status(self, text, color, icon_name):
            self.is_loading = False 
            self.text_control.value = text
            self.bgcolor = color
            self.icon_control.name = icon_name
            self.disabled = False 
            self.update()



# =================================================================
    # [FIX] 1. LOGIC KÉO THẢ ẢNH (DRAG TO SCROLL)
    # =================================================================
    def on_pan_start(e):
        dt_images_row.is_dragging = True
        dt_images_row.velocity = 0 

    def on_scroll_images(e):
        current = getattr(dt_images_row, "scroll_x", 0)
        new_pos = current - e.delta_x
        if new_pos < 0: new_pos = 0
        
        dt_images_row.scroll_x = new_pos
        dt_images_row.scroll_to(offset=new_pos, duration=0)
        dt_images_row.velocity = e.delta_x

    def on_scroll_end(e):
        dt_images_row.is_dragging = False
        def inertia_loop():
            vel = getattr(dt_images_row, "velocity", 0)
            while abs(vel) > 0.1 and not dt_images_row.is_dragging:
                vel = vel * 0.95 
                current = getattr(dt_images_row, "scroll_x", 0)
                new_pos = current - vel
                if new_pos < 0: 
                    new_pos = 0
                    vel = 0
                dt_images_row.scroll_x = new_pos
                dt_images_row.scroll_to(offset=new_pos, duration=0)
                time.sleep(0.010)
        threading.Thread(target=inertia_loop, daemon=True).start()

    # =================================================================
    # [FIX] 2. LOGIC HÌNH NỀN & CHẾ ĐỘ NGHỈ (IDLE MODE)
    # =================================================================
    
    # =================================================================
    # [FIX] 2. LOGIC HÌNH NỀN (ƯU TIÊN: CONFIG -> DEFAULT -> GRADIENT)
    # =================================================================
    
    # 1. Lấy ảnh từ Cài đặt
    bg_img = APP_CONFIG.get("background")
    
    # 2. Kiểm tra ảnh Cài đặt có tồn tại không?
    if bg_img and not os.path.exists(bg_img):
        print(f"[BG] Ảnh cài đặt không tìm thấy: {bg_img}")
        bg_img = None 
        APP_CONFIG["background"] = None
        save_config() # Xóa config lỗi để lần sau đỡ check lại

    # 3. Nếu không có ảnh cài đặt (hoặc bị lỗi), tìm ảnh MẶC ĐỊNH
    if not bg_img:
        # Đường dẫn: .../Launcher_Data/default_bg.png
        default_bg_path = os.path.join(BASE_DATA_PATH, "default_bg.png")
        
        if os.path.exists(default_bg_path):
            print(f"[BG] Đang dùng ảnh mặc định: {default_bg_path}")
            bg_img = default_bg_path
        else:
            print("[BG] Không tìm thấy cả ảnh mặc định -> Dùng Gradient")

    # 4. Setup Gradient (Chỉ dùng khi KHÔNG CÓ bất kỳ ảnh nào)
    bg_gradient = ft.LinearGradient(colors=["#141E30", "#243B55"]) if not bg_img else None

    # 5. Các lớp phủ (Dim Layer)
    bg_dim_layer = ft.Container(
        expand=True, 
        bgcolor="#66000000", 
        visible=True if bg_img else False, 
        opacity=1, 
        animate_opacity=1000
    )
    bg_content_layer = ft.Container(opacity=1, animate_opacity=500, content=None)

    # 6. Container chính
    bg_container = ft.Container(
        expand=True,
        image=ft.DecorationImage(src=bg_img, fit=ft.ImageFit.COVER) if bg_img else None,
        gradient=bg_gradient, 
        content=ft.Stack([bg_dim_layer, bg_content_layer], expand=True),
        # [FIX] Nếu có ảnh -> Opacity 0 (chờ startup), Nếu Gradient -> 1 luôn (để tránh màn đen)
        opacity=0 if bg_img else 1, 
        animate_opacity=1000
    )

    def pick_bg_result(e):
        if e.files:
            path = e.files[0].path
            APP_CONFIG["background"] = path
            save_config()
            bg_container.image = ft.DecorationImage(src=path, fit=ft.ImageFit.COVER)
            bg_container.gradient = None 
            bg_container.update()
    
    file_picker = ft.FilePicker(on_result=pick_bg_result)
    page.overlay.append(file_picker)

    # B. Chế độ nghỉ (Idle Mode)
    IDLE_TIMEOUT = 300 
    state = {"last_interaction": time.time(), "is_idle": False}
    sleep_overlay = ft.Container(expand=True, bgcolor="transparent", visible=False)

    def go_to_sleep():
        if not state["is_idle"]:
            state["is_idle"] = True
            bg_dim_layer.opacity = 0 
            bg_content_layer.opacity = 0 
            # Ẩn nội dung chính
            if 'body_container' in locals() or 'body_container' in globals():
                body_container.opacity = 0
            # Ẩn sidebar
            sidebar_container.offset = ft.Offset(1.1, 0)
            sidebar_blur_layer.opacity = 0
            sleep_overlay.visible = True
            page.update()

    def wake_up(e=None):
        state["last_interaction"] = time.time()
        if state["is_idle"] or sleep_overlay.visible:
            state["is_idle"] = False
            bg_dim_layer.opacity = 1
            bg_content_layer.opacity = 1
            if 'body_container' in locals() or 'body_container' in globals():
                body_container.opacity = 1
            sleep_overlay.visible = False
            page.update()

    sleep_overlay.on_hover = lambda e: wake_up()
    page.on_scroll = wake_up
    page.on_click = wake_up

    # =================================================================
    # [FIX] 3. KHỞI TẠO BIẾN GIAO DIỆN (UI VARIABLES)
    # =================================================================

    # [FIX] 3. KHỞI TẠO BIẾN GIAO DIỆN (UI VARIABLES)
    dt_img_bg = ft.Image(src="", width=1280, height=720, fit=ft.ImageFit.COVER, opacity=0.4)
    
    # [ĐÃ SỬA] Xóa shadow đi để hết lỗi (ft.Image không hỗ trợ shadow trực tiếp)
    dt_icon_small = ft.Image(src="", width=100, height=100, border_radius=15, fit=ft.ImageFit.COVER)

    dt_name = ft.Text("", size=40, weight="bold", font_family="Segoe UI")
    dt_ver = ft.Text("", size=15, italic=True, color="#AAAAAA")
    dt_desc = ft.Text("", size=14, no_wrap=False, max_lines=3, color="white")
    dt_req = ft.Text("Đang tải cấu hình...", size=12, color="#CCCCCC", font_family="Consolas")
    
    dt_images_row = ft.Row(scroll=ft.ScrollMode.HIDDEN, wrap=False, spacing=10)
    dt_images_row.scroll_x = 0
    dt_images_row.velocity = 0
    dt_images_row.is_dragging = False

    dt_viet_btn = ft.ElevatedButton("Tải Việt Hóa", icon=ft.icons.LANGUAGE, bgcolor="green", color="white", visible=False)
    dt_update_btn = ShineButton(text="Kiểm tra Update", width=200)

    # Logic Nút Tải & Driver
    driver_text = ft.Text("LẤY LINK DRIVER", size=13, weight="bold", color="white", opacity=0, animate_opacity=200)
    driver_arrow = ft.Icon(ft.icons.KEYBOARD_ARROW_LEFT, color="white", size=20)
    current_driver_link = [""] 

    def on_driver_action_click(e):
        e.control.stop_propagation = True 
        if current_driver_link[0]:
            webbrowser.open(current_driver_link[0])
            show_push_notification("Đang mở trình duyệt...", "info")
        else:
            show_push_notification("Lỗi: Không tìm thấy Link!", "error")

    def toggle_driver_mode(e):
        if e: e.control.stop_propagation = True 
        is_closed = driver_overlay.width < 100 
        if is_closed:
            driver_text_container.visible = True
            driver_text_container.update()
            driver_overlay.width = 300
            driver_overlay.bgcolor = "#2E7D32" 
            driver_overlay.border_radius = 8   
            driver_arrow_container.right = 260 
            driver_arrow.name = ft.icons.KEYBOARD_ARROW_RIGHT 
            threading.Thread(target=lambda: (time.sleep(0.2), setattr(driver_text, 'opacity', 1) or driver_text.update()), daemon=True).start()
        else:
            driver_text.opacity = 0 
            driver_overlay.width = 40
            driver_overlay.bgcolor = "#CC8400" 
            driver_overlay.border_radius = ft.border_radius.only(top_right=8, bottom_right=8)
            driver_arrow_container.right = 0 
            driver_arrow.name = ft.icons.KEYBOARD_ARROW_LEFT
            def hide_text():
                time.sleep(0.4) 
                if driver_overlay.width < 100: 
                    driver_text_container.visible = False
                    driver_text_container.update()
            threading.Thread(target=hide_text, daemon=True).start()
        driver_overlay.update()
        driver_arrow.update()
        driver_arrow_container.update()
        driver_text.update()

    btn_download_base = ft.Container(
        content=ft.Row([ft.Icon(ft.icons.DOWNLOAD, color="white"), ft.Text("TẢI NGAY", color="white", weight="bold")], alignment=ft.MainAxisAlignment.CENTER),
        bgcolor="orange", height=50, width=300, border_radius=8, on_click=None 
    )

    driver_arrow_container = ft.Container(
        content=driver_arrow, width=40, height=40, alignment=ft.alignment.center, bgcolor=None, 
        right=0, top=5, animate_position=ft.Animation(400, "easeOutQuart"),
        on_click=toggle_driver_mode, tooltip="Quay lại / Đóng"
    )
    
    driver_text_container = ft.Container(
        content=driver_text, alignment=ft.alignment.center, padding=ft.padding.only(left=30),
        on_click=on_driver_action_click, tooltip="Nhấn để lấy Link", visible=False 
    )

    driver_overlay = ft.Container(
        width=40, height=50, bgcolor="#CC8400", 
        border_radius=ft.border_radius.only(top_right=8, bottom_right=8),
        right=0, animate=ft.Animation(400, "easeOutQuart"), 
        content=ft.Stack([driver_text_container, driver_arrow_container]),
        on_click=toggle_driver_mode, clip_behavior=ft.ClipBehavior.HARD_EDGE
    )

    dt_download_stack = ft.Stack(controls=[btn_download_base, driver_overlay], width=300, height=50)


























    # =================================================================
    # HÀM HIỂN THỊ CHI TIẾT GAME (UPDATE LOGIC LOADING ẢNH)
    # =================================================================
    def show_game_detail_dialog(game, card_ref):
        # 1. Reset UI cơ bản
        dt_name.value = game['name']
        dt_icon_small.src = game['icon'] # Cập nhật ảnh icon nhỏ
        dt_ver.value = f"Phiên bản hiện tại: {game['version']}"
        dt_desc.value = game.get('subtitle', 'Đang tải mô tả...')
        dt_img_bg.src = game['icon'] 
        dt_req.value = "Đang kết nối LinkNeverDie..."
        
        # 2. [FIX] Tạo Skeleton Loading (Ảnh giả) ngay lập tức
        # Để người dùng biết là đang tải, không bị trống trơn
        dt_images_row.controls.clear()
        for _ in range(5):
            loading_card = ft.Container(
                width=250, height=350, 
                bgcolor="#20FFFFFF", border_radius=15,
                alignment=ft.alignment.center,
                content=ft.Column([
                    ft.ProgressRing(width=30, height=30, stroke_width=3, color="orange"),
                    ft.Text("Đang tải ảnh...", size=10, color="#888888")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
            )
            dt_images_row.controls.append(loading_card)
        dt_images_row.scroll_x = 0
        
        # 3. Hàm xử lý logic chạy ngầm
        def run_check_process(e=None):
            dt_update_btn.start_loading()
            
            def worker():
                time.sleep(0.5) # Delay nhẹ
                
                # Cào dữ liệu
                data = fetch_full_details(game['lnd_url'])
                
                # --- XỬ LÝ KẾT QUẢ ---
                if not data:
                    dt_update_btn.set_status("Lỗi K.Nối", "#555555", ft.icons.CLOUD_OFF)
                    # Xóa skeleton nếu lỗi
                    dt_images_row.controls.clear()
                    dt_images_row.controls.append(ft.Text("Không tải được ảnh :(", color="red"))
                    dt_images_row.update()
                    return

                # A. Update Cấu hình
                if data.get('requirements'):
                    game['requirements'] = data['requirements']
                    dt_req.value = data['requirements']
                    dt_req.update()
                
                # B. [FIX] Update Album ảnh (Nhân 4 & Cuộn giữa)
                if data.get('album'):
                    album = data['album']
                    game['album_images'] = album 
                    
                    # [QUAN TRỌNG] Nhân bản để tạo cảm giác vô tận
                    infinite_album = album * 4 
                    
                    dt_images_row.controls.clear()
                    
                    for img_src in infinite_album:
                        img_card = ft.Container(
                            content=ft.Image(src=img_src, height=350, border_radius=10, fit=ft.ImageFit.FIT_HEIGHT),
                            on_click=lambda e, s=img_src: setattr(dt_img_bg, 'src', s) or dt_img_bg.update(),
                            # Hiệu ứng hover nhẹ
                            animate_scale=ft.Animation(200, "easeOut"),
                            on_hover=lambda e: (setattr(e.control, 'scale', 1.02 if e.data=='true' else 1.0) or e.control.update())
                        )
                        dt_images_row.controls.append(img_card)
                    
                    # Cập nhật hình nền mờ bằng ảnh đầu tiên lấy được
                    if len(album) > 0:
                        dt_img_bg.src = album[0]
                        dt_img_bg.opacity = 0.6 
                        dt_img_bg.update()
                    
                    # [FIX] Tính toán vị trí giữa để cuộn tới
                    # Giả sử mỗi ảnh rộng trung bình 250px + 10px padding
                    mid_index = len(infinite_album) // 2
                    scroll_pos = mid_index * 260 
                    
                    dt_images_row.scroll_x = scroll_pos
                    dt_images_row.update()
                    # Cuộn nhẹ 1 chút để tạo hiệu ứng
                    dt_images_row.scroll_to(offset=scroll_pos, duration=0)

                # C. Check Version
                web = data.get('web_version', 'Unknown')
                local = game['version']
                
                txt, col, ico = "Không xác định", "#555555", ft.icons.HELP_OUTLINE
                
                if web and web not in ['Unknown', 'Error', 'N/A']:
                    if not is_version_match_smart(web, local):
                        txt, col, ico = f"CÓ BẢN MỚI: {web}", "#D32F2F", ft.icons.CLOUD_DOWNLOAD
                    else:
                        txt, col, ico = "ĐÃ CẬP NHẬT", "#2E7D32", ft.icons.CHECK_CIRCLE
                else:
                    txt, col, ico = "Web không ghi Ver", "#FF8F00", ft.icons.WARNING_AMBER
                
                game['status'] = txt
                save_cache()
                if card_ref: 
                    try: card_ref.refresh_ui()
                    except: pass
                
                dt_update_btn.set_status(txt, col, ico)

            threading.Thread(target=worker, daemon=True).start()

        dt_update_btn.on_click = run_check_process
        
        # Logic nút tải & Driver
        driver_overlay.visible = False
        if game['download_link']:
            btn_download_base.bgcolor = "orange"
            btn_download_base.on_click = lambda e: (close_detail(None), threading.Thread(target=lambda: trigger_download_process(game), daemon=True).start())
            try: btn_download_base.content.controls[1].value = "TẢI NGAY"
            except: pass
            current_driver_link[0] = game['download_link']
            driver_overlay.visible = True
        else:
            btn_download_base.bgcolor = "grey"
            btn_download_base.on_click = None
            try: btn_download_base.content.controls[1].value = "CHƯA CÓ LINK"
            except: pass

        # Logic Việt Hóa
        dt_viet_btn.visible = bool(game.get('viet_link'))
        if dt_viet_btn.visible:
            dt_viet_btn.on_click = lambda e: webbrowser.open(game['viet_link'])

        # Hiển thị
        trigger_zone.visible = False
        sidebar_container.offset = ft.Offset(1.1, 0)
        dl_trigger_zone.visible = False
        game_detail_overlay.offset = ft.Offset(0, 0)
        page.update()
        
        run_check_process()
        
        # Logic nút tải
        driver_overlay.visible = False
        if game['download_link']:
            btn_download_base.bgcolor = "orange"
            btn_download_base.on_click = lambda e: (close_detail(None), threading.Thread(target=lambda: trigger_download_process(game), daemon=True).start())
            try: btn_download_base.content.controls[1].value = "TẢI NGAY"
            except: pass
            current_driver_link[0] = game['download_link']
            driver_overlay.visible = True
        else:
            btn_download_base.bgcolor = "grey"
            btn_download_base.on_click = None
            try: btn_download_base.content.controls[1].value = "CHƯA CÓ LINK"
            except: pass

        # Logic Việt Hóa
        dt_viet_btn.visible = bool(game.get('viet_link'))
        if dt_viet_btn.visible:
            dt_viet_btn.on_click = lambda e: webbrowser.open(game['viet_link'])

        # Hiển thị Overlay
        trigger_zone.visible = False
        sidebar_container.offset = ft.Offset(1.1, 0)
        dl_trigger_zone.visible = False
        game_detail_overlay.offset = ft.Offset(0, 0)
        page.update()
        
        run_check_process()

    def close_detail(e):
        game_detail_overlay.offset = ft.Offset(0, 1) 
        dl_trigger_zone.visible = True
        dl_trigger_zone.update()
        trigger_zone.visible = True
        trigger_zone.update()
        page.update()


















        
    game_detail_overlay = ft.Container(
        width=1280, height=720,
        bgcolor="#141E30",
        offset=ft.Offset(0, 1), # Mặc định ẩn dưới đáy
        animate_offset=ft.Animation(400, "easeOutCubic"),
        padding=0,
        content=ft.Stack([
            # 1. Ảnh nền Full
            dt_img_bg,
            
            # 2. Lớp phủ đen mờ
            ft.Container(
                gradient=ft.LinearGradient(
                    colors=["transparent", "#141E30"],
                    begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                    stops=[0.0, 0.9]
                ), expand=True
            ),
            
            # 3. Nội dung chính (Cột bên trái)
            ft.Container(
                padding=50,
                content=ft.Column([
                    ft.Container(expand=True), # Đẩy nội dung xuống đáy
                    
                    # --- [HEADER MỚI] ICON + TÊN GAME + VERSION ---
                    ft.Row([
                        dt_icon_small, # Ảnh nhỏ đã quay lại!
                        ft.Column([
                            dt_name,
                            dt_ver,
                        ], spacing=0, alignment=ft.MainAxisAlignment.CENTER)
                    ], spacing=20),
                    
                    ft.Container(height=20), # Khoảng cách

                    # --- ALBUM ẢNH (GIỮ NGUYÊN CODE KÉO THẢ) ---
                    ft.Text("HÌNH ẢNH MÔ TẢ:", size=16, weight="bold", color="orange"),
                    ft.Container(
                        height=350, # Giảm chiều cao chút cho cân đối
                        content=ft.GestureDetector(
                            on_pan_start=on_pan_start,      
                            on_pan_update=on_scroll_images, 
                            on_pan_end=on_scroll_end,       
                            content=ft.Container(
                                content=dt_images_row,
                                padding=0, 
                                alignment=ft.alignment.center_left,
                            )
                        )
                    ),

                    ft.Container(height=10),
                    dt_desc,

                    ft.Divider(color="grey"),

                    # --- CẤU HÌNH ---
                    ft.Text("CẤU HÌNH YÊU CẦU:", size=12, weight="bold", color="orange"),
                    ft.Container(
                        height=100,
                        padding=10,
                        border=ft.border.all(1, "#444444"),
                        border_radius=5,
                        content=ft.Column([dt_req], scroll=ft.ScrollMode.AUTO)
                    ),

                    ft.Container(height=20),
                    ft.Row([dt_download_stack, dt_viet_btn, dt_update_btn]),
                    
                ], scroll=ft.ScrollMode.HIDDEN) # Cho phép lăn chuột toàn bộ cột
            ),
            
            # 4. Nút Đóng (Góc trên phải)
            ft.Container(
                top=20, right=20,
                content=ft.IconButton(ft.icons.CLOSE, icon_size=30, icon_color="white", on_click=close_detail)
            )
        ])
    )














# [THÊM MỚI] Container chứa toàn bộ nội dung chính (Header + Game)
    body_container = ft.Container(
    content=ft.Column([
        header,
        ft.Container(
            content=grid, 
            expand=True,
            padding=ft.padding.only(left=20, right=20, bottom=20)
        )
    ], spacing=10),
    expand=True,
    # [THÊM 2 DÒNG NÀY]
    opacity=1, # Mặc định là hiện
    animate_opacity=ft.Animation(1000, "easeOut"), # Hiệu ứng mờ dần trong 1 giây
)
    # --- MAIN LAYOUT ---
    main_layout = ft.Container(
        width=1280, height=720,
        clip_behavior=ft.ClipBehavior.HARD_EDGE, 
        
        # [FIX] Bỏ MouseRegion, chỉ giữ lại nội dung Stack bên trong
        content=ft.Stack([
            bg_container,       
            body_container,     
            game_detail_overlay,    
            sidebar_blur_layer,  
            trigger_zone,         
            sidebar_container,     
            blur_overlay,         
            settings_drawer,





            dl_trigger_zone,   # <--- Dùng biến mới này (Vùng cảm ứng to)
            dl_overlay_blur,
            downloads_drawer,
            dl_anim_box,
            coord_container,
            notification_stack,
            sleep_overlay       
        ], expand=True),
        
        opacity=0, 
        animate_opacity=500
    )

    page.add(main_layout)

    # --- 9. LOGIC KHỞI ĐỘNG (FIX LỖI KHÔNG CẬP NHẬT DATA) ---
    async def run_startup():
        global RAW_GAME_DATA
        
        # 1. Chạy hiệu ứng Loading Splash
        await splash.animate_loading()
        
        # 2. Hiện giao diện chính
        bg_container.opacity = 1
        main_layout.opacity = 1
        page.update()

        # 3. Fix kích thước (Chống màn hình đen)
        # (Giữ nguyên đoạn nhích nhẹ 1px cũ của bạn ở đây...)
        current_w = page.window.width
        current_h = page.window.height
        page.window.width = current_w + 1
        page.window.height = current_h + 1
        page.update()
        await asyncio.sleep(0.05)
        page.window.width = 1280
        page.window.height = 720
        page.update()
        
        # --- [FIX QUAN TRỌNG] TẢI DATA MỚI NHẤT TỪ GITHUB ---
        print("[STARTUP] Bắt đầu đồng bộ dữ liệu...")
        splash.msg_txt.value = "Đang cập nhật danh sách game..."
        splash.page.update()

        # Gọi hàm tải trực tiếp (Bắt buộc tải lại để lấy list mới)
        success = await asyncio.to_thread(download_data_direct)
        
        if success:
            print("[STARTUP] Đã tải xong raw_games.txt mới nhất.")
        else:
            print("[STARTUP] Tải thất bại, dùng dữ liệu cũ.")

        # --- NẠP DỮ LIỆU VÀO RAM ---
        if os.path.exists(LOCAL_DATA_PATH):
            try:
                with open(LOCAL_DATA_PATH, "r", encoding="utf-8") as f:
                    content = f.read()
                    RAW_GAME_DATA = ast.literal_eval(content)
                
                print(f"[STARTUP] Đã nạp {len(RAW_GAME_DATA)} game vào hệ thống.")
                
                # Cập nhật giao diện Grid ngay lập tức
                refresh_data_and_grid() 
                
            except Exception as e: 
                print(f"[STARTUP] Lỗi đọc file data: {e}")
        
        # --- Kích hoạt luồng tải ảnh ---
        # (Sau khi đã có danh sách game đầy đủ)
        threading.Thread(target=bg_download_icons, daemon=True).start()
        

        # ---------------------------------------------------

        # 4. [SAU KHI UI ỔN ĐỊNH] MỚI BẮT ĐẦU CHECK UPDATE
        # Lúc này màn hình đã đứng im, animation sẽ trượt ra cực mượt
        try:
            # Hàm con check mạng
            def fetch_update_data_sync():
                timestamp = int(time.time())
                RAW_URL = f"https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/version.json?t={timestamp}"
                no_cache_headers = {
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
                resp = requests.get(RAW_URL, headers=no_cache_headers, timeout=5)
                return resp.json()

            # Chạy check ngầm
            data = await asyncio.to_thread(fetch_update_data_sync)
            
            server_ver = data["latest_version"].strip()
            local_ver = CURRENT_VERSION.strip()
            
            print(f"Auto Check (Async): Local={local_ver} | Server={server_ver}")

            # Hiện thông báo nếu có bản mới
            if server_ver != local_ver:
                download_url = data.get("download_url", "")
                if download_url:
                    # Đợi thêm xíu cho người dùng nhìn thấy giao diện đã
                    await asyncio.sleep(0.5) 
                    
                    show_push_notification(
                        f"Đã có phiên bản mới v{server_ver}", 
                        type="update", 
                        duration=None, # Giữ nguyên để người dùng kịp bấm
                        key="update_alert",
                        on_click_action=lambda: start_self_update(download_url, server_ver)
                    )
        except Exception as e: 
            print(f"Lỗi Auto Check: {e}")
            pass

        # 4. [FIX TỰ DI CHUYỂN & FIX MÀN ĐEN]
        # Chỉ thay đổi kích thước nhẹ để ép vẽ lại, TUYỆT ĐỐI KHÔNG dùng .center()
        current_w = page.window.width
        current_h = page.window.height
        
        # Nhích nhẹ 1 pixel
        page.window.width = current_w + 1
        page.window.height = current_h + 1
        page.update()
        
        await asyncio.sleep(0.05) # Nghỉ cực ngắn
        
        # Trả về kích thước cũ (1280x720)
        # [QUAN TRỌNG] Không đụng vào vị trí (top/left) của cửa sổ
        page.window.width = 1280
        page.window.height = 720
        page.update()
        
        await asyncio.sleep(0.1)
        
        page.window.width = 1280
        page.window.height = 720
        page.update()
        
        await asyncio.sleep(0.1) # Nghỉ một nhịp
        
        # Trả về kích thước chuẩn
        page.window.width = 1280
        page.window.height = 720
        page.update()
        # ---------------------------------------------------

    # Khởi tạo Splash (Chỉ truyền page và hàm tắt always_on_top)
    splash = SplashLoader(page, lambda: setattr(page.window, 'always_on_top', False))
    
    # Bắt đầu quy trình khởi động
    page.run_task(run_startup)

    # --- WORKER: Xử lý 1 game ---
    def process_single_icon(g):
        has_new = False
        try:
            slug = clean_name_for_slug(g['name'])
            # [QUAN TRỌNG] Chỉ tìm file .jpg
            local_path = os.path.join(ICON_FOLDER, f"{slug}.jpg")
            
            # Logic kiểm tra file
            # 1. Chưa có file
            # 2. Hoặc file bị hỏng (0KB)
            should_download = not os.path.exists(local_path) or os.path.getsize(local_path) < 1024
            
            has_link = g.get('lnd_url') and len(str(g.get('lnd_url'))) > 10

            if should_download and has_link:
                # print(f"⬇️ [ĐANG TẢI] {g['name']}...") # Bỏ comment nếu muốn xem chi tiết
                
                img_url = get_lnd_image(g['lnd_url'])
                if img_url and download_icon(img_url, local_path):
                    g['icon'] = local_path
                    has_new = True
                    
                    # Update UI ngay lập tức (Thread Safe)
                    try:
                        for card in grid.controls:
                            if card.game['name'] == g['name']:
                                card.img_control.src = local_path
                                card.img_control.update()
                                break
                    except: pass
            else:
                # Nếu đã có ảnh, đảm bảo đường dẫn trong RAM đúng là file .jpg đó
                if os.path.exists(local_path):
                     g['icon'] = local_path
                     # Cập nhật ngược lại vào UI nếu đang hiển thị sai
                     try:
                        for card in grid.controls:
                            if card.game['name'] == g['name'] and card.img_control.src != local_path:
                                card.img_control.src = local_path
                                card.img_control.update()
                     except: pass

        except Exception: pass
        return has_new

    # --- TURBO V3: TỐC ĐỘ ÁNH SÁNG (NO DELAY) ---
    def bg_download_icons():
        # [TỐI ƯU 1] Bỏ time.sleep(2) -> Chạy ngay lập tức
        print(f"[FLASH] Bắt đầu quét {len(GAME_LIST)} game...")
        
        # [TỐI ƯU 2] Quét thư mục 1 lần duy nhất (Nhanh gấp 100 lần check từng file)
        try:
            existing_files = set(os.listdir(ICON_FOLDER)) # Tạo danh sách các file đang có
        except:
            existing_files = set()

        missing_games = []
        changed = False

        # --- GIAI ĐOẠN 1: CHECK NHANH (Main Thread) ---
        for g in GAME_LIST:
            slug = clean_name_for_slug(g['name'])
            target_filename = f"{slug}.jpg"
            local_path = os.path.join(ICON_FOLDER, target_filename)

            # Check xem file có trong danh sách đã quét không?
            if target_filename in existing_files:
                # Nếu có file -> Check nhanh dung lượng (tránh file rác)
                # Thao tác này cực nhanh, không đáng kể
                if os.path.getsize(local_path) > 1024:
                    # File ngon -> Update RAM và UI ngay lập tức
                    if g.get('icon') != local_path:
                        g['icon'] = local_path
                        # Update UI
                        try:
                            for card in grid.controls:
                                if card.game['name'] == g['name']:
                                    # Chỉ update nếu src khác nhau để đỡ giật
                                    if card.img_control.src != local_path:
                                        card.img_control.src = local_path
                                        card.img_control.update()
                                    break
                        except: pass
                    continue # Bỏ qua, không cần tải
            
            # Nếu chạy xuống đây nghĩa là thiếu file hoặc file lỗi
            missing_games.append(g)

        # --- GIAI ĐOẠN 2: CHỈ TẢI CÁI THIẾU (Đa luồng) ---
        if not missing_games:
            print("[FLASH] ✅ Full ảnh. Không tốn 1 giọt RAM nào để tải.")
            return

        print(f"[FLASH] ⚡ Phát hiện {len(missing_games)} game thiếu ảnh. Kích hoạt Đa luồng...")
        
        # Chỉ khởi động luồng cho những game cần thiết
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Tận dụng lại hàm process_single_icon cũ (Worker)
            results = executor.map(process_single_icon, missing_games)
            for res in results:
                if res: changed = True
        
        if changed:
            print("[FLASH] Đã cập nhật xong cache.")
            save_cache()



    def idle_checker():
        while True:
            if time.time() - state["last_interaction"] > IDLE_TIMEOUT:
                go_to_sleep()
            time.sleep(1)

    threading.Thread(target=idle_checker, daemon=True).start()
    threading.Thread(target=bg_download_icons, daemon=True).start()

    if APP_CONFIG.get("auto_update_games", False):
        # [cite_start]Lúc này đang ở trong hàm main nên nó mới nhìn thấy process_game_updates_thread [cite: 99]
        threading.Thread(target=process_game_updates_thread, daemon=True).start()




















if __name__ == "__main__":

    # --- [MẸO FIX ICON TASKBAR KHI CHẠY VS CODE] ---
    # Đặt ID ngay khi Process Python vừa khởi động, trước cả khi Flet chạy
    myappid = 'conist.link.launcher.v2.dev' 
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except: pass
    # -----------------------------------------------

    # 1. Tạo một cái tên khóa độc nhất vô nhị
    mutex_id = "Global\\Conist_Launcher_v2_Unique_Lock"
    
    # 2. Thử tạo khóa
    mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_id)
    
    # 3. Kiểm tra xem khóa đã tồn tại chưa
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:
        sys.exit(0)
    
    # 4. Nếu chưa chạy -> Chạy App bình thường
    ft.app(target=main, assets_dir=BASE_DATA_PATH)
