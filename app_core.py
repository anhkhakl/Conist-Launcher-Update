# [COPY VÀO DÒNG 1 CỦA app_core.py]
import flet as ft
import sys
import os
import subprocess
import requests
import json
import re
import threading
import time
import webbrowser
import winreg as reg
import winsound
import random
import shutil
import asyncio
import ctypes
import concurrent.futures
import math     # <--- Fix lỗi math
import ast      # <--- Fix lỗi ast
import zipfile  # <--- Fix lỗi zipfile
from bs4 import BeautifulSoup
from PIL import Image

# Thử import pystray (Tray Icon)
try:
    import pystray
    from pystray import MenuItem as item
    HAS_TRAY_LIB = True
except ImportError:
    HAS_TRAY_LIB = False
    print("Warning: Chưa cài pystray -> Tắt tính năng chạy ngầm.")


# --- [FIX MEI ERROR - SAFE MODE] DỌN DẸP THƯ MỤC TẠM (CHẠY NGẦM) ---
def cleanup_mei_folders_safe():
    def worker():
        try:
            # 1. Chỉ chạy khi là file EXE (Để không ảnh hưởng lúc Dev trên VS Code)
            if not getattr(sys, 'frozen', False): 
                return

            base_temp = os.environ.get('TEMP')
            if not base_temp: return
            
            # Lấy tên thư mục tạm của phiên bản ĐANG CHẠY (để không lỡ tay xóa nhầm)
            current_mei = os.path.basename(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else ""
            
            # Ngủ 1 giây để hệ thống ổn định trước khi quét rác
            time.sleep(1)

            # Quét và xóa các thư mục _MEI cũ
            if os.path.exists(base_temp):
                for item in os.listdir(base_temp):
                    # Chỉ xóa thư mục _MEI và KHÁC thư mục hiện tại
                    if item.startswith("_MEI") and item != current_mei:
                        full_path = os.path.join(base_temp, item)
                        try:
                            # Xóa mạnh tay (ignore_errors=True để không crash nếu file đang bị khóa)
                            shutil.rmtree(full_path, ignore_errors=True)
                        except: pass
        except: pass

    # Chạy trên luồng phụ để không bao giờ làm treo App lúc khởi động
    threading.Thread(target=worker, daemon=True).start()

# Gọi hàm ngay lập tức
cleanup_mei_folders_safe()


# --- CẤU HÌNH TURBO DOWNLOAD ---
# Tạo một Session dùng chung để không phải kết nối lại nhiều lần
http_session = requests.Session()
http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Connection': 'keep-alive', # Giữ kết nối
    'Accept-Encoding': 'gzip, deflate', # Nén dữ liệu cho nhẹ
})

# --- [ADD] HÀM LẤY LINK STEAM TỪ LND ---
def get_real_steam_url(lnd_soup):
    """Tìm link Steam chính chủ trong trang LND"""
    try:
        # Tìm thẻ <a> có href chứa store.steampowered.com
        steam_link = lnd_soup.find('a', href=re.compile(r'store\.steampowered\.com/app/', re.I))
        if steam_link:
            return steam_link['href']
    except: pass
    return None









def parse_mixed_game_data(file_content):
    """
    Parser 'Huyền Thoại': Dùng y chang logic của Launcher cũ (ast.literal_eval).
    Đọc nguyên file 1 lần -> Tự động bỏ qua # [ID] -> Hiểu Python List.
    """
    try:
        # --- CÁCH 1: CÁCH CỦA LAUNCHER CŨ (CHUẨN NHẤT) ---
        # Hàm này tự động coi dấu # là comment và bỏ qua, nên # [1] không gây lỗi.
        import ast
        data = ast.literal_eval(file_content)
        if isinstance(data, list):
            return data
            
    except Exception:
        # --- CÁCH 2: BẢO HIỂM (FIX LỖI NULL/TRUE/FALSE) ---
        # Launcher cũ sẽ chết nếu gặp 'null', ta thêm bước này để cứu.
        try:
            fixed = file_content.replace('null', 'None').replace('true', 'True').replace('false', 'False')
            data = ast.literal_eval(fixed)
            if isinstance(data, list):
                return data
        except:
            pass # Nếu nát quá thì chịu
            
    return []











def fetch_steam_data(steam_url):
    """Cào dữ liệu từ Steam (Logo, Ảnh, Cấu hình, Online Status)"""
    if not steam_url: return None
    try:
        # Thêm tham số l=vietnamese để ưu tiên lấy tiếng Việt cho dễ khớp với keyword của bạn
        if "?" in steam_url:
            steam_url += "&l=vietnamese"
        else:
            steam_url += "?l=vietnamese"

        cookies = {'birthtime': '0', 'lastagecheckage': '1-January-1990'}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        res = requests.get(steam_url, headers=headers, cookies=cookies, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        data = {}

        # 1. LẤY LOGO
        header_img = soup.find('img', class_='game_header_image_full')
        if header_img:
            data['icon'] = header_img.get('src')

        # 2. LẤY ẢNH PREVIEW
        images = []
        carousel = soup.find('div', class_='gamehighlight_desktopcarousel')
        if carousel and carousel.get('data-props'):
            import html 
            try:
                props_str = html.unescape(carousel['data-props'])
                props_json = json.loads(props_str)
                for ss in props_json.get('screenshots', []):
                    img_url = ss.get('full') or ss.get('path_full')
                    if img_url: images.append(img_url)
            except: pass
        if images: data['album'] = images

        # 3. [UPDATE THEO YÊU CẦU] CHECK ONLINE / OFFLINE
        # Logic: Quét cả Nhãn người dùng (Glance Tags) VÀ Tính năng Dev (Category)
        
        mp_status = None 
        
        # Từ khóa Online (Việt + Anh + Pháp/Đức cơ bản nếu có)
        online_keywords = [
            'multi-player', 'multiplayer', 'online', 'co-op', 'mmo', 'pvp', 
            'chơi nhiều người', 'phối hợp trên mạng', 'trực tuyến', 'nhiều người', 
            'giao chiến', 'mạng cục bộ', 'local multiplayer'
        ]
        
        # Từ khóa Offline
        offline_keywords = [
            'single-player', 'singleplayer', 'chơi đơn', 'một người', 'single player'
        ]

        found_online = False
        found_offline = False

        # --- CÁCH 1: QUÉT NHÃN NGƯỜI DÙNG (glance_tags) - Ưu tiên cái này ---
        # Đây là phần bạn vừa yêu cầu thêm vào
        glance_tags = soup.find('div', class_='glance_tags')
        if glance_tags:
            tags = glance_tags.find_all('a', class_='app_tag')
            for tag in tags:
                txt = tag.get_text(strip=True).lower()
                # Debug: print(f"Found Tag: {txt}")
                if any(k in txt for k in online_keywords): found_online = True
                if any(k in txt for k in offline_keywords): found_offline = True

        # --- CÁCH 2: QUÉT TÍNH NĂNG DEV (category_block) - Code cũ dự phòng ---
        # Nếu Cách 1 chưa tìm ra Online, ta quét tiếp cái này cho chắc
        if not found_online:
            features_div = soup.find('div', id='category_block')
            if features_div:
                labels = features_div.find_all('div', class_='label')
                for lbl in labels:
                    txt = lbl.get_text(strip=True).lower()
                    if any(k in txt for k in online_keywords): found_online = True
                    if any(k in txt for k in offline_keywords): found_offline = True

        # --- QUYẾT ĐỊNH ---
        # Ưu tiên: Nếu có dấu hiệu Online -> Là Online (Vì nhiều game Chơi đơn vẫn có chế độ Online)
        if found_online:
            mp_status = "Online"
        elif found_offline:
            mp_status = "Offline"
        
        data['mp_status'] = mp_status

        # 4. LẤY CẤU HÌNH
        req_str = ""
        sys_req = soup.find('div', class_='game_area_sys_req_full')
        if not sys_req:
            sys_req = soup.find('div', {'data-os': 'win'})
        
        if sys_req:
            text = sys_req.get_text(separator="\n").strip()
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            req_str = "\n".join(lines)
        if req_str: data['requirements'] = req_str

        return data
    except Exception as e:
        print(f"[STEAM] Lỗi fetch: {e}")
        return None
    

















    # --- HÀM TỔNG HỢP: HYBRID ENGINE (STEAM + LND) ---
# --- HÀM TỔNG HỢP: HYBRID ENGINE (STEAM + LND) ---
def fetch_full_details(lnd_url):
    if not lnd_url: return None
    
    final_data = {
        'web_version': 'Unknown',
        'icon': None, # [MỚI] Thêm trường icon
        'album': [],
        'requirements': 'Đang cập nhật...',
        'mp_status': 'Offline'
    }

    try:
        # --- GIAI ĐOẠN 1: KẾT NỐI LND ---
        headers = {'User-Agent': 'Mozilla/5.0'}
        res_lnd = requests.get(lnd_url, headers=headers, timeout=8)
        soup_lnd = BeautifulSoup(res_lnd.text, 'html.parser')

        # 1. Luôn lấy Version từ LND
        ver_p = soup_lnd.find('p', class_='data-label', string=re.compile(r'Phiên bản', re.I))
        if ver_p:
            ver_info = ver_p.find_next_sibling('p', class_='info')
            if ver_info: final_data['web_version'] = ver_info.get_text(strip=True)
        else:
            title = soup_lnd.title.string if soup_lnd.title else ""
            match = re.search(r'(?:v|ver|build|update)\.?\s*(\d+(?:\.\d+)*)', title, re.I)
            if match: final_data['web_version'] = match.group(1)

        # --- GIAI ĐOẠN 2: THỬ SANG STEAM ---
        steam_url = get_real_steam_url(soup_lnd)
        steam_data = None
        
        if steam_url:
            # print(f"[HYBRID] Tìm thấy Steam: {steam_url}")
            steam_data = fetch_steam_data(steam_url)
        
        # Nếu lấy được dữ liệu Steam -> Ưu tiên dùng
        if steam_data:
            if steam_data.get('icon'): final_data['icon'] = steam_data['icon'] # [QUAN TRỌNG] Lấy Logo Steam
            if steam_data.get('album'): final_data['album'] = steam_data['album']
            if steam_data.get('requirements'): final_data['requirements'] = steam_data['requirements']
            if steam_data.get('mp_status'): final_data['mp_status'] = steam_data['mp_status']
        
        # --- GIAI ĐOẠN 3: DỰ PHÒNG (FALLBACK VỀ LND) ---
        
        # A. Dự phòng LOGO (Nếu Steam không có)
        if not final_data['icon']:
            img = soup_lnd.find('img', id='wallpaper_img')
            if img:
                src = img.get('src')
                final_data['icon'] = "https://linkneverdie.net" + src if src.startswith("/") else src

        # B. Dự phòng ALBUM
        if not final_data['album']:
            images = []
            screenshot_div = soup_lnd.find('div', id='screenshots_div')
            if screenshot_div:
                target_imgs = screenshot_div.find_all('img')
                for img in target_imgs:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        if src.startswith("/"): src = "https://linkneverdie.net" + src
                        if src not in images: images.append(src)
            final_data['album'] = images[:10]

        # C. Dự phòng Cấu hình
        if final_data['requirements'] == 'Đang cập nhật...':
            req_str = ""
            cols = [('game_area_sys_req_leftCol', 'TỐI THIỂU'), ('game_area_sys_req_rightCol', 'KHUYẾN NGHỊ')]
            for cls, title in cols:
                col = soup_lnd.find('div', class_=cls)
                if col:
                    req_str += f"\n--- {title} ---\n"
                    for li in col.find_all('li'):
                        req_str += li.get_text(strip=True) + "\n"
            if req_str: final_data['requirements'] = req_str.strip()

        # D. Dự phòng Online/Offline
        if not steam_data: 
            final_data['mp_status'] = "Online"
            try:
                mp_label = soup_lnd.find('p', class_='data-label', string=re.compile(r'Multiplayer', re.I))
                if mp_label:
                    info_p = mp_label.find_next_sibling('p', class_='info')
                    if info_p:
                        text = info_p.get_text(strip=True).lower()
                        if "không có" in text or "không c" in text:
                            final_data['mp_status'] = "Offline"
            except: pass

        return final_data

    except Exception as e:
        print(f"[HYBRID] Lỗi nghiêm trọng: {e}")
        return None










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
































def kill_zombie_overlays():
    """Diệt sạch các Overlay cũ còn sót lại để tránh trùng lặp"""
    try:
        # Lệnh taskkill của Windows để tắt toàn bộ tiến trình tên là ConistOverlayHelper.exe
        # subprocess.call("taskkill /F /IM ConistOverlayHelper.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[SYSTEM] Đã dọn dẹp các Overlay cũ. (DISABLED)")
    except: pass








# Tên thư mục dữ liệu
DATA_DIR_NAME = "Launcher_Data"

# Đường dẫn tài nguyên (Trỏ thẳng vào thư mục đã được Vỏ giải nén)
BASE_DATA_PATH = os.path.join(get_base_path(), DATA_DIR_NAME)


# ==========================================
# 2. CẤU HÌNH & BIẾN TOÀN CỤC (DÙNG SAU KHI ĐÃ CÓ HÀM)
# ==========================================
# [CHÈN VÀO KHU VỰC BIẾN TOÀN CỤC]
active_game_sessions = {} # [BẮT BUỘC] Phải là ngoặc nhọn {} để lưu Process ID #
GLOBAL_GHOST_PREVIEW = None  # <--- Biến cầu nối để gọi animation từ bất cứ đâu















# =================================================================
# [NEW V5] CHANGELOG MODAL (CRYSTAL CLEAR + CONTINUOUS GEAR)
# =================================================================
class ChangelogModal(ft.Container):
    def __init__(self, page_ref):
        super().__init__()
        self.page_ref = page_ref
        self.visible = False
        self.is_idling = False # Cờ kiểm soát vòng quay chậm
        
        # --- CẤU HÌNH ANIMATION TAB ---
        self.opacity = 0 
        self.animate_opacity = ft.Animation(400, "easeOut")
        
        # Offset: Trượt từ trái (-0.2) vào giữa
        self.offset = ft.transform.Offset(-0.2, 0) 
        self.animate_offset = ft.Animation(600, "easeOutCubic")
        
        self.alignment = ft.alignment.center
        self.expand = True 
        self.bgcolor = "#00000000"
        
        self.changelog_content = """
- Fix Lỗi cho lnd (cái bug xung đột với steam).
- Tối ưu lại phần giao diện nhìn cho nó mượt hơn vs đẹp hơn.
- Thêm thông tin nhiều và đa dạng hơn cho mỗi game kèm theo đó là cào dữ liệu từ steam và lnd cho phần info của mỗi game card.
- Thêm phần online và offline cho mỗi 1 game card, dẫu phần này hơi chậm và ngu nên cần về sao fix lại.
- Mẹ m bel.
        """

        # --- [1] ICON BÁNH RĂNG ---
        self.gear_icon = ft.Icon(
            ft.icons.SETTINGS, 
            color="#00E5FF", 
            size=28,
            rotate=ft.Rotate(0, alignment=ft.alignment.center),
            # Animation sẽ được code điều khiển tay hoàn toàn để mượt hơn
            animate_rotation=None 
        )

        # --- [2] NÚT BẤM TỐI GIẢN (Đen mờ) ---
        self.btn_close = ft.Container(
            content=ft.Text("Đã Hiểu", size=12, weight="bold", color="#666666"),
            width=120, height=35,
            # Nền gần như tàng hình, chỉ hiện khi hover
            bgcolor="#00000000", 
            border=ft.border.all(1, "#333333"), 
            border_radius=6,
            alignment=ft.alignment.center,
            animate_scale=ft.Animation(100, "easeOut"),
            animate=ft.Animation(200, "easeOut"),
            on_click=self.hide,
            on_hover=self.animate_button_hover
        )

        # --- [3] UI CHÍNH (Cái bảng Trong Suốt) ---
        self.dialog_box = ft.Container(
            width=600, height=380,
            
            # --- [QUAN TRỌNG] ĐỘ TRONG SUỐT ---
            # #0D... = Alpha 5% (Gần như trong vắt)
            bgcolor="#0D000000", 
            
            # Giảm Blur xuống thấp (5-10) để nhìn xuyên thấu rõ hơn
            # Nếu muốn trong vắt như kính thường thì chỉnh về 0
            blur=ft.Blur(8, 8, ft.BlurTileMode.MIRROR),
            
            border_radius=12,
            border=ft.border.all(1, "#1AFFFFFF"), # Viền trắng siêu mờ để định hình
            shadow=ft.BoxShadow(blur_radius=50, color="#000000"), # Bóng đổ để tách nền
            padding=25,
            
            content=ft.Column([
                # Header
                ft.Row([
                    self.gear_icon, 
                    ft.Text("NHẬT KÝ CẬP NHẬT", size=18, weight="bold", color="white", font_family="Segoe UI"),
                    ft.Container(expand=True),
                    ft.IconButton(ft.icons.CLOSE, icon_color="#444444", icon_size=20, on_click=self.hide)
                ], alignment=ft.MainAxisAlignment.CENTER),
                
                ft.Divider(color="#1AFFFFFF", height=20),
                
                # Nội dung
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        ft.Text(f"Phiên bản: v{CURRENT_VERSION}", italic=True, color="#00E5FF", size=12),
                        ft.Container(height=10),
                        ft.Text(self.changelog_content, size=14, color="#DDDDDD", font_family="Consolas"),
                    ], scroll=ft.ScrollMode.AUTO)
                ),
                
                ft.Divider(color="#1AFFFFFF", height=20),
                
                # Footer
                ft.Row([self.btn_close], alignment=ft.MainAxisAlignment.END)
            ])
        )
        
        self.content = self.dialog_box

    # --- ANIMATION NÚT (Sáng nhẹ khi hover) ---
    def animate_button_hover(self, e):
        is_hover = e.data == "true"
        e.control.scale = 1.05 if is_hover else 1.0
        # Hover: Hiện nền đen mờ + Viền sáng
        e.control.bgcolor = "#80000000" if is_hover else "#00000000"
        e.control.border = ft.border.all(1, "#00E5FF") if is_hover else ft.border.all(1, "#333333")
        e.control.content.color = "white" if is_hover else "#666666"
        e.control.content.update()
        e.control.update()

    # --- LUỒNG QUAY BÁNH RĂNG (Vô tận) ---
    def gear_loop(self):
        # 1. Quay nhanh lúc đầu (Giả lập lăn vào)
        steps = 20
        for i in range(steps):
            if not self.visible: return
            self.gear_icon.rotate.angle += 0.3 # Tốc độ nhanh
            self.gear_icon.update()
            time.sleep(0.02)

        # 2. Chuyển sang quay chậm (Idle)
        self.is_idling = True
        while self.visible and self.is_idling:
            self.gear_icon.rotate.angle += 0.04 # Tốc độ chậm rãi
            self.gear_icon.update()
            time.sleep(0.03)

    def show(self):
        self.visible = True
        self.opacity = 0
        self.offset = ft.transform.Offset(-0.2, 0)
        self.gear_icon.rotate.angle = 0 # Reset góc
        self.page_ref.update()
        
        time.sleep(0.05)
        
        # Animation trượt vào
        self.opacity = 1
        self.offset = ft.transform.Offset(0, 0)
        self.page_ref.update()
        
        # Bắt đầu luồng quay bánh răng
        threading.Thread(target=self.gear_loop, daemon=True).start()

    def hide(self, e=None):
        self.is_idling = False # Dừng quay chậm
        
        # Animation trượt ra
        self.opacity = 0
        self.offset = ft.transform.Offset(0.2, 0) 
        self.page_ref.update()
        
        # Quay nhanh thêm 1 đoạn (Giả lập lăn đi)
        def spin_out():
            for _ in range(15):
                self.gear_icon.rotate.angle += 0.4
                self.gear_icon.update()
                time.sleep(0.02)
            
            self.visible = False
            # Reset về vị trí ẩn bên trái
            self.offset = ft.transform.Offset(-0.2, 0)
            try: self.page_ref.update()
            except: pass

        threading.Thread(target=spin_out, daemon=True).start()

    # LOGIC KIỂM TRA (DỄ TÍNH: Cứ khác version là hiện)
    def check_and_show_once(self):
        try:
            flag_file = os.path.join(get_base_path(), "Launcher_Data", "last_opened_version.txt")
            last_ver = ""
            if os.path.exists(flag_file):
                with open(flag_file, "r") as f: last_ver = f.read().strip()
            
            # 1. Nếu chưa có file (lần đầu chạy) -> Hiện luôn để chào mừng
            if not last_ver:
                self.show()
                with open(flag_file, "w") as f: f.write(CURRENT_VERSION)
                return

            # 2. Nếu phiên bản lưu trong file KHÁC phiên bản hiện tại -> Hiện luôn
            # (Bất kể nâng cấp, hạ cấp hay cài đè, miễn khác là hiện)
            if last_ver != CURRENT_VERSION:
                self.show()
                with open(flag_file, "w") as f: f.write(CURRENT_VERSION)
            
            # Nếu trùng version thì thôi, không làm gì cả.
                
        except Exception: pass






        












