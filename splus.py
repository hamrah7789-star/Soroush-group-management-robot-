#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import zipfile
import tempfile
import shutil
import asyncio
import traceback
import subprocess
import importlib
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ============================================================
# ⚙️ تنظیمات
# ============================================================

# لینک مستقیم فایل splus.zip (نه کل پروژه!)
ZIP_URL = "https://github.com/hamrah7789-star/Soroush-group-management-robot-/raw/main/splus.zip"

# مسیر دائمی برای دیتابیس‌ها (کنار خود این فایل)
PERSISTENT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data"
)

ZIP_NAME = "splus.zip"

# 📚 کتابخانه‌هایی که ربات سروش معمولاً نیاز داره
# اگه بعداً ارور ModuleNotFoundError گرفتی، اسم ماژول رو به این لیست اضافه کن
REQUIRED_MODULES = [
    "requests",
    "websockets",
    "pyaes",
    "rsa",
    "jdatetime",
    "nest_asyncio",
    "flask",  # بعضی ربات‌های سروش از flask برای پنل وب استفاده می‌کنن
]

# ============================================================
# 🌈 رنگ‌ها برای خروجی زیباتر
# ============================================================
class Colors:
    G = '\033[92m'  # سبز
    R = '\033[91m'  # قرمز
    Y = '\033[93m'  # زرد
    B = '\033[94m'  # آبی
    C = '\033[96m'  # فیروزه‌ای
    X = '\033[0m'   # ریست

def p(text, color=Colors.X):
    print(f"{color}{text}{Colors.X}")


# ============================================================
# 📚 نصب خودکار کتابخانه‌ها
# ============================================================

def check_module(module_name: str) -> bool:
    """چک میکنه آیا یه ماژول نصب هست یا نه"""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def install_pip(module_name: str) -> bool:
    """یه ماژول رو با pip نصب میکنه"""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", module_name],
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def ensure_requirements():
    """همه‌ی کتابخانه‌های لازم رو چک و در صورت نیاز نصب میکنه"""
    p("\n📚 چک کردن کتابخانه‌های مورد نیاز...", Colors.B)
    for mod in REQUIRED_MODULES:
        if check_module(mod):
            p(f"   ✅ {mod} نصب است", Colors.G)
        else:
            p(f"   ⏳ {mod} نصب نیست — در حال نصب...", Colors.Y)
            if install_pip(mod):
                p(f"   ✅ {mod} نصب شد", Colors.G)
            else:
                p(f"   ❌ نصب {mod} شکست خورد (شاید لازم نباشه)", Colors.R)


# ============================================================
# 🌐 دانلود
# ============================================================

def download_zip(url: str, dest_path: str) -> bool:
    """دانلود فایل zip از لینک"""
    p(f"\n🌐 در حال دانلود از:\n   {url}", Colors.B)
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
                        print(
                            f"\r   ⬇️  {percent:5.1f}% "
                            f"({downloaded:,}/{total:,} بایت)",
                            end="", flush=True,
                        )

            print()
            p(f"✅ دانلود کامل شد ({downloaded:,} بایت)", Colors.G)
            return True

    except HTTPError as e:
        p(f"❌ خطای HTTP: {e.code} — {e.reason}", Colors.R)
        return False
    except URLError as e:
        p(f"❌ خطای اتصال: {e.reason}", Colors.R)
        return False
    except Exception as e:
        p(f"❌ خطا در دانلود: {e}", Colors.R)
        return False


# ============================================================
# 📦 استخراج توی RAM
# ============================================================

def extract_to_ram(zip_path: str) -> str:
    """فایل zip رو توی یه پوشه موقت (RAM) استخراج میکنه."""
    tmp_root = tempfile.gettempdir()
    p(f"💾 پوشه موقت (RAM): {tmp_root}", Colors.C)

    extract_dir = tempfile.mkdtemp(prefix="soroush_bot_", dir=tmp_root)
    p(f"📂 پوشه استخراج: {extract_dir}", Colors.C)

    p("📦 در حال استخراج...", Colors.B)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # چک امنیتی path traversal
            for member in zf.namelist():
                member_path = os.path.realpath(os.path.join(extract_dir, member))
                if not member_path.startswith(os.path.realpath(extract_dir)):
                    raise Exception(f"⚠️ مسیر ناامن در zip: {member}")

            zf.extractall(extract_dir)
        p("✅ استخراج کامل شد", Colors.G)
        return extract_dir

    except zipfile.BadZipFile:
        p("❌ فایل zip خرابه!", Colors.R)
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None
    except Exception as e:
        p(f"❌ خطا در استخراج: {e}", Colors.R)
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None


# ============================================================
# 🔧 پیدا کردن main.py
# ============================================================

def find_main_py(extract_dir: str):
    """main.py رو توی پوشه استخراج‌شده پیدا میکنه."""
    direct = os.path.join(extract_dir, "main.py")
    if os.path.isfile(direct):
        return extract_dir

    for root, dirs, files in os.walk(extract_dir):
        if "main.py" in files:
            return root

    return None


