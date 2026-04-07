#!/usr/bin/env python3
import os
import sys
import zipfile
import shutil
import subprocess
import requests
from pathlib import Path
from bs4 import BeautifulSoup

# Advanced dependency check for SD detection
try:
    import psutil
except ImportError:
    psutil = None

# --- CONFIGURATION & GLOBALS ---
MYRIENT_URL = "https://myrient.erista.me/files/Redump/Nintendo%20-%20Wii%20-%20Disc%20Images%20(USA)/"
CUSTOM_DEST_PATH = None

def show_splash():
    print("\033[96m" + """
    =========================================
      WIILINK & MYRIENT INSTALLER v4.3
    =========================================
    """ + "\033[0m")

def print_progress(current, total, prefix='', length=40):
    if total <= 0: return
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}%')
    sys.stdout.flush()
    if current >= total: print()

def get_active_destination():
    global CUSTOM_DEST_PATH
    if CUSTOM_DEST_PATH: return CUSTOM_DEST_PATH
    if psutil:
        for p in psutil.disk_partitions():
            if 'removable' in p.opts or p.fstype.lower() in ['vfat', 'fat32', 'msdos']:
                if "/boot" not in p.mountpoint: return Path(p.mountpoint)
    user = os.getlogin()
    for p in [Path(f"/media/{user}"), Path(f"/run/media/{user}")]:
        if p.exists():
            mounts = [m for m in p.iterdir() if m.is_dir()]
            if mounts: return mounts[0]
    return None

def search_and_download_myrient():
    dest_path = get_active_destination() or Path.home() / "Downloads"
    print(f"\n--- Connecting to Myrient ---")
    try:
        response = requests.get(MYRIENT_URL, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Get all links and clean them up
        links = [a.get('href') for a in soup.find_all('a') if a.get('href')]
        
        query = input("\nEnter game name (e.g., 'mario' or 'zelda'): ").strip().lower()
        
        # FUZZY SEARCH logic: matches if your word is ANYWHERE in the filename
        results = []
        for link in links:
            if link.startswith('?') or link.startswith('/'): continue
            if query in link.lower():
                results.append(link)
        
        if not results:
            print(f"\033[91mNo games found matching '{query}'. Try a shorter keyword like 'Wii'.\033[0m")
            return

        # Show top 20 results
        print(f"\nFound {len(results)} matches:")
        for i, res in enumerate(results[:20]): 
            # Clean up %20 and other URL characters for display
            clean_name = requests.utils.unquote(res)
            print(f"{i+1}: {clean_name}")
        
        choice = input("\nSelect number (q to cancel): ")
        if choice.lower() == 'q': return
        target_file = results[int(choice) - 1]
        
        dl_save = Path.home() / "Downloads" / requests.utils.unquote(target_file)
        
        print(f"\nDownloading: {dl_save.name}")
        with requests.get(MYRIENT_URL + target_file, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            with open(dl_save, 'wb') as f:
                done = 0
                for chunk in r.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
                    done += len(chunk)
                    print_progress(done, total, prefix='Download')
        
        if dl_save.suffix == '.zip': 
            handle_extraction_and_conversion(dl_save, dest_path)
        else:
            convert_to_wbfs(dl_save, dest_path)
            
    except Exception as e: 
        print(f"Error during search/download: {e}")

def handle_extraction_and_conversion(zip_path, final_dest):
    temp_dir = Path.home() / "Downloads" / "temp_wii"
    temp_dir.mkdir(exist_ok=True)
    try:
        print(f"\n--- Extracting ZIP ---")
        with zipfile.ZipFile(zip_path, 'r') as z:
            iso_list = [n for n in z.namelist() if n.lower().endswith(('.iso', '.nkit.iso'))]
            if not iso_list: 
                print("No ISO found in ZIP."); return
            iso_name = iso_list[0]
            total = z.getinfo(iso_name).file_size
            with z.open(iso_name) as source, open(temp_dir / iso_name, "wb") as target:
                done = 0
                while True:
                    chunk = source.read(1024*1024)
                    if not chunk: break
                    target.write(chunk)
                    done += len(chunk)
                    print_progress(done, total, prefix='Extracting')
        
        convert_to_wbfs(temp_dir / iso_name, final_dest)
        (temp_dir / iso_name).unlink()
        zip_path.unlink()
        temp_dir.rmdir()
    except Exception as e: print(f"\nProcessing failed: {e}")

def convert_to_wbfs(iso_path, final_dest):
    if shutil.which("wit") is None:
        print("\033[91mError: 'wit' not found. Ensure Wiimms ISO Tools is installed.\033[0m")
        return
    wbfs_dir = final_dest / "wbfs"
    wbfs_dir.mkdir(exist_ok=True)
    try:
        print(f"\n--- Checking Game ID ---")
        game_id = subprocess.check_output(["wit", "ID6", str(iso_path)]).decode().strip()
        dest_file = wbfs_dir / f"{game_id}.wbfs"
        print(f"Converting to: {dest_file.name}...")
        subprocess.run(["wit", "copy", "--wbfs", str(iso_path), str(dest_file)], check=True)
        print(f"\033[92mSuccess! Game installed.\033[0m")
    except Exception as e: print(f"WIT Error: {e}")

def show_menu():
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        show_splash()
        active_path = get_active_destination()
        print(f"Current Destination: \033[92m{active_path or 'Downloads Folder'}\033[0m")
        print("\n1: Install WiiLink Assets\n2: Search & Download Games\n3: Set Custom Path\n4: Local ISO to WBFS\n5: Exit")
        c = input("\nSelect: ")
        if c == '1': print("Checking WiiLink assets...")
        elif c == '2': search_and_download_myrient()
        elif c == '3':
            path_input = input("\nEnter full path (or 'clear'): ").strip()
            global CUSTOM_DEST_PATH
            if path_input.lower() == 'clear': CUSTOM_DEST_PATH = None
            else: CUSTOM_DEST_PATH = Path(path_input)
        elif c == '4':
            iso = Path(input("Enter path to ISO: ").strip())
            if iso.exists(): convert_to_wbfs(iso, active_path or Path.home() / "Downloads")
        elif c == '5': break
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    show_menu()
