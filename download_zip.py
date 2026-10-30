import os
import sys
import zipfile
import tempfile
import shutil
import asyncio
import traceback
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ============================================================
# ⚙️ تنظیمات
# ============================================================

# لینک مستقیم فایل splus.zip (نه کل پروژه!)
ZIP_URL = "https://github.com/hamrah7789-star/Soroush-group-management-robot-/raw/main/splus.zip"

# مسیر دائمی برای دیتابیس‌ها (کنار خود bootstrap.py)
PERSISTENT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data"
)

ZIP_NAME = "splus.zip"


# ============================================================
# 🌐 دانلود
# ============================================================

def download_zip(url: str, dest_path: str) -> bool:
    """دانلود فایل zip از لینک"""
    print(f"🌐 در حال دانلود از: {url}")
    try:
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (SoroushBot)"
        })
        with urlopen(req, timeout=60) as response:
            total = response.headers.get("Content-Length")
            total = int(total) if total else 0
            
            downloaded = 0
            chunk_size = 64 * 1024  # 64KB
            
            with open(dest_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total > 0:
                        percent = (downloaded / total) * 100
                        print(f"\r   ⬇️  {percent:5.1f}% ({downloaded:,}/{total:,} بایت)",
                              end="", flush=True)
            
            print()  # خط جدید
            print(f"✅ دانلود کامل شد ({downloaded:,} بایت)")
            return True
    
    except HTTPError as e:
        print(f"❌ خطای HTTP: {e.code} — {e.reason}")
        return False
    except URLError as e:
        print(f"❌ خطای اتصال: {e.reason}")
        return False
    except Exception as e:
        print(f"❌ خطا در دانلود: {e}")
        return False


# ============================================================
# 📦 استخراج توی RAM
# ============================================================

def extract_to_ram(zip_path: str) -> str:
    """فایل zip رو توی یه پوشه موقت (RAM) استخراج میکنه."""
    tmp_root = tempfile.gettempdir()
    print(f"💾 پوشه موقت (RAM): {tmp_root}")
    
    extract_dir = tempfile.mkdtemp(prefix="soroush_bot_", dir=tmp_root)
    print(f"📂 پوشه استخراج: {extract_dir}")
    
    print("📦 در حال استخراج...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                member_path = os.path.realpath(os.path.join(extract_dir, member))
                if not member_path.startswith(os.path.realpath(extract_dir)):
                    raise Exception(f"⚠️ مسیر ناامن در zip: {member}")
            
            zf.extractall(extract_dir)
        print(f"✅ استخراج کامل شد")
        return extract_dir
    
    except zipfile.BadZipFile:
        print("❌ فایل zip خرابه!")
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None
    except Exception as e:
        print(f"❌ خطا در استخراج: {e}")
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None


# ============================================================
# 🔧 پیدا کردن main.py
# ============================================================

def find_main_py(extract_dir: str):
    """
    main.py رو توی پوشه استخراج‌شده پیدا میکنه.
    """
    # حالت 1: مستقیم توی extract_dir
    direct = os.path.join(extract_dir, "main.py")
    if os.path.isfile(direct):
        return extract_dir
    
    # حالت 2: توی یه زیرپوشه (مثل splus/)
    for root, dirs, files in os.walk(extract_dir):
        if "main.py" in files:
            return root
    
    return None


# ============================================================
# 💾 مدیریت دیتابیس‌های دائمی
# ============================================================

def setup_persistent_data(bot_dir: str):
    """پوشه data رو توی RAM با پوشه دائمی sync میکنه."""
    os.makedirs(PERSISTENT_DATA_DIR, exist_ok=True)
    
    ram_data_dir = os.path.join(bot_dir, "data")
    os.makedirs(ram_data_dir, exist_ok=True)
    
    print("📥 کپی دیتابیس‌های قبلی به RAM...")
    copied = 0
    for item in os.listdir(PERSISTENT_DATA_DIR):
        src = os.path.join(PERSISTENT_DATA_DIR, item)
        dst = os.path.join(ram_data_dir, item)
        try:
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                copied += 1
        except Exception as e:
            print(f"   ⚠️ خطا در کپی {item}: {e}")
    
    if copied:
        print(f"   ✅ {copied} فایل کپی شد")
    else:
        print("   ℹ️ دیتابیس قبلی نداشتیم")


def save_persistent_data(bot_dir: str):
    """دیتابیس‌های RAM رو به مسیر دائمی برمیگردونه"""
    ram_data_dir = os.path.join(bot_dir, "data")
    if not os.path.isdir(ram_data_dir):
        return
    
    print("📤 ذخیره دیتابیس‌ها به حافظه اصلی...")
    saved = 0
    for item in os.listdir(ram_data_dir):
        src = os.path.join(ram_data_dir, item)
        dst = os.path.join(PERSISTENT_DATA_DIR, item)
        try:
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                saved += 1
        except Exception as e:
            print(f"   ⚠️ خطا در ذخیره {item}: {e}")
    
    if saved:
        print(f"   ✅ {saved} فایل ذخیره شد")
    else:
        print("   ℹ️ فایلی برای ذخیره نبود")


# ============================================================
# 🚀 اجرای main.py
# ============================================================

async def run_bot(bot_dir: str):
    """main.py رو توی پوشه مشخص اجرا میکنه"""
    original_cwd = os.getcwd()
    original_sys_path = sys.path.copy()
    
    try:
        os.chdir(bot_dir)
        sys.path.insert(0, bot_dir)
        
        # پاک کردن ماژول‌های کش‌شده
        for mod_name in list(sys.modules.keys()):
            if mod_name in ("config", "bot", "database", "main", "bot2", "bot3",
                            "user_data_manager", "owner_manager", "rules_manager"):
                del sys.modules[mod_name]
        
        print("🚀 در حال اجرا main.py...")
        print("=" * 60)
        
        import main as bot_main
        
        if hasattr(bot_main, "main"):
            await bot_main.main()
        else:
            pass
    
    finally:
        os.chdir(original_cwd)
        sys.path = original_sys_path


# ============================================================
# 🎬 اجرای اصلی
# ============================================================

def main():
    print("=" * 60)
    print("🤖 ربات سروش — اجرا از روی RAM")
    print("=" * 60)
    print()
    
    zip_path = None
    extract_dir = None
    bot_dir = None
    
    try:
        # 1. دانلود
        tmp_dir = tempfile.mkdtemp(prefix="soroush_zip_")
        zip_path = os.path.join(tmp_dir, ZIP_NAME)
        
        if not download_zip(ZIP_URL, zip_path):
            print("❌ دانلود شکست خورد!")
            return 1
        
        # 2. استخراج توی RAM
        extract_dir = extract_to_ram(zip_path)
        if not extract_dir:
            print("❌ استخراج شکست خورد!")
            return 1
        
        # 3. پیدا کردن main.py
        bot_dir = find_main_py(extract_dir)
        if not bot_dir:
            print("❌ main.py پیدا نشد!")
            # برای دیباگ، لیست فایل‌ها رو چاپ کن
            print("📄 فایل‌های استخراج شده:")
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    print(f"   - {os.path.join(root, f)}")
            return 1
        print(f"✅ main.py پیدا شد: {bot_dir}")
        
        # 4. کپی دیتابیس‌های قبلی به RAM
        setup_persistent_data(bot_dir)
        
        # 5. اجرای main.py
        try:
            asyncio.run(run_bot(bot_dir))
        except KeyboardInterrupt:
            print("\n🛑 متوقف شد")
        except Exception as e:
            print(f"\n❌ خطا در اجرا: {e}")
            traceback.print_exc()
        
        # 6. ذخیره دیتابیس‌ها به حافظه اصلی
        save_persistent_data(bot_dir)
        
        print()
        print("✅ دیتابیس‌ها ذخیره شدن. همه فایل‌های موقت پاک میشن.")
    
    finally:
        print("🧹 پاک کردن فایل‌های موقت...")
        
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                print("   ✅ zip حذف شد")
            except:
                pass
        
        if extract_dir and os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
            print("   ✅ پوشه استخراج حذف شد")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n🛑 متوقف شد")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ خطای غیرمنتظره: {e}")
        traceback.print_exc()
        sys.exit(1)