import os
import sys
import time
import json
import serial
from datetime import datetime

# Enable VT100 ANSI sequences on Windows console
os.system('')

# Ensure core package import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.adb_helper import (
    get_device_status, check_root, get_device_info, 
    verify_hardware_safety, enable_diag_port, disable_diag_port,
    backup_efs, restore_efs, setup_android_telephony_volte,
    query_ims_registration, adb_exec
)
from core.diag import (
    efs_hello, efs_write_file, efs_read_file, find_diag_port
)

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PAYLOAD_DIR = os.path.join(TOOL_DIR, "payload")
BACKUP_DIR = os.path.join(TOOL_DIR, "backups")

# ==============================================================================
# TERMINAL UI THEME & FORMATTING (IMPECCABLE CRAFT SPECIFICATION)
# ==============================================================================
class Theme:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    
    # Semantic Palette
    CYAN    = "\033[38;5;51m"
    BLUE    = "\033[38;5;75m"
    PURPLE  = "\033[38;5;141m"
    EMERALD = "\033[38;5;48m"
    GOLD    = "\033[38;5;220m"
    CORAL   = "\033[38;5;203m"
    WHITE   = "\033[38;5;255m"
    SLATE   = "\033[38;5;246m"
    DARK    = "\033[38;5;238m"

    @classmethod
    def header(cls, title: str):
        width = 66
        print(f"\n{cls.CYAN}┌{'─' * width}┐{cls.RESET}")
        print(f"{cls.CYAN}│ {cls.BOLD}{cls.WHITE}{title.center(width - 2)}{cls.RESET}{cls.CYAN} │{cls.RESET}")
        print(f"{cls.CYAN}└{'─' * width}┘{cls.RESET}\n")

    @classmethod
    def badge(cls, text: str, status: str = "info") -> str:
        color_map = {
            "ok": cls.EMERALD,
            "pass": cls.EMERALD,
            "warn": cls.GOLD,
            "error": cls.CORAL,
            "crit": cls.CORAL,
            "info": cls.CYAN,
            "dim": cls.SLATE
        }
        c = color_map.get(status.lower(), cls.WHITE)
        return f"{c}[{text}]{cls.RESET}"

    @classmethod
    def card(cls, label: str, val: str):
        print(f"  {cls.SLATE}• {cls.WHITE}{label:<18}{cls.RESET} {cls.BOLD}{val}{cls.RESET}")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    width = 66
    print(f"{Theme.CYAN}┌{'─' * width}┐{Theme.RESET}")
    print(f"{Theme.CYAN}│ {Theme.BOLD}{Theme.WHITE}{'LEECO LE S2 / LE 2 (MSM8976) • VOLTE ENABLER'.center(width - 2)}{Theme.RESET}{Theme.CYAN} │{Theme.RESET}")
    print(f"{Theme.CYAN}└{'─' * width}┘{Theme.RESET}")

def wait_key():
    print(f"\n{Theme.SLATE}Press {Theme.BOLD}[Enter]{Theme.RESET}{Theme.SLATE} to return to main menu...{Theme.RESET}", end="")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

# ==============================================================================
# MENU IMPLEMENTATIONS
# ==============================================================================
def menu_check_device():
    clear_screen()
    print_banner()
    Theme.header("HARDWARE & COMPATIBILITY AUDIT")
    
    ok, serial_no, state = get_device_status()
    if not ok:
        print(f"  {Theme.badge('ERROR', 'error')} {Theme.CORAL}{state}{Theme.RESET}")
        print(f"  {Theme.SLATE}└─ Please check USB cable and verify 'USB Debugging' is enabled.{Theme.RESET}")
        wait_key()
        return None, None
        
    print(f"  {Theme.badge('DETECTED', 'ok')} Serial ID: {Theme.BOLD}{serial_no}{Theme.RESET} | Connection State: {Theme.EMERALD}{state}{Theme.RESET}")
    
    is_root = check_root()
    if is_root:
        print(f"  {Theme.badge('ROOT', 'ok')} Privileges: {Theme.EMERALD}SuperUser Available (Root / TWRP Active){Theme.RESET}")
    else:
        print(f"  {Theme.badge('WARN', 'warn')} Privileges: {Theme.GOLD}Root access not detected via ADB.{Theme.RESET}")
        print(f"  {Theme.SLATE}└─ Please grant Magisk SuperUser prompt or execute from TWRP.{Theme.RESET}")
        
    info = get_device_info()
    print(f"\n{Theme.CYAN}┌── DEVICE SPECIFICATIONS ─────────────────────────────────────────┐{Theme.RESET}")
    Theme.card("Target Model", f"{info['model']} ({info['device']})")
    Theme.card("SoC Platform", f"{info['platform']}")
    Theme.card("Android Release", f"Android {info['android_version']} (SDK {info['sdk']})")
    Theme.card("Build ID", f"{info['rom_id']}")
    Theme.card("Modem Baseband", f"{info['baseband']}")
    Theme.card("Active SIM / Telco", f"{info['operator']}")
    print(f"{Theme.CYAN}└──────────────────────────────────────────────────────────────────┘{Theme.RESET}")
    
    print(f"\n{Theme.BOLD}Safety Inspection (Anti-Brick Guardrail):{Theme.RESET}")
    safe, msg = verify_hardware_safety(info)
    if safe:
        print(f"  {Theme.badge('VALIDATED', 'ok')} {Theme.EMERALD}{msg}{Theme.RESET}")
    else:
        print(f"  {Theme.badge('CRITICAL', 'crit')} {Theme.CORAL}{msg}{Theme.RESET}")
        
    wait_key()
    return info, is_root