class GhostDownloadPreview(ft.Container):
    def __init__(self):
        super().__init__()
        self.visible = False 
        self.force_stop = False # [MỚI] Cờ để báo hiệu tắt ngay lập tức
        
        # ... (Các thông số width, offset, opacity cũ GIỮ NGUYÊN) ...
        self.width = 260 
        self.left = 0
        self.top = 0
        self.bottom = 0 
        self.opacity = 0 
        self.offset = ft.transform.Offset(-0.2, 0) 
        self.animate_opacity = ft.Animation(500, "easeOut") 
        self.animate_offset = ft.Animation(500, "easeOutQuart") 
        self.bgcolor = ft.colors.with_opacity(0.08, "#000000") 
        self.blur = ft.Blur(10, 10, ft.BlurTileMode.MIRROR)
        self.border = ft.border.only(right=ft.border.BorderSide(1, ft.colors.with_opacity(0.1, "white")))
        self.shadow = None 

        # Nội dung (Giữ nguyên)
        self.img = ft.Image(width=60, height=60, border_radius=8, fit=ft.ImageFit.COVER, opacity=0.9)
        self.lbl = ft.Text("", size=14, weight="bold", color="white", no_wrap=True)
        
        self.content = ft.Container(
            padding=20,
            content=ft.Column(controls=[
                ft.Container(height=40), 
                ft.Row([
                    ft.Icon(ft.icons.DOWNLOAD_FOR_OFFLINE, color="#00E5FF", size=24), 
                    ft.Text("KHO TẢI", weight="bold", size=15, color="white")
                ]),
                ft.Divider(color=ft.colors.with_opacity(0.15, "white"), height=20),
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.05, "white"), 
                    padding=10, border_radius=10,
                    content=ft.Row([
                        self.img, 
                        ft.Column([
                            self.lbl,
                            ft.Text("Đang khởi tạo...", size=11, color="cyan", italic=True),
                            ft.ProgressBar(width=80, height=2, color="cyan", bgcolor="#444444")
                        ], spacing=3)
                    ], spacing=10)
                ),
                ft.Container(expand=True), 
                ft.Text("Nhấn Tab để xem chi tiết", color="white60", size=11, weight="bold")
            ])
        )

    # [MỚI] Hàm tắt ngay lập tức (Gọi khi bấm Tab)
    def hide_fast(self):
        self.force_stop = True # Gửi tín hiệu dừng
        self.visible = False   # Ẩn ngay lập tức khỏi màn hình
        self.opacity = 0
        self.update()

    def trigger(self, name, icon):
        try:
            self.force_stop = False # Reset cờ
            self.lbl.value = name if len(name) < 15 else name[:12] + "..."
            self.img.src = icon if icon else "https://via.placeholder.com/60"
            
            # Reset trạng thái
            self.visible = True
            self.opacity = 0 
            self.offset = ft.transform.Offset(-0.2, 0)
            self.update()
            
            def run():
                time.sleep(0.05)
                # 1. Hiện ra
                if self.force_stop: return # Check ngay
                self.opacity = 1 
                self.offset = ft.transform.Offset(0, 0)
                self.update()
                
                # 2. [THÔNG MINH] Thay vì ngủ 2.2s liền tù tì, ta ngủ 22 lần, mỗi lần 0.1s
                # Để nếu bấm Tab cái là thoát vòng lặp ngay
                for _ in range(22): 
                    if self.force_stop: return # Thoát ngay nếu bị ép tắt
                    time.sleep(0.1) 
                
                # 3. Biến mất (Chỉ chạy nếu không bị force_stop)
                if not self.force_stop:
                    self.opacity = 0 
                    self.offset = ft.transform.Offset(-0.2, 0)
                    self.update()
                    time.sleep(0.6)
                    if not self.force_stop: # Check lần cuối
                        self.visible = False
                        self.update()
            
            threading.Thread(target=run, daemon=True).start()
        except: pass






















CURRENT_VERSION = "2.0.5"


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