# ============================================================
# 💾 مدیریت دیتابیس‌های دائمی
# ============================================================

def setup_persistent_data(bot_dir: str):
    """دیتابیس‌های دائمی رو به RAM کپی میکنه"""
    os.makedirs(PERSISTENT_DATA_DIR, exist_ok=True)

    ram_data_dir = os.path.join(bot_dir, "data")
    os.makedirs(ram_data_dir, exist_ok=True)

    p("📥 کپی دیتابیس‌های قبلی به RAM...", Colors.B)
    copied = 0
    for item in os.listdir(PERSISTENT_DATA_DIR):
        src = os.path.join(PERSISTENT_DATA_DIR, item)
        dst = os.path.join(ram_data_dir, item)
        try:
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                copied += 1
        except Exception as e:
            p(f"   ⚠️ خطا در کپی {item}: {e}", Colors.Y)

    if copied:
        p(f"   ✅ {copied} فایل کپی شد", Colors.G)
    else:
        p("   ℹ️ دیتابیس قبلی نداشتیم", Colors.C)


def save_persistent_data(bot_dir: str):
    """دیتابیس‌های RAM رو به مسیر دائمی برمیگردونه"""
    ram_data_dir = os.path.join(bot_dir, "data")
    if not os.path.isdir(ram_data_dir):
        return

    p("📤 ذخیره دیتابیس‌ها به حافظه اصلی...", Colors.B)
    saved = 0
    for item in os.listdir(ram_data_dir):
        src = os.path.join(ram_data_dir, item)
        dst = os.path.join(PERSISTENT_DATA_DIR, item)
        try:
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                saved += 1
        except Exception as e:
            p(f"   ⚠️ خطا در ذخیره {item}: {e}", Colors.Y)

    if saved:
        p(f"   ✅ {saved} فایل ذخیره شد", Colors.G)
    else:
        p("   ℹ️ فایلی برای ذخیره نبود", Colors.C)


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
            if mod_name in (
                "config", "bot", "database", "main", "bot2", "bot3",
                "user_data_manager", "owner_manager", "rules_manager",
            ):
                del sys.modules[mod_name]

        p("\n🚀 در حال اجرا main.py...", Colors.B)
        p("=" * 60, Colors.C)

        import main as bot_main

        if hasattr(bot_main, "main"):
            await bot_main.main()

    finally:
        os.chdir(original_cwd)
        sys.path = original_sys_path


# ============================================================
# 🎬 اجرای اصلی
# ============================================================

def main():
    p("=" * 60, Colors.C)
    p("🤖 ربات سروش — اجرا از روی RAM (با نصب خودکار کتابخانه‌ها)", Colors.C)
    p("=" * 60, Colors.C)

    zip_path = None
    extract_dir = None
    bot_dir = None

    try:
        # 0. نصب کتابخانه‌های مورد نیاز
        ensure_requirements()

        # 1. دانلود
        tmp_dir = tempfile.mkdtemp(prefix="soroush_zip_")
        zip_path = os.path.join(tmp_dir, ZIP_NAME)

        if not download_zip(ZIP_URL, zip_path):
            p("❌ دانلود شکست خورد!", Colors.R)
            return 1

        # 2. استخراج توی RAM
        extract_dir = extract_to_ram(zip_path)
        if not extract_dir:
            p("❌ استخراج شکست خورد!", Colors.R)
            return 1

        # 3. پیدا کردن main.py
        bot_dir = find_main_py(extract_dir)
        if not bot_dir:
            p("❌ main.py پیدا نشد!", Colors.R)
            p("📄 لیست فایل‌های استخراج‌شده برای دیباگ:", Colors.Y)
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    p(f"   - {os.path.join(root, f)}", Colors.Y)
            return 1
        p(f"✅ main.py پیدا شد: {bot_dir}", Colors.G)

        # 4. کپی دیتابیس‌های قبلی به RAM
        setup_persistent_data(bot_dir)

        # 5. اجرای ربات
        try:
            asyncio.run(run_bot(bot_dir))
        except KeyboardInterrupt:
            p("\n🛑 متوقف شد", Colors.Y)
        except Exception as e:
            p(f"\n❌ خطا در اجرا: {e}", Colors.R)
            traceback.print_exc()

        # 6. ذخیره دیتابیس‌ها
        save_persistent_data(bot_dir)

        p("\n✅ دیتابیس‌ها ذخیره شدن. همه فایل‌های موقت پاک میشن.", Colors.G)

    finally:
        p("🧹 پاک کردن فایل‌های موقت...", Colors.B)

        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                p("   ✅ zip حذف شد", Colors.G)
            except Exception:
                pass

        if extract_dir and os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
            p("   ✅ پوشه استخراج حذف شد", Colors.G)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        p("\n🛑 متوقف شد", Colors.Y)
        sys.exit(0)
    except Exception as e:
        p(f"\n❌ خطای غیرمنتظره: {e}", Colors.R)
        traceback.print_exc()
        sys.exit(1)