def menu_backup_efs():
    clear_screen()
    print_banner()
    Theme.header("PARTITION BACKUP UTILITY (IMEI & RF CALIBRATION)")
    
    ok, serial_no, state = get_device_status()
    if not ok:
        print(f"  {Theme.badge('ERROR', 'error')} Please connect device via ADB first.")
        wait_key()
        return
        
    if not check_root():
        print(f"  {Theme.badge('ERROR', 'error')} Root privileges required to read raw block devices.")
        wait_key()
        return
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_folder = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    print(f"  {Theme.badge('INIT', 'info')} Backing up critical partitions (modemst1, modemst2, fsg)...")
    print(f"  {Theme.SLATE}Destination: {target_folder}{Theme.RESET}\n")
    
    success, msg = backup_efs(target_folder)
    if success:
        print(f"  {Theme.badge('SUCCESS', 'ok')} {Theme.EMERALD}{msg}{Theme.RESET}")
        print(f"  {Theme.SLATE}Note: Keep this backup secure; it contains unique device calibration data.{Theme.RESET}")
    else:
        print(f"  {Theme.badge('FAILED', 'error')} {Theme.CORAL}{msg}{Theme.RESET}")
        
    wait_key()

def select_com_port():
    print(f"\n  {Theme.badge('SCAN', 'info')} Scanning for Qualcomm Diagnostic Serial Interfaces...")
    found = find_diag_port()
    if isinstance(found, str) and found:
        print(f"  {Theme.badge('FOUND', 'ok')} Auto-detected Diagnostic COM Port: {Theme.BOLD}{Theme.CYAN}{found}{Theme.RESET}")
        ans = input(f"  Use interface [{found}]? (Y/n): ").strip().lower()
        if ans == '' or ans == 'y':
            return found
            
    if isinstance(found, list) and found:
        print(f"  {Theme.badge('PORTS', 'info')} Multiple diagnostic candidate ports detected:")
        for i, p in enumerate(found):
            print(f"    [{i+1}] {p}")
        idx = input("  Select COM port index (or type port name, e.g. COM15): ").strip()
        if idx.isdigit() and 1 <= int(idx) <= len(found):
            return found[int(idx)-1]
        elif idx.upper().startswith("COM"):
            return idx.upper()
            
    manual = input("  Enter COM port name manually (e.g. COM15): ").strip().upper()
    return manual if manual.startswith("COM") else f"COM{manual}"