# --- [V4.7 BACK TO BASIC] THÔNG BÁO CHUẨN (TREO 5 PHÚT CHO UPDATE) ---
def show_push_notification(message, type="info", duration=4000, on_click_action=None, key=None):
    # 1. Chống Spam
    if key:
        for control in notification_stack.controls:
            if control.data == key: return

    # 2. Cấu hình màu
    config = {
        "info": {"color": "#2196F3", "icon": ft.icons.INFO},
        "success": {"color": "#4CAF50", "icon": ft.icons.CHECK},
        "warning": {"color": "#FFC107", "icon": ft.icons.WARNING},
        "error": {"color": "#F44336", "icon": ft.icons.ERROR},
        "update": {"color": "#D32F2F", "icon": ft.icons.CLOUD_DOWNLOAD},
        "loading": {"color": "#1976D2", "icon": ft.icons.DOWNLOADING},
    }
    style = config.get(type, config["info"])
    
    # [LOGIC QUAN TRỌNG] Nếu là Update -> Ép thời gian lên 5 phút (300 giây)
    # Dù bên ngoài truyền bao nhiêu thì vào đây cũng thành 5 phút
    if type == "update":
        duration = 300000 

    banner_ref = [None]

    def close_banner(e=None):
        if banner_ref[0]:
            try:
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

    # --- UI ĐƠN GIẢN NHẤT ---
    icon_box = ft.Container(
        content=ft.Icon(style["icon"], color="white", size=16),
        width=30, height=30, bgcolor=style["color"],
        border_radius=15, alignment=ft.alignment.center,
        # Không Rotate, Không Shine, Không Stack
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

    # Chèn vào Stack (Update lên đầu)
    update_index = -1
    for i, ctrl in enumerate(notification_stack.controls):
        if ctrl.data == "update_alert": update_index = i; break
    
    if update_index != -1 and type != "update":
        notification_stack.controls.insert(update_index + 1, banner)
    else:
        notification_stack.controls.insert(0, banner)
        
    notification_stack.update()

    # Animation Loop (Chỉ mở ra và chờ tắt)
    def animate_physics():
        try:
            # 1. Animation mở rộng
            time.sleep(0.05)
            target_width = 280
            current_w = 30
            text_shown = False
            
            while abs(target_width - current_w) > 1:
                current_w += (target_width - current_w) * 0.08
                banner.width = current_w
                if current_w > 180 and not text_shown:
                    text_content.opacity = 1
                    text_content.update()
                    text_shown = True
                banner.update()
                time.sleep(0.016)
            
            banner.width = target_width
            if not text_shown: 
                text_content.opacity = 1
                text_content.update()
            banner.update()

            # 2. CHỜ VÀ TẮT
            if duration:
                # Ngủ đúng thời gian quy định (5 phút với update) rồi tắt
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


# ==========================================
# [NEW] HỆ THỐNG DATA TỰ ĐỘNG (FORMAT PYTHON RAW)
# ==========================================

# 1. Cấu hình đường dẫn (BẠN THAY LINK GITHUB CỦA BẠN VÀO ĐÂY)
# Link phải là dạng RAW (Bấm nút Raw trên Github rồi copy link)
URL_VERSION_FILE = "https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/data_version.txt"
URL_RAW_DATA_FILE = "https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/raw_games.txt"
# --- CẤU HÌNH AUTO-FIX LND ---
LND_FIX_FILENAME = "LinkNeverDie.Com_Lib.dll"
# Link tải file thuốc xịn từ Github của bạn
URL_LND_FIX = "https://github.com/anhkhakl/Conist-Launcher-Update/raw/main/LinkNeverDie.Com_Lib.dll"

def apply_lnd_vaccine(game_folder_path):
    """
    Tiêm Vắc-xin: Luôn luôn GHI ĐÈ file thuốc xịn vào thư mục game.
    Kể cả file cũ có đang ở chế độ Read-only cũng phá để ghi đè.
    """
    import stat # Thư viện để chỉnh quyền file
    
    try:
        # 1. Kiểm tra "Kho thuốc" (Launcher_Data) đã có thuốc chưa?
        local_fix_path = os.path.join(BASE_DATA_PATH, LND_FIX_FILENAME)
        
        # Nếu kho chưa có thì tải về từ Github
        if not os.path.exists(local_fix_path):
            print("[AUTO-FIX] Trong kho chưa có thuốc, đang tải về...")
            try:
                res = requests.get(URL_LND_FIX, timeout=15)
                if res.status_code == 200:
                    with open(local_fix_path, "wb") as f:
                        f.write(res.content)
                else:
                    print(f"[AUTO-FIX] Tải thuốc thất bại: {res.status_code}")
                    return 
            except: return

        # 2. Xác định vị trí file trong thư mục Game (Mục tiêu cần tiêu diệt/thay thế)
        dest_path = os.path.join(game_folder_path, LND_FIX_FILENAME)
        
        # 3. [QUAN TRỌNG] Xử lý file cũ trong thư mục game (nếu có)
        if os.path.exists(dest_path):
            try:
                # Kiểm tra nếu file cũ bị set "Read-only" thì gỡ ra để xóa được
                os.chmod(dest_path, stat.S_IWRITE)
                # Xóa luôn cho sạch sẽ
                os.remove(dest_path)
                print("[AUTO-FIX] Đã xóa file cũ trong game.")
            except Exception as e:
                print(f"[AUTO-FIX] Không xóa được file cũ: {e}")
                # Nếu không xóa được (do đang chạy chẳng hạn) thì return luôn
                return

        # 4. Chép file thuốc xịn vào
        shutil.copy2(local_fix_path, dest_path)
        print(f"[AUTO-FIX] Đã chép đè thuốc mới vào: {game_folder_path}")

    except Exception as e:
        print(f"[AUTO-FIX] Lỗi: {e}")
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
        
        res = requests.get(f"{URL_RAW_DATA_FILE}?t={timestamp}", timeout=15)
        
        if res.status_code == 200:
            raw_content = res.text
            
            # [QUAN TRỌNG] Kiểm tra thử xem có đọc được không
            test_data = parse_mixed_game_data(raw_content)
            
            if len(test_data) > 0:
                with open(LOCAL_DATA_PATH, "w", encoding="utf-8") as f:
                    f.write(raw_content)
                return True
            else:
                print("[DATA] File tải về không đọc được game nào!")
                return False
    except Exception as e:
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
    """Lấy link ảnh bìa từ LND (Retry + Headers)"""
    if not lnd_url: return None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://linkneverdie.net/'
    }

    for attempt in range(3):
        try:
            res = requests.get(lnd_url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            img = soup.find('img', id='wallpaper_img')
            if img:
                src = img.get('src')
                return "https://linkneverdie.net" + src if src.startswith("/") else src
            break # Nếu vào được web mà không thấy ảnh thì thôi, không retry
        except:
            time.sleep(1) # Lỗi mạng thì thử lại
            
    return None

def fetch_lnd_version(lnd_url):
    """Lấy version game (Retry + Headers)"""
    if not lnd_url: return "N/A"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for attempt in range(3):
        try:
            res = requests.get(lnd_url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Cách 1: Tìm thẻ data-label
            ver_p = soup.find('p', class_='data-label', string=re.compile(r'Phiên bản', re.I))
            if ver_p:
                ver_info = ver_p.find_next_sibling('p', class_='info')
                if ver_info: return ver_info.get_text(strip=True)
            
            # Cách 2: Tìm trong Title
            title = soup.title.string if soup.title else ""
            match = re.search(r'(?:v|ver|build|update)\.?\s*(\d+(?:\.\d+)*)', title, re.I)
            if match: return match.group(1)
            
            return "Unknown"
        except:
            time.sleep(1)
            
    return "Error"

def download_icon(img_url, save_path):
    """Tải icon và CẮT VUÔNG (Center Crop) để không bị méo"""
    for attempt in range(3):
        try:
            if save_path.endswith(".png"): save_path = save_path.replace(".png", ".jpg")
            
            # Dùng http_session đã khai báo ở trên
            res = http_session.get(img_url, stream=True, timeout=10)
            
            if res.status_code == 200:
                img = Image.open(res.raw)
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                
                # --- [FIX QUAN TRỌNG] THUẬT TOÁN CẮT ẢNH VUÔNG ---
                # Thay vì ép (resize) gây méo, ta sẽ cắt lấy phần giữa (Crop)
                width, height = img.size
                new_edge = min(width, height) # Lấy cạnh ngắn nhất làm chuẩn
                
                # Tính toán tọa độ trung tâm để cắt đúng giữa
                left = (width - new_edge) / 2
                top = (height - new_edge) / 2
                right = (width + new_edge) / 2
                bottom = (height + new_edge) / 2
                
                # Cắt ảnh trước
                img = img.crop((left, top, right, bottom))
                
                # Sau đó mới thu nhỏ về 150x150
                img = img.resize((150, 150), Image.Resampling.LANCZOS)
                
                img.save(save_path, "JPEG", quality=90)
                return True
        except Exception as e:
            # print(f"Lỗi tải ảnh: {e}")
            time.sleep(0.5)
    return False
# --- HÀM CHECK STEAM (TỐC ĐỘ CAO) ---
def check_steam_online_status(game_name):
    try:
        # 1. Tìm kiếm game trên Steam
        # Dùng cookies để vượt qua Age Gate (xác nhận tuổi) của Steam
        cookies = {'birthtime': '0', 'lastagecheckage': '1-January-1990'}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # Search term
        search_url = f"https://store.steampowered.com/search/?term={game_name}&category1=998" # 998 = Game
        res = requests.get(search_url, headers=headers, cookies=cookies, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Lấy kết quả đầu tiên
        link = soup.find('a', class_='search_result_row')
        if not link: 
            return "Offline" # Không tìm thấy trên Steam -> Mặc định Offline
        
        game_url = link['href']
        
        # 2. Vào trang chi tiết game
        res_game = requests.get(game_url, headers=headers, cookies=cookies, timeout=5)
        soup_game = BeautifulSoup(res_game.text, 'html.parser')
        
        # 3. Quét các nhãn (Categories)
        # Tìm các class 'game_area_details_specs' chứa thông tin chơi mạng
        categories = soup_game.find_all('div', class_='game_area_details_specs')
        
        status = "Offline"
        for cat in categories:
            txt = cat.get_text().lower()
            # Từ khóa nhận diện Online của Steam
            if "multi-player" in txt or "multiplayer" in txt or "online" in txt or "co-op" in txt or "mmo" in txt:
                status = "Online"
                break
        
        return status
    except:
        return "Offline" # Lỗi mạng -> Mặc định Offline cho an toàn

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
        # --- [CODE GỐC TỪ TEST2.TXT - KHÔNG CÓ DELAY] ---
        
        # 1. Hiện cửa sổ NGAY LẬP TỨC (Không được sleep trước đó)
        self.page.window.visible = True
        
        # 2. Thay đổi kích thước +10px để ép Windows vẽ lại giao diện ngay
        # (Thao tác này giúp fix lỗi màn hình đen hoặc giao diện bị bẹp)
        self.page.window.width = 1280 + 10
        self.page.window.height = 720 + 10
        self.page.update()
        
        # 3. Nghỉ cực ngắn để Windows kịp xử lý lệnh resize
        await asyncio.sleep(0.1)

        # 4. Trả về kích thước chuẩn và căn giữa
        self.page.window.width = 1280
        self.page.window.height = 720
        self.page.window.center()
        self.page.update()
        # -----------------------------------------------------------

        # Chạy thanh Loading (Giữ nguyên)
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
















# --- [NEW] HÀM CHẠY SYSTEM TRAY ---
def run_system_tray(page):
    # 1. Định nghĩa hàm mở lại App
    def on_open_request(icon, item):
        icon.stop() # Tắt tray icon đi
        page.window.visible = True
        page.window.always_on_top = True # Đẩy lên trên cùng
        page.update()
        
        time.sleep(0.1)
        page.window.always_on_top = False # Trả lại trạng thái bình thường
        page.update()

    # 2. Định nghĩa hàm thoát hẳn
    def on_quit_request(icon, item):
        icon.stop()
        page.window.destroy() # Hủy cửa sổ Flet => Tắt App

    # 3. Lấy icon của App
    icon_path = os.path.join(get_base_path(), "Launcher_Data", "app_icon.ico")
    # Nếu không tìm thấy icon thì dùng icon mặc định (tạo ảnh trống) hoặc bỏ qua
    image = Image.open(icon_path) 

    # 4. Tạo Menu chuột phải
    menu = (
        item('Mở Launcher', on_open_request, default=True), # Double click là mở
        item('Thoát hẳn', on_quit_request)
    )

    # 5. Chạy Icon
    tray_icon = pystray.Icon("ConistLauncher", image, "Conist Link Launcher", menu)
    tray_icon.run()
















# ==========================================
# 3. GIAO DIỆN CHÍNH (MAIN APP)
# ==========================================

def main(page: ft.Page):
    # --- [FIX QUAN TRỌNG] CẤU HÌNH MÀU TRONG SUỐT NGAY LẬP TỨC ---
    # Phải đặt ở đây để Flet hiểu ngay khi vừa tạo cửa sổ
    page.window.visible = False 
    page.bgcolor = "#141E30"        
    page.window.bgcolor = "#141E30"
    page.window.frameless = True
    page.window.title_bar_hidden = True
    # -------------------------------------------------------------

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
    # 3. Kích hoạt App (Dán vào cuối hàm main)
    try:
        if 'run_startup' in locals():
            page.run_task(run_startup)
    except Exception as e:
        print(f"Lỗi Startup: {e}")
        # Nếu lỗi, ép hiện giao diện ngay để cứu vãn
        page.window.always_on_top = False
        bg_container.opacity = 1
        main_layout.opacity = 1
        page.update()
    global APP_CONFIG, file_picker, GAME_LIST
    
    # XÓA DANH SÁCH CŨ
    GAME_LIST.clear() 

# [TRẢ LẠI CODE GỐC]
    global grid
    grid = ft.GridView(
        expand=True, runs_count=5, max_extent=180, child_aspect_ratio=0.7,
        spacing=20, run_spacing=20, padding=20,

    )
# --- [FIX FINAL] HÀM VẼ GRID CHUẨN (DÙNG CHUNG CHO ALL) ---
    def render_grid_safe(source_list):
        try:
            grid.controls.clear()
            
            if not source_list:
                grid.controls.append(ft.Text("Không tìm thấy game nào.", color="yellow"))
                grid.update()
                return

            # 1. Tạo thẻ (Mặc định tàng hình do class GameCard)
            temp_cards = []
            for g in source_list:
                try:
                    card = GameCard(g)
                    temp_cards.append(card)
                    grid.controls.append(card)
                except: pass
            
            # 2. Update Grid để Flet gắn thẻ vào Page
            grid.update()
            
            # 3. Chạy hiệu ứng "Thác đổ" (Có kiểm tra an toàn)
            def animate_worker():
                # [QUAN TRỌNG] Chờ 0.1s để đảm bảo thẻ đã được gắn vào Page
                # Fix lỗi "Control must be added to the page first"
                time.sleep(0.1) 
                
                for card in temp_cards:
                    try:
                        # Chỉ update nếu thẻ thực sự đang nằm trên Page
                        if card.page: 
                            card.opacity = 1
                            card.update()
                            time.sleep(0.03) # Tốc độ thác đổ
                    except: pass
            
            threading.Thread(target=animate_worker, daemon=True).start()

        except Exception as e:
            print(f"Lỗi Render Grid: {e}")
    def refresh_data_and_grid():
        global RAW_GAME_DATA
        GAME_LIST.clear()
        
        # 1. NẠP DỮ LIỆU TỪ FILE LOCAL (Dùng Parser thông minh)
        if os.path.exists(LOCAL_DATA_PATH):
            try:
                with open(LOCAL_DATA_PATH, "r", encoding="utf-8") as f:
                    content = f.read()
                    if len(content) > 5:
                        # [THAY ĐỔI Ở ĐÂY] Gọi hàm parse mới
                        RAW_GAME_DATA = parse_mixed_game_data(content)
                        print(f"[DATA] Đã nạp thành công {len(RAW_GAME_DATA)} game.")
            except Exception as e:
                print(f"[DATA] Lỗi đọc file: {e}")

        GAME_LIST.clear()
        
        # 2. Đọc Cache trạng thái (Status, Online/Offline cũ)
        cached_data = {}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_data = {g['name']: g for g in json.load(f)}
            except: pass

        # 3. Convert dữ liệu thật (Bỏ qua Dummy)
        for raw in RAW_GAME_DATA:
            try:
                slug = clean_name_for_slug(raw['name'])
                icon_path = os.path.join(ICON_FOLDER, f"{slug}.jpg")
                saved = cached_data.get(raw['name'], {})
                
                # Logic lấy icon: Ưu tiên file trong máy -> Link web -> Placeholder
                final_icon = icon_path if os.path.exists(icon_path) else raw.get('icon', '')
                if not final_icon: final_icon = "https://via.placeholder.com/150"

                game_obj = {
                    "name": raw['name'],
                    "subtitle": raw.get('subtitle', ''),
                    "version": raw.get('version', '1.0'),
                    "lnd_url": raw.get('lnd_url', ''),
                    "download_link": raw.get('download_link', ''),
                    "viet_link": raw.get('viet_link'),
                    "icon": final_icon,
                    "status": saved.get('status', 'CHƯA KIỂM TRA'),
                    "mp_status": saved.get('mp_status', None), 
                    "requirements": saved.get('requirements', ''),
                    "album_images": saved.get('album_images', [])
                }
                GAME_LIST.append(game_obj)
            except Exception as e:
                print(f"Lỗi skip game: {e}")

        # 4. [FIX] Vẽ lại Grid với Hiệu ứng Thác đổ (Waterfall)
        try:
            if 'grid' in locals() or 'grid' in globals():
                render_grid_safe(GAME_LIST)
                grid.controls.clear()
                
                if not GAME_LIST:
                    grid.controls.append(ft.Text("Đang tải danh sách game...", color="yellow"))
                    grid.update()
                else:
                    # Tạo danh sách thẻ tạm thời
                    temp_cards = []
                    for g in GAME_LIST:
                        try:
                            card = GameCard(g)
                            temp_cards.append(card)
                            grid.controls.append(card)
                        except: pass
                    
                    # Cập nhật Grid lần 1 (Lúc này thẻ đang tàng hình opacity=0)
                    grid.update()
                    
                    # [NEW] Chạy luồng riêng để bật từng thẻ lên (Hiệu ứng Sang Chảnh)
                    def animate_cards_show():
                        import time
                        for card in temp_cards:
                            # Chỉ hiện những thẻ đang tàng hình
                            if card.opacity == 0:
                                card.opacity = 1
                                card.update()
                                # Nghỉ cực ngắn (0.03s) tạo hiệu ứng sóng lướt qua
                                time.sleep(0.03) 
                                
                    threading.Thread(target=animate_cards_show, daemon=True).start()

                print(f"[SYSTEM] Đã hiển thị {len(GAME_LIST)} game.")
        except Exception as e:
            print(f"[UI ERROR] Không thể vẽ Grid: {e}")



    # --- [FIX FINAL V3] TẮT APP MƯỢT NHƯ GAME (GPU RENDER) ---
    def on_window_event(e):
        if e.data == "close":
            try:
                # 1. KÍCH HOẠT HIỆU ỨNG BIẾN MẤT (FADE OUT NỘI DUNG)
                # Dùng GPU của Flet để làm mờ nội dung, mượt hơn làm mờ cửa sổ Windows gấp 10 lần
                main_layout.animate_opacity = ft.Animation(200, "easeIn") # 200ms = 0.2 giây
                main_layout.opacity = 0
                main_layout.update()
                
                # 2. Đợi đúng 0.2s cho hiệu ứng chạy xong
                time.sleep(0.2)
            except: pass

            # 3. ẨN CỬA SỔ NGAY LẬP TỨC
            page.window.visible = False
            page.update()

            # 4. DỌN DẸP CHIẾN TRƯỜNG (CHẠY NGẦM)
            def background_cleanup():
                try:
                    # Hủy download
                    if ACTIVE_DOWNLOADS:
                        for name, state in list(ACTIVE_DOWNLOADS.items()):
                            state['cancelled'] = True
                        time.sleep(0.5) 

                    # Xử lý Tray Icon hoặc Thoát hẳn
                    run_bg = APP_CONFIG.get("run_in_background", False)
                    if run_bg and HAS_TRAY_LIB:
                        # [QUAN TRỌNG] Reset lại độ rõ để lần sau mở lên từ Tray thì thấy được
                        # (Vì App chỉ ẩn đi chứ không tắt hẳn)
                        main_layout.opacity = 1
                        page.update()
                        threading.Thread(target=run_system_tray, args=[page], daemon=True).start()
                    else:
                        page.window.destroy()
                        os._exit(0) # Kill sạch sành sanh
                except: 
                    os._exit(0)

            threading.Thread(target=background_cleanup, daemon=True).start()

    page.window.prevent_close = True 
    page.window.on_event = on_window_event











    def save_cache():
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(GAME_LIST, f, indent=4, ensure_ascii=False)
        except: pass
    
# --- SETUP CỬA SỔ ---
    # 1. Ẩn đi để chờ Splash hiện (Fix lỗi không có loading)
    page.window.visible = False 
    
    # 2. Luôn hiện trên cùng LÚC ĐẦU (để Splash không bị che) -> Sau này sẽ tắt
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
    
    # [FIX SCROLL FINAL] Thanh cuộn "Zin": Đẹp, Mượt, Dễ kéo
    page.theme = ft.Theme(
        font_family="Segoe UI",
        scrollbar_theme=ft.ScrollbarTheme(
            thumb_visibility=True,      # Luôn hiện (để bạn dễ cầm)
            thickness=8,                # Dày 8px (Chuẩn UX, không quá to, không quá bé)
            radius=4,                   # Bo góc mềm mại (Sang hơn bo 10px)
            interactive=True,           # Tăng độ nhạy khi kéo
            # Tuyệt đối KHÔNG set màu -> Để nó tự dùng màu Xám/Trắng mặc định siêu đẹp
        )
    )
    page.update()

    # --- CÁC HÀM XỬ LÝ SỰ KIỆN (ĐÃ ĐƯỢC THỤT LỀ CHUẨN) ---
    
    def on_startup_change(e): 
        toggle_startup(e.control.value)

    def window_drag(e): 
        page.window.start_dragging()








# --- [FIX 1] KHAI BÁO BIẾN CỜ Ở ĐÂY ---
    is_scanning_updates = False 
    active_game_sessions = {}

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
                if not APP_CONFIG.get("auto_update_games", False): break

                if game.get('lnd_url') and len(str(game.get('lnd_url'))) > 10:
                    try:
                        # [SỬA] Gọi hàm lấy full info để lấy cả Version lẫn Multiplayer
                        full_info = fetch_full_details(game['lnd_url']) 
                        
                        if full_info:
                            # 1. Cập nhật Online/Offline
                            game['mp_status'] = full_info.get('mp_status', 'Offline')

                            # 2. Check Version (Giữ nguyên logic cũ nhưng lấy từ full_info)
                            online_ver = full_info.get('web_version', 'Unknown')
                            local_ver = game['version']
                            
                            # ... (Logic so sánh version giữ nguyên) ...
                            # ... Nếu có bản mới thì game['status'] = ...
                            
                            # 3. Cập nhật UI Thẻ Game
                            try:
                                for card in grid.controls:
                                    if card.game['name'] == game['name']:
                                        card.refresh_ui() # Gọi hàm refresh mới
                                        break
                            except: pass
                    except: pass
                
                time.sleep(0.05)
            
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

    # --- [FIX BUG UNIKEY] ---
    # Biến lưu timer (đặt ngay trên hàm on_search)
    search_timer = None 

    def run_search_logic(keyword):
        # Đây là hàm tìm kiếm thực sự (chạy sau khi đã ngừng gõ)
        try:
            val = keyword.lower()
            if not val:
                # Nếu từ khóa rỗng -> Hiện tất cả
                filtered = GAME_LIST
            else:
                # Nếu có từ khóa -> Lọc
                filtered = [g for g in GAME_LIST if val in g['name'].lower()]
            
            # [FIX] Gọi hàm vẽ chuẩn (Sẽ tự động có hiệu ứng hiện lên)
            render_grid_safe(filtered)
            
        except Exception as e:
            print(f"Lỗi Search: {e}")

    def on_search(e):
        nonlocal search_timer # Sử dụng biến timer khai báo bên trên
        
        # 1. Hủy hẹn giờ cũ (nếu người dùng gõ tiếp trong lúc đang đếm)
        if search_timer:
            search_timer.cancel()
        
        # 2. Lấy giá trị hiện tại
        current_val = search_box.value 
        
        # 3. Tạo hẹn giờ mới (Delay 0.4 giây)
        # Chỉ khi nào người dùng ngừng gõ 0.4s thì hàm run_search_logic mới được chạy
        search_timer = threading.Timer(0.4, run_search_logic, args=[current_val])
        search_timer.start()

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
            self.height = 245 
            self.border_radius = 15
            
            # Màu nền mặc định (Đen mờ 50%)
            self.default_bg = "#80000000" 
            self.bgcolor = self.default_bg 
            self.padding = 10
            
            # [QUAN TRỌNG] Hai dòng này quyết định độ mượt
            self.animate_scale = ft.Animation(200, "easeOut")
            self.animate = ft.Animation(200, "easeOut")
            
            # [FIX] Hiệu ứng hiện hình (300ms = Nhanh gọn & Sang)
            self.opacity = 0  # Mặc định tàng hình
            self.animate_opacity = ft.Animation(300, "easeOut")
            
            # Gắn sự kiện
            self.on_click = lambda e: (play_click_sound(), self.open_detail(e))
            self.on_hover = self.hover_card # <--- Bắt buộc phải có dòng này
            
            # 1. Status Update
            stt = self.game.get('status', 'Unknown')
            stt_col = "green" if "ĐÃ CẬP NHẬT" in stt else ("orange" if "CÓ BẢN MỚI" in stt else "grey")
            self.status_txt = ft.Text(stt, size=10, color=stt_col, weight="bold", no_wrap=True)

            # 2. Status Online/Offline
            self.mp_txt = ft.Text("", size=10, color="transparent", weight="bold", no_wrap=True)
            mp_stt = self.game.get('mp_status')
            if mp_stt == "Online":
                self.mp_txt.value = "● ONLINE"
                self.mp_txt.color = "#00E5FF"
            elif mp_stt == "Offline":
                self.mp_txt.value = "● OFFLINE"
                self.mp_txt.color = "#888888"

            # Hình ảnh
            icon_src = self.game.get('icon', '')
            if not icon_src: icon_src = "https://via.placeholder.com/150"
            self.img_control = ft.Image(src=icon_src, width=140, height=140, border_radius=10, fit=ft.ImageFit.COVER)
            
            # 3. Giao diện Card
            self.content = ft.Column([
                self.img_control,
                ft.Text(self.game.get('name', 'No Name'), size=14, weight="bold", no_wrap=True, text_align="center", width=140),
                ft.Column([self.status_txt, self.mp_txt], spacing=2, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            ], spacing=5, alignment=ft.MainAxisAlignment.START, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # [HÀM XỬ LÝ ANIMATION]
        def hover_card(self, e):
            is_hover = e.data == "true"
            # Phóng to 1.05 lần
            self.scale = 1.05 if is_hover else 1.0
            # Sáng nền lên (Trắng mờ 20%)
            self.bgcolor = "#33FFFFFF" if is_hover else self.default_bg 
            self.update()

        def open_detail(self, e): show_game_detail_dialog(self.game, self)
        
        def refresh_ui(self):
            try:
                self.img_control.src = self.game.get('icon', '')
                stt = self.game.get('status', '')
                self.status_txt.value = stt
                self.status_txt.color = "green" if "ĐÃ CẬP NHẬT" in stt else "orange"
                
                mp_stt = self.game.get('mp_status')
                if mp_stt == "Online":
                    self.mp_txt.value = "● ONLINE"; self.mp_txt.color = "#00E5FF"
                elif mp_stt == "Offline":
                    self.mp_txt.value = "● OFFLINE"; self.mp_txt.color = "#888888"
                else:
                    self.mp_txt.value = ""; self.mp_txt.color = "transparent"
                self.update()
            except: pass

    # [FIX CLEANUP] Hàm tải file thông minh (Tự xóa rác nếu bị hủy)
    def download_file_with_state(url, dest_path, progress_callback, control_state, game_name=None):
        try:
            print(f"🔗 CMD: Đang xử lý link: {url}")
            
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

           # --- GIAI ĐOẠN 3: GHI FILE AN TOÀN ---
            total_size = int(final_response.headers.get('Content-Length', 0))
            block_size = 1024 * 1024 
            wrote = 0
            last_time = time.time()
            last_wrote = 0
            
            # [LOGIC MỚI] Dùng try-finally để đảm bảo file luôn được đóng
            file_opened = False
            try:
                with open(dest_path, "wb") as f:
                    file_opened = True
                    for data in final_response.iter_content(block_size):
                        # 1. KIỂM TRA HỦY
                        if control_state["cancelled"]:
                            print(f"CMD: Đã nhận lệnh HỦY cho {game_name}")
                            break # Thoát vòng lặp ghi -> File sẽ tự đóng nhờ 'with'
                        
                        # 2. KIỂM TRA TẠM DỪNG
                        while control_state["paused"]:
                            if control_state["cancelled"]: break
                            time.sleep(1)
                            
                        if data:
                            wrote += len(data)
                            f.write(data)
                            
                            # Tính tốc độ... (Giữ nguyên)
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
            except Exception as e:
                print(f"Lỗi ghi file: {e}")
                return False
            
            # [QUAN TRỌNG] XỬ LÝ HẬU KỲ: XÓA FILE NẾU HỦY
            if control_state["cancelled"]:
                try:
                    time.sleep(0.5) # Chờ 0.5s cho hệ thống nhả file
                    if os.path.exists(dest_path):
                        os.remove(dest_path) # Xóa file rác
                        print(f"CMD: Đã dọn sạch file rác {dest_path}")
                except Exception as del_err:
                    print(f"CMD: Không thể xóa file rác: {del_err}")
                return False # Trả về False vì chưa tải xong

            return True

        except Exception as e:
            print(f"CMD: Lỗi ngoại lệ: {e}")
            return False
        




















        def on_startup_change(e): toggle_startup(e.control.value)
        def window_drag(e): page.window.start_dragging()
        

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
                ft.Switch(
                    label="Cho phép ẩn vào taskbar khi thoát", 
                    value=APP_CONFIG.get("run_in_background", False),
                    on_change=lambda e: (APP_CONFIG.update({"run_in_background": e.control.value}), save_config())
                ),
                ft.Container(height=5),
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


                ft.Container(height=10),
            





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

    def on_dir_result(e: ft.FilePickerResultEvent):
        if e.path:
            APP_CONFIG["download_dir"] = e.path
            save_config()
            
            # [NEW] Quét ngay khi chọn xong thư mục mới
            scan_and_restore_downloaded_games() 

            if hasattr(dir_picker, "pending_game_data"):
                trigger_download_process(dir_picker.pending_game_data)

    dir_picker = ft.FilePicker(on_result=on_dir_result)
    page.overlay.append(dir_picker)















































































        

            # --- [MOVED UP] XỬ LÝ CHƠI GAME + WATCHER ---
    # --- [FIX CORE] XỬ LÝ GIẢI NÉN VÀ CHƠI GAME ---
    def handle_play_game(game_name, e, spinner, status_txt, btn_play, progress_overlay, icon_src=""):
        # Reset UI
        btn_play.visible = False
        spinner.visible = True
        status_txt.value = "Đang xử lý..."
        status_txt.color = "white"
        progress_overlay.width = 0 
        
        btn_play.update()
        spinner.update()
        status_txt.update()
        progress_overlay.update()

        # Helper: Reset UI về trạng thái "Play" nếu lỗi hoặc xong
        def reset_ui_ready():
            try:
                btn_play.visible = True
                btn_play.icon = ft.icons.PLAY_ARROW_ROUNDED
                btn_play.text = "" 
                spinner.visible = False
                status_txt.value = "Sẵn sàng chơi"
                status_txt.color = "#AAAAAA"
                progress_overlay.width = 0
                
                btn_play.update()
                spinner.update()
                status_txt.update()
                progress_overlay.update()
            except: pass

        def game_worker():
            save_path = APP_CONFIG.get("download_dir")
            slug = clean_name_for_slug(game_name)
            
            zip_file = os.path.join(save_path, f"{slug}.zip")
            game_folder = os.path.join(save_path, slug)
            
            # --- GIAI ĐOẠN 1: GIẢI NÉN (NẾU CẦN) ---
            # Chỉ giải nén nếu chưa có folder game
            if not os.path.exists(game_folder) or len(os.listdir(game_folder)) == 0:
                if not os.path.exists(zip_file):
                    status_txt.value = "Lỗi: Không thấy file game!"
                    status_txt.color = "red"
                    status_txt.update()
                    time.sleep(2)
                    reset_ui_ready()
                    return

                status_txt.value = "Đang giải nén..."
                status_txt.update()
                
                # [FIX] Sử dụng WinRAR hoặc 7-Zip hệ thống (Mạnh hơn Python Zip gấp 10 lần)
                extracted_ok = False
                
                # Tìm phần mềm giải nén trên máy
                seven_zip_exe = r"C:\Program Files\7-Zip\7z.exe"
                winrar_exe = r"C:\Program Files\WinRAR\WinRAR.exe"
                if not os.path.exists(winrar_exe): winrar_exe = r"C:\Program Files (x86)\WinRAR\WinRAR.exe"

                # Mật khẩu thông dụng của LND
                passwords = ["LinkNeverDie.Com", "linkneverdie.com"]
                
                # Ưu tiên 1: Dùng 7-Zip (Nhanh nhất)
                if os.path.exists(seven_zip_exe):
                    for pwd in passwords:
                        try:
                            # Lệnh: 7z x -pPASS -y -oOUT IN
                            cmd = [seven_zip_exe, "x", f"-p{pwd}", "-y", f"-o{game_folder}", zip_file]
                            # Chạy lệnh và ẩn cửa sổ đen
                            subprocess.run(cmd, creationflags=0x08000000, check=True)
                            extracted_ok = True
                            break
                        except: pass
                
                # Ưu tiên 2: Dùng WinRAR
                elif os.path.exists(winrar_exe):
                    for pwd in passwords:
                        try:
                            # Lệnh: WinRAR x -pPASS -ibck -y -o+ IN OUT\
                            cmd = [winrar_exe, "x", f"-p{pwd}", "-ibck", "-y", "-o+", zip_file, game_folder + "\\"]
                            subprocess.run(cmd, creationflags=0x08000000, check=True)
                            extracted_ok = True
                            break
                        except: pass
                
                # Ưu tiên 3: Python Zip (Dự phòng cuối cùng - Hay lỗi với file to)
                if not extracted_ok:
                    try:
                        with zipfile.ZipFile(zip_file, 'r') as zf:
                            # Thử từng pass
                            for pwd in passwords:
                                try:
                                    zf.extractall(game_folder, pwd=bytes(pwd, 'utf-8'))
                                    extracted_ok = True
                                    break
                                except: continue
                    except Exception as e:
                        print(f"Zip Error: {e}")

                if not extracted_ok:
                    status_txt.value = "Lỗi giải nén (Pass/Corrupt)"
                    status_txt.color = "red"
                    status_txt.update()
                    time.sleep(3)
                    reset_ui_ready()
                    return # Dừng luôn
                
                # [QUAN TRỌNG] Chỉ xóa zip nếu giải nén thành công
                try: os.remove(zip_file)
                except: pass

            # --- GIAI ĐOẠN 2: TÌM FILE EXE (THÔNG MINH HƠN) ---
            status_txt.value = "Đang khởi động..."
            status_txt.update()
            
            target_exe = None
            candidates = []
            
            # File rác cần né
            ignore_list = ["unitycrashhandler", "unins", "setup", "dxsetup", "vcredist", "crashreport"]
            
            for root, dirs, files in os.walk(game_folder):
                for file in files:
                    if file.lower().endswith(".exe"):
                        f_lower = file.lower()
                        if any(x in f_lower for x in ignore_list): continue
                        
                        score = 0
                        # Ưu tiên file có tên giống tên game
                        if slug.replace("_", "") in f_lower.replace("_", ""): score += 100
                        # Ưu tiên file tên "Launcher"
                        if "launcher" in f_lower: score += 50
                        # Ưu tiên file nằm ngay thư mục gốc (root)
                        if root == game_folder: score += 20
                        
                        candidates.append((score, os.path.join(root, file)))
            
            if candidates:
                # Sắp xếp theo điểm cao nhất
                candidates.sort(key=lambda x: x[0], reverse=True)
                target_exe = candidates[0][1]
            
            if target_exe:
                working_dir = os.path.dirname(target_exe)
                
                # Tiêm thuốc (Nếu có code tiêm thuốc)
                try: apply_lnd_vaccine(working_dir)
                except: pass

                try:
                    subprocess.Popen([target_exe], cwd=working_dir)
                except OSError as err:
                    # Nếu lỗi quyền Admin (Mã 740)
                    if err.winerror == 740:
                        ctypes.windll.shell32.ShellExecuteW(None, "runas", target_exe, None, working_dir, 1)
            else:
                status_txt.value = "Lỗi: Không tìm thấy file .exe game!"
                status_txt.color = "red"
                status_txt.update()
                time.sleep(3)
            
            reset_ui_ready()

        threading.Thread(target=game_worker, daemon=True).start()










































    # =========================================================================
    # [MODULE] GLOBAL WATCHER (RÌNH GAME & GỌI VỆ TINH & AUTO-KILL)
    # =========================================================================

    # OVERLAY_HELPER_NAME = "ConistOverlayHelper.exe"
    # URL_OVERLAY_HELPER = "https://github.com/anhkhakl/Conist-Launcher-Update/releases/download/v2.0.5/ConistOverlayHelper.exe"

    # # 1. HÀM KIỂM TRA & TẢI FILE
    # def ensure_overlay_helper_exists():
    #     try:
    #         data_dir = os.path.join(get_base_path(), "Launcher_Data")
    #         helper_path = os.path.join(data_dir, OVERLAY_HELPER_NAME)
            
    #         # Nếu chưa có thì tải về
    #         if not os.path.exists(helper_path):
    #             print("[OVERLAY] Đang tải Helper về...")
    #             try:
    #                 res = requests.get(URL_OVERLAY_HELPER, stream=True, timeout=30)
    #                 if res.status_code == 200:
    #                     with open(helper_path, "wb") as f:
    #                         for chunk in res.iter_content(chunk_size=8192):
    #                             f.write(chunk)
    #                     print("[OVERLAY] Tải Helper thành công.")
    #                 else:
    #                     print(f"[OVERLAY] Link hỏng: {res.status_code}")
    #                     return None
    #             except:
    #                 return None
                    
    #         return helper_path
    #     except Exception as e:
    #         print(f"[OVERLAY] Lỗi tải Helper: {e}")
    #         return None

    # # 2. HÀM BẬT OVERLAY (CHẾ ĐỘ DEBUG)
    # def launch_overlay_process(game_name, icon_path, x, y, hwnd):
    #     print(f"\n[DEBUG] --- BẮT ĐẦU QUY TRÌNH GỌI VỆ TINH ---")
    #     print(f"[DEBUG] Game: {game_name}")
    #     print(f"[DEBUG] Icon: {icon_path}")
    #     print(f"[DEBUG] Tọa độ: X={x}, Y={y}")
    #     print(f"[DEBUG] HWND: {hwnd}")

    #     try:
    #         hp = ensure_overlay_helper_exists()
    #         print(f"[DEBUG] Đường dẫn Helper: {hp}")
            
    #         if not hp:
    #             print("[DEBUG] LỖI: Không lấy được đường dẫn Helper (None).")
    #             return None
                
    #         if not os.path.exists(hp):
    #             print(f"[DEBUG] LỖI: File Helper không tồn tại tại: {hp}")
    #             return None
                
    #         print(f"[DEBUG] File tồn tại. Đang thử kích hoạt subprocess...")
            
    #         cmd_args = [hp, str(game_name), str(icon_path), str(x), str(y), str(hwnd)]
            
    #         # Dùng Popen để không bị treo Launcher
    #         proc = subprocess.Popen(cmd_args)
            
    #         if proc:
    #             print(f"[DEBUG] THÀNH CÔNG: Đã tạo tiến trình. PID: {proc.pid}")
    #             return proc
    #         else:
    #             print("[DEBUG] LỖI: Popen trả về None.")

    #     except Exception as e:
    #         print(f"[DEBUG] NGOẠI LỆ (CRASH): {e}")
            
    #     return None

    # # 3. HÀM WATCHER (AUTO-KILL & DICT LOGIC)
    # def start_global_game_watcher():
    #     import ctypes
    #     from ctypes import wintypes
        
    #     user32 = ctypes.windll.user32
    #     kernel32 = ctypes.windll.kernel32
    #     psapi = ctypes.windll.psapi

    #     print("[WATCHER] Đã kích hoạt chế độ Auto-Kill Overlay (Dict Mode)...")
        
    #     def get_process_name(hwnd):
    #         try:
    #             pid = ctypes.c_ulong()
    #             user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    #             if pid.value == 0: return ""
    #             hProcess = kernel32.OpenProcess(0x1000, False, pid) 
    #             if hProcess:
    #                 buf = ctypes.create_unicode_buffer(1024)
    #                 psapi.GetModuleBaseNameW(hProcess, None, buf, 1024)
    #                 kernel32.CloseHandle(hProcess)
    #                 return buf.value.lower()
    #         except: pass
    #         return ""

    #     def worker():
    #         while True:
    #             try:
    #                 WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    #                 IGNORED_APPS = [
    #                     "explorer.exe", "chrome.exe", "msedge.exe", "firefox.exe", 
    #                     "discord.exe", "steam.exe", "taskmgr.exe", "searchapp.exe",
    #                     "conistoverlayhelper.exe", "code.exe", "python.exe", "applicationframehost.exe",
    #                     "shellexperiencehost.exe", "lockapp.exe"
    #                 ]
    #                 visible_windows = []

    #                 def foreach_window(hwnd, lParam):
    #                     if user32.IsWindowVisible(hwnd):
    #                         length = user32.GetWindowTextLengthW(hwnd)
    #                         if length > 0:
    #                             buff = ctypes.create_unicode_buffer(length + 1)
    #                             user32.GetWindowTextW(hwnd, buff, length + 1)
    #                             visible_windows.append((hwnd, buff.value))
    #                     return True
                    
    #                 user32.EnumWindows(WNDENUMPROC(foreach_window), 0)

    #                 # Tập hợp các game đang chạy thực tế
    #                 current_running_games = set()
                    
    #                 for hwnd, title in visible_windows:
    #                     if not hwnd: continue
    #                     title_lower = title.lower()
                        
    #                     matched_game = None
    #                     matched_icon = ""

    #                     for game in GAME_LIST:
    #                         g_name = game['name']
    #                         pattern = r"\b" + re.escape(g_name.lower()) + r"\b"
    #                         if re.search(pattern, title_lower):
    #                             matched_game = g_name
    #                             matched_icon = game.get('icon', '')
    #                             break
                        
    #                     if not matched_game: continue

    #                     rect = wintypes.RECT()
    #                     user32.GetWindowRect(hwnd, ctypes.byref(rect))
    #                     w = rect.right - rect.left
    #                     h = rect.bottom - rect.top
    #                     if w < 600 or h < 400: continue

    #                     proc_name = get_process_name(hwnd)
    #                     if proc_name in IGNORED_APPS: continue

    #                     # ==> TÌM THẤY GAME
    #                     current_running_games.add(matched_game)
                        
    #                     # Nếu game này chưa có trong danh sách quản lý -> BẬT OVERLAY
    #                     if matched_game not in active_game_sessions:
    #                         hwnd_int = int(hwnd)
    #                         print(f"[DETECT] Game Start: {matched_game}")
                            
    #                         clean_icon = matched_icon.replace("\\", "/") if matched_icon else ""
                            
    #                         # Bật và lấy Process Object
    #                         # proc = launch_overlay_process(matched_game, clean_icon, rect.left, rect.top, hwnd_int)
                            
    #                         # if proc:
    #                         #     # Lưu vào Dictionary: { "Tên Game": Process_Object }
    #                         #     active_game_sessions[matched_game] = proc

    #                 # ==> KIỂM TRA GAME ĐÃ TẮT (AUTO-KILL)
    #                 # Duyệt qua các game đang được Overlay
    #                 for old_game in list(active_game_sessions.keys()):
    #                     if old_game not in current_running_games:
    #                         print(f"[DETECT] Game Stop: {old_game} -> Kill Overlay")
    #                         try:
    #                             # Lôi đầu Process ra và Kill
    #                             proc = active_game_sessions[old_game]
    #                             proc.kill() 
    #                         except: pass
                            
    #                         # Xóa khỏi Dictionary
    #                         del active_game_sessions[old_game]

    #             except Exception as e:
    #                 # print(f"Watcher Error: {e}") 
    #                 pass
                
    #             time.sleep(2)

    #     threading.Thread(target=worker, daemon=True).start()



# --- [FIX FINAL] QUẢN LÝ UI DOWNLOAD (REALTIME) ---

    # 1. Hai danh sách chứa thẻ (Biến toàn cục để hàm khác gọi được)
    # [QUAN TRỌNG] Phải khai báo 2 biến này trước khi dùng trong downloads_drawer
    global download_list_col, finished_list_col
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
    # --- [V21 FINAL FIX] CARD ĐÃ XONG (UNINSTALL + STEAM LINK + NO CRASH) ---
    def create_finished_card(name, icon_src, version, on_play_click):
        state = {"expanded": False}
        close_timer = [None]

        # UI Components
        progress_overlay = ft.Container(width=0, height=70, bgcolor="#BB000000", border_radius=12, animate=ft.Animation(300, "easeOut"))
        spinner = ft.ProgressRing(width=25, height=25, stroke_width=3, color="white", visible=False)
        status_txt = ft.Text("Sẵn sàng chơi", size=10, color="#888888", italic=True)

        # --- LOGIC CHỨC NĂNG ---
        def delete_game_logic(e):
            e.control.stop_propagation = True
            show_push_notification(f"Đang xóa {name}...", "warning")
            try:
                dl_dir = APP_CONFIG.get("download_dir")
                slug = clean_name_for_slug(name)
                targets = [os.path.join(dl_dir, slug), os.path.join(dl_dir, f"{slug}.zip")]
                deleted = False
                for p in targets:
                    if os.path.exists(p):
                        if os.path.isdir(p): shutil.rmtree(p)
                        else: os.remove(p)
                        deleted = True
                
                if deleted:
                    show_push_notification(f"Đã gỡ cài đặt {name}", "success")
                    main_card.visible = False
                    main_card.update()
                    if name in COMPLETED_GAMES: COMPLETED_GAMES.remove(name)
                else:
                    show_push_notification("Không tìm thấy file để xóa!", "error")
                    main_card.visible = False
                    main_card.update()
            except Exception as err: show_push_notification(f"Lỗi xóa: {err}", "error")

        def open_steam_info(e):
            e.control.stop_propagation = True
            game_obj = next((g for g in GAME_LIST if g['name'] == name), None)
            if not game_obj or not game_obj.get('lnd_url'): return show_push_notification("Không tìm thấy Link gốc!", "error")
            show_push_notification(f"Đang tìm link Steam...", "loading")
            def worker():
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    res = requests.get(game_obj['lnd_url'], headers=headers, timeout=8)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    steam_link_tag = soup.find('a', href=re.compile(r'store\.steampowered\.com/app/'))
                    if steam_link_tag:
                        webbrowser.open(steam_link_tag['href'])
                        show_push_notification("Đã tìm thấy! Đang mở...", "success")
                    else:
                        webbrowser.open(f"https://www.google.com/search?q={name} steam")
                        show_push_notification("Không có link Steam, đang tìm Google...", "warning")
                except: show_push_notification("Lỗi kết nối!", "error")
            threading.Thread(target=worker, daemon=True).start()

        def open_location_logic(e):
            e.control.stop_propagation = True
            dl_dir = APP_CONFIG.get("download_dir")
            slug = clean_name_for_slug(name)
            target = os.path.join(dl_dir, slug)
            if not os.path.exists(target): target = os.path.join(dl_dir, f"{slug}.zip")
            if not os.path.exists(target): target = dl_dir
            try: subprocess.Popen(f'explorer /select,"{os.path.abspath(target)}"')
            except: os.startfile(dl_dir)

        def check_update_logic(e):
            e.control.stop_propagation = True
            game_obj = next((g for g in GAME_LIST if g['name'] == name), None)
            if not game_obj: return
            show_push_notification(f"Đang check {name}...", "loading")
            def worker():
                ver = fetch_lnd_version(game_obj.get('lnd_url'))
                if ver != "Unknown" and not is_version_match_smart(ver, version):
                    show_push_notification(f"CÓ BẢN MỚI: {ver}", "warning")
                else: show_push_notification("Đang là bản mới nhất", "success")
            threading.Thread(target=worker, daemon=True).start()

        def share_game_logic(e):
            e.control.stop_propagation = True
            show_push_notification("Tính năng Chia sẻ đang được thực hiện...", "info")

        # --- UI LAYERS ---
        def create_vertical_btn(icon, text, color="white", on_click=None, show_arrow=False):
            return ft.Container(
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
                border_radius=8, bgcolor="transparent", on_click=on_click,
                on_hover=lambda e: (setattr(e.control, 'bgcolor', "#70FFFFFF" if e.data=="true" else "transparent") or e.control.update()),
                content=ft.Row([
                    ft.Icon(icon, size=20, color=color),
                    ft.Text(text, size=13, color="white", weight="bold"),
                    ft.Container(expand=True),
                    ft.Icon(ft.icons.CHEVRON_RIGHT, size=18, color="#888888") if show_arrow else ft.Container()
                ], alignment=ft.MainAxisAlignment.START)
            )

        def create_back_btn():
            return ft.Container(
                padding=10, margin=ft.margin.only(bottom=5), border_radius=5, bgcolor="#10FFFFFF",
                on_click=lambda e: slide_to_main(),
                on_hover=lambda e: (setattr(e.control, 'bgcolor', "#30FFFFFF" if e.data=="true" else "#10FFFFFF") or e.control.update()),
                content=ft.Row([ft.Icon(ft.icons.ARROW_BACK, size=16, color="cyan"), ft.Text("Quay lại Menu", size=12, color="cyan", weight="bold")])
            )

        # Layers
        view_main = ft.Container(
            offset=ft.Offset(0, 0), animate_offset=ft.Animation(400, "easeOutQuart"),
            content=ft.Column([
                ft.Divider(height=1, color="#333333"),
                create_vertical_btn(ft.icons.SETTINGS, "Cài đặt", "cyan", lambda e: prepare_and_slide("settings"), show_arrow=True),
                create_vertical_btn(ft.icons.DELETE_FOREVER, "Gỡ cài đặt", "#FF5252", delete_game_logic),
                create_vertical_btn(ft.icons.MORE_HORIZ, "Khác", "amber", lambda e: prepare_and_slide("more"), show_arrow=True),
            ], spacing=4)
        )
        
        sub_menu_content = ft.Column(spacing=4)
        view_sub = ft.Container(offset=ft.Offset(1.2, 0), animate_offset=ft.Animation(400, "easeOutQuart"), content=sub_menu_content)

        def prepare_and_slide(target):
            sub_menu_content.controls.clear()
            sub_menu_content.controls.append(create_back_btn())
            sub_menu_content.controls.append(ft.Divider(height=1, color="#333333"))
            if target == "settings":
                sub_menu_content.controls.append(create_vertical_btn(ft.icons.CLOUD_SYNC, "Kiểm tra cập nhật", "#4CAF50", check_update_logic))
                sub_menu_content.controls.append(create_vertical_btn(ft.icons.FOLDER_OPEN, "Mở thư mục game", "#2196F3", open_location_logic))
            elif target == "more":
                sub_menu_content.controls.append(create_vertical_btn(ft.icons.INFO, "Thông tin chi tiết", "white", open_steam_info))
                sub_menu_content.controls.append(create_vertical_btn(ft.icons.SHARE, "Chia sẻ game", "white", share_game_logic))
            view_main.offset = ft.Offset(-1.2, 0)
            view_sub.offset = ft.Offset(0, 0)
            view_main.update()
            view_sub.update()

        def slide_to_main():
            view_main.offset = ft.Offset(0, 0)
            view_sub.offset = ft.Offset(1.2, 0)
            view_main.update()
            view_sub.update()

        # Header (FIXED BUTTON CRASH)
        arrow_icon = ft.Icon(ft.icons.KEYBOARD_ARROW_DOWN, size=20, color="grey", rotate=ft.Rotate(0, alignment=ft.alignment.center), animate_rotation=ft.Animation(300, "easeOut"))
        
        # [FIX] Nút play sạch sẽ, không còn stop_propagation thừa thãi
        btn_play = ft.IconButton(ft.icons.PLAY_ARROW_ROUNDED, icon_color="green", icon_size=30, tooltip="Chơi ngay",
            on_click=lambda e: on_play_click(e, spinner, status_txt, e.control, progress_overlay))

        header_content = ft.Container(
            height=70, padding=ft.padding.symmetric(horizontal=10),
            content=ft.Row([
                ft.Image(src=icon_src, width=50, height=50, border_radius=8, fit=ft.ImageFit.COVER),
                ft.Column([
                    ft.Text(name, color="#88FF88", weight="bold", size=13),
                    ft.Text(f"Ver: {version}", size=10, color="grey"),
                    status_txt, 
                ], spacing=2, alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(expand=True), btn_play, spinner, ft.Container(content=arrow_icon, padding=5)
            ], alignment=ft.MainAxisAlignment.START)
        )

        # Main Card
        main_card = ft.Container(
            height=70, bgcolor="#CC151515", blur=ft.Blur(10, 10, ft.BlurTileMode.MIRROR),
            border_radius=12, clip_behavior=ft.ClipBehavior.HARD_EDGE, animate=ft.Animation(300, "easeOutBack"),
        )
        slider_wrapper = ft.Container(content=ft.Stack([view_main, view_sub]), padding=ft.padding.only(left=10, right=10, bottom=10), opacity=0, animate_opacity=200)

        def toggle_card(e):
            state["expanded"] = not state["expanded"]
            main_card.height = 220 if state["expanded"] else 70
            main_card.bgcolor = "#E6000000" if state["expanded"] else "#CC151515"
            slider_wrapper.opacity = 1 if state["expanded"] else 0
            arrow_icon.rotate.angle = 3.14 if state["expanded"] else 0
            if state["expanded"]: slide_to_main() # Reset về main
            main_card.update()
            slider_wrapper.update()
            arrow_icon.update()

        # [FIX] Hàm đóng tự động (Sửa lỗi setattr dict)
        def auto_close():
            state["expanded"] = False
            toggle_card(None)

        def on_hover_card(e):
            if e.data == "true":
                if close_timer[0]: close_timer[0].cancel()
                if not state["expanded"]: 
                    main_card.bgcolor = "#DD252525"
                    main_card.update()
            else:
                if not state["expanded"]: 
                    main_card.bgcolor = "#CC151515"
                    main_card.update()
                if state["expanded"]:
                    close_timer[0] = threading.Timer(0.4, auto_close)
                    close_timer[0].start()

        main_card.content = ft.Stack([
            ft.Container(content=progress_overlay, alignment=ft.alignment.top_left),
            ft.Column([header_content, slider_wrapper], spacing=0)
        ])
        main_card.on_click = toggle_card
        main_card.on_hover = on_hover_card
        return main_card


















    # 1. Overlay làm tối nền khi mở tab Download
    dl_overlay_blur = ft.Container(
        expand=True,
        bgcolor="#0D000000", # Đen mờ nhẹ
        blur=ft.Blur(10, 10, ft.BlurTileMode.MIRROR),
        opacity=0, visible=False,
        animate_opacity=300,
        on_click=lambda e: close_downloads_drawer() # Bấm ra ngoài là đóng
    )

    # 2. Logic Đóng/Mở Tab
    def open_downloads_drawer(e=None):
        # [NEW] Quét lại ổ cứng ngay khi mở tab
        scan_and_restore_downloaded_games()
        
        downloads_drawer.left = 0 
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























# --- [FIX] QUÉT FILE ZIP VÀ FOLDER CỰC MẠNH ---
    def scan_and_restore_downloaded_games():
        dl_dir = APP_CONFIG.get("download_dir")
        if not dl_dir or not os.path.exists(dl_dir): return

        # Xóa UI cũ
        finished_list_col.controls.clear()
        
        # Danh sách tạm để check trùng
        temp_completed_names = []

        # Duyệt qua danh sách game gốc
        for game in GAME_LIST:
            game_name = game['name']
            
            # Bỏ qua nếu đang tải dở
            if game_name in ACTIVE_DOWNLOADS: continue
            
            slug = clean_name_for_slug(game_name)
            
            # Kiểm tra 2 trường hợp:
            # 1. File Zip còn đó
            zip_path = os.path.join(dl_dir, f"{slug}.zip")
            # 2. Hoặc Thư mục game đã giải nén
            folder_path = os.path.join(dl_dir, slug)
            
            is_downloaded = False
            
            # Logic: Chỉ cần 1 trong 2 tồn tại là coi như có game
            if os.path.exists(zip_path):
                is_downloaded = True
            elif os.path.exists(folder_path) and os.path.isdir(folder_path):
                # Check kỹ hơn: Folder phải có ít nhất 1 file bên trong
                if len(os.listdir(folder_path)) > 0:
                    is_downloaded = True

            if is_downloaded:
                # Tạo thẻ đã xong
                card = create_finished_card(
                    game_name, 
                    game['icon'], 
                    game['version'],
                    # Truyền full tham số để nút Play hoạt động
                    lambda e, i, t, b, p, g_name=game_name, g_icon=game['icon']: handle_play_game(g_name, e, i, t, b, p, g_icon)
                )
                finished_list_col.controls.append(card)
                temp_completed_names.append(game_name)

        # Cập nhật lại danh sách hoàn thành toàn cục
        COMPLETED_GAMES.clear()
        COMPLETED_GAMES.extend(temp_completed_names)
        finished_list_col.update()

















    # --- [FIXED] TẢI GAME AN TOÀN (TRY-CATCH UI UPDATE) ---
    def trigger_download_process(game_data, is_update=False):
        game_name = game_data['name']
        
        if is_update:
            save_path = get_base_path()
        else:
            save_path = APP_CONFIG.get("download_dir")
        
        if not save_path:
            dir_picker.pending_game_data = game_data 
            dir_picker.get_directory_path("Chọn nơi lưu Game")
            return

        slug = clean_name_for_slug(game_name)
        
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

        ctrl_state = {"paused": False, "cancelled": False, "path": file_path}
        ACTIVE_DOWNLOADS[game_name] = ctrl_state
        
        page.run_task(run_download_anim)
        real_icon = game_data['icon']
        
        # --- LOGIC NÚT DỪNG & HỦY ---
        def toggle_pause(e):
            if not ctrl_state["cancelled"]:
                ctrl_state["paused"] = not ctrl_state["paused"]
                e.control.icon = ft.icons.PLAY_CIRCLE_FILLED if ctrl_state["paused"] else ft.icons.PAUSE_CIRCLE_FILLED
                e.control.icon_color = "green" if ctrl_state["paused"] else "yellow"
                e.control.tooltip = "Tiếp tục" if ctrl_state["paused"] else "Tạm dừng"
                e.control.update()

        def cancel_download(e):
            ctrl_state["cancelled"] = True
            try:
                if card_ui in download_list_col.controls:
                    download_list_col.controls.remove(card_ui)
                    download_list_col.update()
            except: pass

            if game_name in ACTIVE_DOWNLOADS: del ACTIVE_DOWNLOADS[game_name]
            
            try:
                if os.path.exists(file_path): os.remove(file_path)
            except: pass
            show_push_notification(f"Đã hủy {game_name}", "error")

        # Tạo UI Card
        card_ui, pb, txt_pct, txt_spd, btn_pause_ref = create_downloading_card_ui(
            game_name, real_icon, toggle_pause, cancel_download
        )
        
        # [FIX 1] Thêm thẻ vào UI và cập nhật ngay lập tức
        download_list_col.controls.insert(0, card_ui) 
        download_list_col.update()
        
        # [FIX 2] Chờ 0.2s để đảm bảo Flet đã vẽ xong thẻ này lên màn hình
        time.sleep(0.2)

        # [FIX 3] Hàm cập nhật UI an toàn (Chống Crash)
        def update_progress_ui(ratio, speed_str="0 MB/s"):
            if ctrl_state["cancelled"]: return
            try:
                # Nếu UI chưa kịp vẽ hoặc đã bị tắt -> Bỏ qua update này
                if pb.page: 
                    pb.value = ratio
                    pb.update()
                
                if txt_pct.page:
                    txt_pct.value = f"{int(ratio * 100)}%"
                    txt_pct.update()
                
                if txt_spd.page:
                    txt_spd.value = speed_str
                    txt_spd.update()
            except Exception:
                pass

        def download_thread():
            try:
                # Dọn dẹp bản cũ
                slug = clean_name_for_slug(game_name)
                extract_folder = os.path.join(save_path, slug)
                if os.path.exists(extract_folder):
                    try:
                        txt_pct.value = "XÓA BẢN CŨ..."
                        txt_pct.update()
                        shutil.rmtree(extract_folder) 
                    except: pass

                txt_pct.value = "Đang kết nối..."
                txt_pct.update()

                # BẮT ĐẦU TẢI
                success = download_file_with_state(
                    game_data['download_link'], 
                    file_path, 
                    update_progress_ui, 
                    ctrl_state,
                    game_name
                )
                
                if success and not ctrl_state["cancelled"]:
                    show_push_notification(f"Hoàn tất {game_name}!", "success")
                    winsound.MessageBeep()
                    
                    # Xóa thẻ tải an toàn
                    try:
                        if card_ui in download_list_col.controls:
                            download_list_col.controls.remove(card_ui)
                            download_list_col.update()
                    except: pass
                    
                    if game_name in ACTIVE_DOWNLOADS: del ACTIVE_DOWNLOADS[game_name]

                    if is_update:
                        handle_self_update(file_path)
                    else:
                        # [FIX] Đã sửa lambda truyền đủ tham số cho handle_play_game
                        finished_card = create_finished_card(
                            game_name, real_icon, game_data['version'],
                            lambda e, i, t, b, p, g_name=game_name, g_icon=real_icon: handle_play_game(g_name, e, i, t, b, p, g_icon)
                        )
                        finished_list_col.controls.insert(0, finished_card)
                        finished_list_col.update()
                        COMPLETED_GAMES.append(game_name)

                elif ctrl_state["cancelled"]:
                    pass 
                
                else:
                    # Xử lý lỗi tải
                    try:
                        txt_pct.value = "LỖI TẢI - HÃY XÓA"
                        txt_pct.color = "red"
                        txt_spd.value = "Check Link/Mạng"
                        pb.bgcolor = "#550000"
                        btn_pause_ref.visible = False
                        btn_pause_ref.update()
                        txt_pct.update()
                        txt_spd.update()
                        pb.update()
                    except: pass
                    
                    if game_name in ACTIVE_DOWNLOADS: del ACTIVE_DOWNLOADS[game_name]

            except Exception as e:
                print(f"Lỗi Thread Tải: {e}")
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

    # --- [FIX ORDER] 1. ĐỊNH NGHĨA HÀM ANIMATION TRƯỚC ---
    def animate_sidebar_btn(e):
        icon = e.control.content
        is_hover = e.data == "true"
        
        if icon.name == ft.icons.SETTINGS:
            icon.rotate.angle = 3.14 if is_hover else 0
        elif icon.name == ft.icons.HOME:
            icon.offset.y = -0.3 if is_hover else 0

        e.control.opacity = 1.0 if is_hover else 0.5 
        e.control.scale = 1.1 if is_hover else 1.0   
        icon.update()
        e.control.update()

    # --- [FIX ORDER] 2. ĐỊNH NGHĨA HÀM RESET HOME TRƯỚC ---
    def reset_to_home(e):
        search_box.value = ""
        search_box.update()
        run_search_logic("") 
        
        # Đóng sidebar
        sidebar_state["sidebar"] = False
        sidebar_state["trigger"] = False
        sidebar_container.offset = ft.Offset(1.1, 0)
        sidebar_blur_layer.opacity = 0
        sidebar_container.update()
        sidebar_blur_layer.update()
        
        def delayed_hide_blur():
            time.sleep(0.3)
            sidebar_blur_layer.visible = False
            try: page.update()
            except: pass
        threading.Thread(target=delayed_hide_blur, daemon=True).start()

    # --- [FIX ORDER] 3. BÂY GIỜ MỚI ĐỊNH NGHĨA NÚT BẤM ---
    # Nút Cài đặt
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
        on_hover=animate_sidebar_btn # Lúc này hàm đã tồn tại nên không lỗi nữa
    )

    # Nút Home
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
        on_click=reset_to_home, # Lúc này hàm đã tồn tại
        tooltip="Về trang chủ (Reset)",
        on_hover=animate_sidebar_btn
    )

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


    trigger_zone = ft.Container(
        data="trigger", 
        width=80,       # Rộng ra chút để dễ quẹt trúng
        height=250,     # Chiều cao giới hạn (Không full màn hình nữa)
        right=0, 
        bottom=0,       # [QUAN TRỌNG] Neo xuống đáy
        bgcolor=None,   # Trong suốt
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
            
            # --- HÀM CLICK MỚI (FIX ANIMATION) ---
            def on_download_click_safe(e):
                # 1. KÍCH HOẠT ANIMATION NGAY LẬP TỨC (Không quan tâm logic sau đó)
                if GLOBAL_GHOST_PREVIEW:
                    try:
                        # Lấy icon game
                        final_icon = game.get('icon', "")
                        if not final_icon: final_icon = "https://github.com/anhkhakl/Conist-Launcher-Update/raw/main/app_icon.ico"
                        
                        # GỌI SIDEBAR TRƯỢT RA
                        GLOBAL_GHOST_PREVIEW.trigger(game['name'], final_icon)
                    except: pass

                # 2. Đóng bảng chi tiết
                close_detail(None)
                
                # 3. GỌI LẠI QUY TRÌNH TẢI CŨ (Giữ nguyên logic gốc của bạn)
                # trigger_download_process là hàm gốc xử lý tải/check file/giải nén...
                threading.Thread(target=lambda: trigger_download_process(game), daemon=True).start()
            # --------------------------------------

            # Gán hàm mới vào nút
            btn_download_base.on_click = on_download_click_safe

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
    # ... (Các code phía trên trong hàm main) ...

    # 1. TẠO BIẾN GHOST PREVIEW (Đã có sẵn)
    global GLOBAL_GHOST_PREVIEW
    ghost_preview = GhostDownloadPreview()
    GLOBAL_GHOST_PREVIEW = ghost_preview
    
    # 2. [QUAN TRỌNG] KHỞI TẠO CHANGELOG TẠI ĐÂY (SỬA LỖI UNDEFINED)
    # Phải đặt dòng này TRƯỚC khi tạo main_layout và TRƯỚC các hàm gọi nó
    changelog_popup = ChangelogModal(page) 

    # 3. SAU ĐÓ MỚI ĐẾN MAIN LAYOUT
    main_layout = ft.Container(
        width=1280, height=720,
        clip_behavior=ft.ClipBehavior.HARD_EDGE, 
        content=ft.Stack([
            bg_container,       
            body_container,     
            game_detail_overlay,    
            sidebar_blur_layer,  
            trigger_zone,         
            sidebar_container,     
            blur_overlay,         
            settings_drawer,
            dl_trigger_zone,
            dl_overlay_blur,
            downloads_drawer,
            dl_anim_box,
            coord_container,
            
            # Các lớp phủ
            ghost_preview,
            changelog_popup, # <--- Biến này giờ đã được định nghĩa ở trên, hết lỗi
            notification_stack,
            sleep_overlay       
        ], expand=True),
        
        opacity=0, 
        animate_opacity=ft.Animation(800, "easeOut"),
    )
# --- [BỔ SUNG] HÀM XỬ LÝ PHÍM TẮT (ĐÃ BỊ THIẾU) ---
    def on_global_keyboard(e: ft.KeyboardEvent):
        # 1. TAB: Mở/Đóng Kho Tải
        if e.key == "7" and (e.ctrl or e.meta):
            changelog_popup.show() # Gọi hàm hiện bảng
        if e.key == "Tab":
            # [FIX MỚI] Nếu Ghost Tab đang hiện -> Tắt nó NGAY LẬP TỨC
            if GLOBAL_GHOST_PREVIEW and GLOBAL_GHOST_PREVIEW.visible:
                GLOBAL_GHOST_PREVIEW.hide_fast()

            # Sau đó chạy logic mở kho tải to như bình thường
            if settings_drawer.offset.x > 0 and game_detail_overlay.offset.y > 0:
                if downloads_drawer.left < 0:
                    open_downloads_drawer()
                else:
                    close_downloads_drawer()

        # 2. Ctrl + 9: Chế độ ngủ
        if e.key == "9" and (e.ctrl or e.meta): 
            go_to_sleep()

    # Kích hoạt trình lắng nghe (Dòng này sẽ hết lỗi vì hàm đã có ở trên)
    page.on_keyboard_event = on_global_keyboard
    
    # Thêm giao diện vào trang
    page.add(main_layout)


















    # -----------------------------------------------------------
    # [FIX FINAL V2] KHỞI ĐỘNG AN TOÀN TUYỆT ĐỐI
    # -----------------------------------------------------------
    
    # 1. Tạo màn hình chờ (Bắt buộc phải có biến này trước)
    # Lưu ý: Hàm lambda ở đây chỉ set giá trị, không gọi update để tránh lỗi
    splash = SplashLoader(page, lambda: setattr(page.window, 'always_on_top', False))

    # 2. Định nghĩa quy trình khởi động
    async def run_startup():
        global RAW_GAME_DATA
        
        # Chạy hiệu ứng Loading
        try: await splash.animate_loading()
        except: pass
        
        # --- [FIX CRASH] ---
        # Tắt chế độ luôn ở trên cùng để người dùng Alt+Tab được
        try:
            page.window.always_on_top = False
            page.update() 
        except: pass

        # Hiện giao diện chính
        bg_container.opacity = 1
        main_layout.opacity = 1
        page.update()

        # Fix kích thước (Chống màn hình đen)
        try:
            current_w = page.window.width
            current_h = page.window.height
            page.window.width = current_w + 1
            page.window.height = current_h + 1
            page.update()
            await asyncio.sleep(0.05)
            page.window.width = 1280
            page.window.height = 720
            page.update()
        except: pass
        
        # Tải Data mới
        print("[STARTUP] Đang kiểm tra cập nhật danh sách game...")
        try:
            splash.msg_txt.value = "Đang đồng bộ dữ liệu..."
            splash.page.update()
        except: pass

        success = await asyncio.to_thread(download_data_direct)
        
        if success:
            print("[STARTUP] Đã tải xong data mới.")
            if os.path.exists(LOCAL_DATA_PATH):
                try:
                    with open(LOCAL_DATA_PATH, "r", encoding="utf-8") as f:
                        content = f.read()
                        if len(content) > 10:
                            RAW_GAME_DATA = ast.literal_eval(content)
                            # Lúc này gọi hàm vẽ là an toàn
                            refresh_data_and_grid() 
                except: pass

        # Kích hoạt tải ảnh ngầm
        threading.Thread(target=bg_download_icons, daemon=True).start()

   


        # 5. Check Update App (Logic: Server > Local)
        print("[UPDATE] Bắt đầu kiểm tra phiên bản...")
        try:
            def fetch_update_data_sync():
                timestamp = int(time.time())
                RAW_URL = f"https://raw.githubusercontent.com/anhkhakl/Conist-Launcher-Update/main/version.json?t={timestamp}"
                return requests.get(RAW_URL, timeout=5).json()

            data = await asyncio.to_thread(fetch_update_data_sync)
            
            server_ver = str(data.get("latest_version", "0.0.0")).strip()
            download_url = data.get("download_url", "")
            
            print(f"[UPDATE] Server: '{server_ver}' | Local: '{CURRENT_VERSION}'")

            # Hàm so sánh: Trả về True nếu Ver A > Ver B
            def is_newer(ver_a, ver_b):
                try:
                    a = [int(x) for x in re.findall(r'\d+', str(ver_a))]
                    b = [int(x) for x in re.findall(r'\d+', str(ver_b))]
                    return a > b
                except: return False

            # CHỈ BÁO NẾU SERVER MỚI HƠN MÁY
            if is_newer(server_ver, CURRENT_VERSION):
                print(f"[UPDATE] => CÓ BẢN MỚI! ({server_ver} > {CURRENT_VERSION})")
                if download_url:
                    await asyncio.sleep(1) 
                    show_push_notification(
                        f"Đã có phiên bản mới v{server_ver}", 
                        type="update", 
                        key="update_alert",
                        duration=300000, 
                        on_click_action=lambda: start_self_update(download_url, server_ver)
                    )
            else:
                # Nếu Server BẰNG hoặc NHỎ HƠN Local -> Im lặng tuyệt đối
                print(f"[UPDATE] Không cần update.")
                
        except Exception as e:
            print(f"[UPDATE ERROR] Lỗi kiểm tra: {e}")
        except: pass
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
        try:
            await asyncio.sleep(1)
            changelog_popup.check_and_show_once()
        except: pass
        page.update()
        # ---------------------------------------------------

    # --- KHỞI CHẠY ---
    # 1. Hiện giao diện ngay lập tức
    bg_container.opacity = 1
    page.update()



    # --- WORKER: Tải Ảnh + Check Steam (Đã tích hợp lấy Logo Steam) ---
    def process_single_icon(g):
        has_new = False
        try:
            slug = clean_name_for_slug(g['name'])
            local_path = os.path.join(ICON_FOLDER, f"{slug}.jpg")
            
            # Kiểm tra xem cần làm gì? (Thiếu ảnh HOẶC Thiếu info Online)
            is_icon_missing = not os.path.exists(local_path) or os.path.getsize(local_path) < 1024
            is_mp_missing = g.get('mp_status', 'Unknown') in ['Unknown', 'Checking...']
            has_link = g.get('lnd_url') and len(str(g.get('lnd_url'))) > 10

            if has_link and (is_icon_missing or is_mp_missing):
                # GỌI HYBRID ENGINE 1 LẦN DUY NHẤT (Lấy cả Ảnh + Info)
                full_info = fetch_full_details(g['lnd_url'])
                
                if full_info:
                    # 1. Tải Ảnh (Nếu thiếu)
                    if is_icon_missing and full_info.get('icon'):
                        # Tải từ link Steam (hoặc LND fallback) về máy
                        if download_icon(full_info['icon'], local_path):
                            g['icon'] = local_path
                            has_new = True
                    
                    # 2. Cập nhật Online/Offline (Nếu thiếu)
                    if is_mp_missing:
                        new_mp = full_info.get('mp_status', 'Offline')
                        if g.get('mp_status') != new_mp:
                            g['mp_status'] = new_mp
                            has_new = True

            # Nếu ảnh vẫn chưa tải được nhưng có file cũ -> dùng tạm
            if not is_icon_missing and os.path.exists(local_path):
                if g.get('icon') != local_path:
                    g['icon'] = local_path
            
            # 3. CẬP NHẬT UI
            if has_new:
                try:
                    for card in grid.controls:
                        if card.game['name'] == g['name']:
                            card.refresh_ui()
                            break
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
        
        # [NÂNG CẤP] Logic update UI mượt mà hơn
        if changed:
            print("[FLASH] Đã cập nhật xong cache ảnh.")
            save_cache()
            # Chỉ update Grid 1 lần duy nhất sau khi tải xong tất cả
            try:
                grid.update() 
            except: pass



    def idle_checker():
        while True:
            if time.time() - state["last_interaction"] > IDLE_TIMEOUT:
                go_to_sleep()
            time.sleep(1)

    threading.Thread(target=idle_checker, daemon=True).start()
    threading.Thread(target=bg_download_icons, daemon=True).start()
    # start_global_game_watcher()
    if APP_CONFIG.get("auto_update_games", False):
        # Lúc này đang ở trong hàm main nên nó mới nhìn thấy process_game_updates_thread
        threading.Thread(target=process_game_updates_thread, daemon=True).start()















# 3. Kích hoạt App (Dán vào cuối hàm main, thay thế các dòng cũ)
    try:
        # Gọi quy trình khởi động
        page.run_task(run_startup)
    except Exception as e:
        print(f"Lỗi Startup: {e}")
        # Cứu hộ khẩn cấp: Nếu startup lỗi thì ép hiện giao diện
        page.window.always_on_top = False
        bg_container.opacity = 1
        main_layout.opacity = 1
        page.update()




# [Thay thế toàn bộ đoạn cuối cùng của file test.txt]

if __name__ == "__main__":
    # 1. Fix Icon Taskbar (Chỉ hiệu quả khi chạy source code)
    try:
        myappid = 'conist.link.launcher.v2.live' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except: pass
    
    # 2. Khóa Mutex (Chống mở 2 Launcher cùng lúc)
    mutex_id = "Global\\Conist_Launcher_v2_Unique_Lock"
    try:
        mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_id)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == 183: # ERROR_ALREADY_EXISTS
            sys.exit(0)
    except: pass
    
    # 3. Chạy App Flet
    ft.app(target=main, assets_dir=BASE_DATA_PATH)