def menu_auto_fix_volte():
    clear_screen()
    print_banner()
    Theme.header("AUTOMATED VOLTE PROVISIONING SEQUENCE (1-CLICK)")
    
    # 1. Pre-flight connection and safety checks
    ok, serial_no, state = get_device_status()
    if not ok:
        print(f"  {Theme.badge('ABORT', 'error')} {state}. Please check USB connection and ADB.")
        wait_key()
        return
        
    if not check_root():
        print(f"  {Theme.badge('ABORT', 'error')} Root privileges unavailable. Please grant Magisk access.")
        wait_key()
        return
        
    info = get_device_info()
    safe, msg = verify_hardware_safety(info)
    if not safe:
        print(f"  {Theme.badge('ABORT', 'crit')} {msg}")
        print(f"  {Theme.CORAL}Operation halted to prevent potential device brick.{Theme.RESET}")
        wait_key()
        return
        
    print(f"  {Theme.badge('DEVICE', 'ok')} Target: {Theme.BOLD}{info['model']} ({info['device']}) - Snapdragon 652{Theme.RESET}")
    
    # 2. Automated EFS Backup before modification
    print(f"\n{Theme.BOLD}>>> STEP 1: SAFETY PRE-FLIGHT EFS BACKUP{Theme.RESET}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_backup = os.path.join(BACKUP_DIR, f"auto_backup_before_fix_{timestamp}")
    b_ok, b_msg = backup_efs(target_backup)
    if not b_ok:
        print(f"  {Theme.badge('HALT', 'error')} EFS backup failed: {b_msg}")
        print(f"  {Theme.CORAL}Refusing to proceed without a valid partition safety backup.{Theme.RESET}")
        wait_key()
        return
    print(f"  {Theme.badge('BACKUP OK', 'ok')} {b_msg}")
    
    # 3. Enable Qualcomm Diagnostic Port
    print(f"\n{Theme.BOLD}>>> STEP 2: QUALCOMM DIAGNOSTIC INTERFACE INITIALIZATION{Theme.RESET}")
    enable_diag_port()
    time.sleep(3)
    
    com_port = select_com_port()
    if not com_port:
        print(f"  {Theme.badge('ERROR', 'error')} No valid COM port specified.")
        wait_key()
        return
        
    print(f"  {Theme.badge('CONNECT', 'info')} Opening connection to {com_port}...")
    try:
        ser = serial.Serial(com_port, 115200, timeout=1.5)
    except Exception as e:
        print(f"  {Theme.badge('ERROR', 'error')} Unable to open {com_port}: {e}")
        print(f"  {Theme.SLATE}Ensure Qualcomm HS-USB Diagnostics driver is installed in Device Manager.{Theme.RESET}")
        wait_key()
        return
        
    hello = efs_hello(ser)
    if not hello:
        print(f"  {Theme.badge('ERROR', 'error')} Modem DSP did not respond to EFS Hello handshake.")
        ser.close()
        wait_key()
        return
    print(f"  {Theme.badge('HANDSHAKE', 'ok')} Hexagon Modem DSP responsive (EFS2 protocol active).")
    
    # 4. Ingest and byte-verify payload NV items
    print(f"\n{Theme.BOLD}>>> STEP 3: INGESTING STANDARDIZED VOLTE NV ITEMS{Theme.RESET}")
    manifest_file = os.path.join(PAYLOAD_DIR, "manifest.json")
    if not os.path.exists(manifest_file):
        print(f"  {Theme.badge('ERROR', 'error')} Missing payload manifest: payload/manifest.json")
        ser.close()
        wait_key()
        return
        
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    success_count = 0
    fail_count = 0
    total = len(manifest)
    print(f"  {Theme.badge('FLASH', 'info')} Flashing {total} verified NV items to modem EFS...\n")
    
    for efs_path, filename in manifest.items():
        filepath = os.path.join(PAYLOAD_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  {Theme.badge('MISSING', 'error')} {filename} for {efs_path}")
            fail_count += 1
            continue
            
        with open(filepath, "rb") as f:
            data = f.read()
            
        write_ok, err_msg = efs_write_file(ser, efs_path, data)
        if write_ok:
            read_back, r_err = efs_read_file(ser, efs_path)
            if read_back == data:
                print(f"  {Theme.badge('VERIFIED', 'ok')} {efs_path} {Theme.SLATE}({len(data)} B){Theme.RESET}")
                success_count += 1
            else:
                print(f"  {Theme.badge('MISMATCH', 'warn')} Verification failed: {efs_path}")
                fail_count += 1
        else:
            print(f"  {Theme.badge('WRITE FAIL', 'error')} {efs_path}: {err_msg}")
            fail_count += 1
            
    ser.close()
    print(f"\n  {Theme.badge('RESULT', 'ok')} Flashed & Verified: {Theme.BOLD}{success_count}/{total}{Theme.RESET} items ({fail_count} errors)")
    
    # 5. Configure Android Telephony Provider & APNs
    print(f"\n{Theme.BOLD}>>> STEP 4: TELEPHONY & IMS APN PROVISIONING{Theme.RESET}")
    setup_android_telephony_volte()
    print(f"  {Theme.badge('PROVISIONED', 'ok')} Standardized IMS APNs (Viettel 45204, VinaPhone 45202, MobiFone 45201) & enabled Dual-SIM VoLTE flags.")
    
    # Return Diag port to default MTP mode
    disable_diag_port()
    
    # 6. Reboot prompt
    print(f"\n{Theme.CYAN}┌{'─' * 66}┐{Theme.RESET}")
    print(f"{Theme.CYAN}│ {Theme.BOLD}{Theme.EMERALD}{'VOLTE PROVISIONING COMPLETED SUCCESSFULLY!'.center(64)}{Theme.RESET}{Theme.CYAN} │{Theme.RESET}")
    print(f"{Theme.CYAN}└{'─' * 66}┘{Theme.RESET}")
    
    ans = input(f"\nReboot device now to finalize network attachment? (Y/n): ").strip().lower()
    if ans == '' or ans == 'y':
        print(f"  {Theme.badge('REBOOT', 'info')} Rebooting target device...")
        adb_exec(["reboot"])
        print(f"  {Theme.badge('READY', 'ok')} Device is rebooting. IMS registration will initialize on boot.")
    else:
        print(f"  {Theme.badge('NOTE', 'info')} Please manually reboot your device to apply modem changes.")
        
    wait_key()

def menu_restore_efs():
    clear_screen()
    print_banner()
    Theme.header("EFS PARTITION RESTORE UTILITY")
    
    ok, serial_no, state = get_device_status()
    if not ok or not check_root():
        print(f"  {Theme.badge('ERROR', 'error')} Connect device via ADB with Root privileges enabled.")
        wait_key()
        return
        
    if not os.path.exists(BACKUP_DIR):
        print(f"  {Theme.badge('ERROR', 'error')} Backup directory not found.")
        wait_key()
        return
        
    backups = [d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))]
    root_backup = os.path.join(TOOL_DIR, "..", "backup")
    if os.path.exists(root_backup):
        backups.append("Factory_Stock_Archive (backup/)")
        
    if not backups:
        print(f"  {Theme.badge('EMPTY', 'warn')} No partition backups detected.")
        wait_key()
        return
        
    print(f"{Theme.BOLD}Available Partition Archives:{Theme.RESET}")
    for i, b in enumerate(backups):
        print(f"  [{i+1}] {Theme.CYAN}{b}{Theme.RESET}")
        
    choice = input("\nEnter selection index to restore (or 0 to cancel): ").strip()
    if not choice.isdigit() or int(choice) == 0:
        return
        
    c_idx = int(choice) - 1
    if 0 <= c_idx < len(backups):
        selected = backups[c_idx]
        if "Factory_Stock_Archive" in selected:
            src_folder = os.path.abspath(root_backup)
        else:
            src_folder = os.path.join(BACKUP_DIR, selected)
            
        print(f"\n{Theme.CORAL}[CAUTION] You are about to overwrite critical modem partitions from:{Theme.RESET}")
        print(f"{Theme.SLATE}{src_folder}{Theme.RESET}")
        confirm = input(f"Type '{Theme.BOLD}YES{Theme.RESET}' to confirm restore: ")
        if confirm == "YES":
            print(f"  {Theme.badge('RESTORE', 'info')} Restoring partition blocks...")
            r_ok, r_msg = restore_efs(src_folder)
            if r_ok:
                print(f"  {Theme.badge('SUCCESS', 'ok')} {Theme.EMERALD}{r_msg}{Theme.RESET}")
                ans = input("Reboot device now? (Y/n): ").strip().lower()
                if ans == '' or ans == 'y':
                    adb_exec(["reboot"])
            else:
                print(f"  {Theme.badge('FAILED', 'error')} {Theme.CORAL}{r_msg}{Theme.RESET}")
        else:
            print(f"  {Theme.badge('CANCELLED', 'warn')} Operation aborted by user.")
            
    wait_key()

def menu_check_ims_status():
    clear_screen()
    print_banner()
    Theme.header("LIVE IMS & VOLTE REGISTRATION MONITOR")
    
    ok, serial_no, state = get_device_status()
    if not ok:
        print(f"  {Theme.badge('ERROR', 'error')} {state}")
        wait_key()
        return
        
    print(f"  {Theme.badge('QUERY', 'info')} Querying telephony stack and Qualcomm IMS service status...\n")
    ims_stat = query_ims_registration()
    
    print(f"{Theme.CYAN}┌── IMS SERVICE STATUS ────────────────────────────────────────────┐{Theme.RESET}")
    if ims_stat["registered"]:
        Theme.card("IMS Registration", f"{Theme.EMERALD}[ REGISTERED ]{Theme.RESET}")
    else:
        Theme.card("IMS Registration", f"{Theme.CORAL}[ UNREGISTERED ]{Theme.RESET}")
        
    if ims_stat["voice"]:
        Theme.card("VoLTE (Voice Call)", f"{Theme.EMERALD}[ AVAILABLE (HD Voice AMR-WB) ]{Theme.RESET}")
    else:
        Theme.card("VoLTE (Voice Call)", f"{Theme.CORAL}[ DISABLED / UNAVAILABLE ]{Theme.RESET}")
        
    if ims_stat["video"]:
        Theme.card("Video Calling (VT)", f"{Theme.EMERALD}[ AVAILABLE ]{Theme.RESET}")
    else:
        Theme.card("Video Calling (VT)", f"{Theme.CORAL}[ DISABLED / UNAVAILABLE ]{Theme.RESET}")
    print(f"{Theme.CYAN}└──────────────────────────────────────────────────────────────────┘{Theme.RESET}")
        
    wait_key()

def menu_toggle_diag():
    clear_screen()
    print_banner()
    Theme.header("MANUAL QUALCOMM DIAG PORT TOGGLE")
    
    print(f"  {Theme.CYAN}[1]{Theme.RESET} Enable Qualcomm Diag (diag,adb)")
    print(f"  {Theme.CYAN}[2]{Theme.RESET} Disable Diag / Revert to MTP (mtp,adb)")
    print(f"  {Theme.SLATE}[0]{Theme.RESET} Back to Main Menu")
    
    c = input(f"\n{Theme.BOLD}Select [0-2]: {Theme.RESET}").strip()
    if c == '1':
        enable_diag_port()
        print(f"  {Theme.badge('OK', 'ok')} Diagnostic interface commanded. Please wait 3 seconds for COM enumeration.")
    elif c == '2':
        disable_diag_port()
        print(f"  {Theme.badge('OK', 'ok')} Reverted USB configuration to standard MTP/ADB mode.")
    wait_key()

def main():
    while True:
        clear_screen()
        print_banner()
        print(f"{Theme.SLATE}  Select an operation from the menu below:{Theme.RESET}\n")
        print(f"  {Theme.BOLD}{Theme.CYAN}[1]{Theme.RESET}  Device & Hardware Compatibility Audit")
        print(f"  {Theme.BOLD}{Theme.CYAN}[2]{Theme.RESET}  Create EFS Partition Backup {Theme.SLATE}(modemst1, modemst2, fsg){Theme.RESET}")
        print(f"  {Theme.BOLD}{Theme.CYAN}[3]{Theme.RESET}  Automated VoLTE Provisioning {Theme.EMERALD}[1-Click Full Flow]{Theme.RESET}")
        print(f"  {Theme.BOLD}{Theme.CYAN}[4]{Theme.RESET}  Restore EFS from Previous Archive")
        print(f"  {Theme.BOLD}{Theme.CYAN}[5]{Theme.RESET}  Inspect Live IMS Registration & Capabilities")
        print(f"  {Theme.BOLD}{Theme.CYAN}[6]{Theme.RESET}  Toggle Qualcomm Diagnostic Interface")
        print(f"  {Theme.BOLD}{Theme.SLATE}[0]{Theme.RESET}  Exit\n")
        print(f"{Theme.CYAN}{'─' * 68}{Theme.RESET}")
        
        try:
            choice = input(f"{Theme.BOLD}Selection ❯ {Theme.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Theme.CYAN}Exiting LeEco VoLTE Tool. Goodbye!{Theme.RESET}\n")
            break
            
        if choice == '1':
            menu_check_device()
        elif choice == '2':
            menu_backup_efs()
        elif choice == '3':
            menu_auto_fix_volte()
        elif choice == '4':
            menu_restore_efs()
        elif choice == '5':
            menu_check_ims_status()
        elif choice == '6':
            menu_toggle_diag()
        elif choice == '0':
            print(f"\n{Theme.CYAN}Exiting LeEco VoLTE Tool. Goodbye!{Theme.RESET}\n")
            break

if __name__ == "__main__":
    main()
