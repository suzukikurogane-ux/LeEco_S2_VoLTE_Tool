import subprocess
import os
import sys
import time
import re

def get_adb_path():
    # 1. Project platform-tools directory
    p1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "platform-tools", "adb.exe"))
    if os.path.exists(p1):
        return p1
    # 2. Bundled platform-tools directory inside tool
    p2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "platform-tools", "adb.exe"))
    if os.path.exists(p2):
        return p2
    # 3. System PATH
    return "adb"

ADB_BIN = get_adb_path()

def run_cmd(cmd_list, timeout=30):
    try:
        res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, encoding='utf-8', errors='ignore')
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def adb_exec(args, timeout=30):
    cmd = [ADB_BIN] + args
    return run_cmd(cmd, timeout=timeout)

def adb_shell(cmd_str, as_root=True, timeout=30):
    if as_root:
        # Try direct execution first (if adbd is running as root), otherwise fallback to su -c
        full_cmd = f"su -c '{cmd_str}'"
        rc, out, err = adb_exec(["shell", full_cmd], timeout=timeout)
        if rc == 0 and "not found" not in err.lower() and "permission denied" not in err.lower():
            return rc, out, err
        # Fallback to direct execution
        return adb_exec(["shell", cmd_str], timeout=timeout)
    else:
        return adb_exec(["shell", cmd_str], timeout=timeout)

def get_device_status():
    rc, out, err = adb_exec(["devices"])
    if rc != 0:
        return False, "", "Unable to execute ADB binary"
    
    device_lines = []
    found_header = False
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        if "List of devices attached" in line:
            found_header = True
            continue
        if found_header:
            parts = line.split()
            if len(parts) >= 2:
                device_lines.append((parts[0], parts[1]))
            
    if not device_lines:
        return False, "", "No connected Android devices detected"
    return True, device_lines[0][0], device_lines[0][1]

def check_root():
    rc, out, err = adb_shell("id", as_root=True)
    if "uid=0(root)" in out:
        return True
    # Try adb root
    adb_exec(["root"])
    time.sleep(1)
    rc, out, err = adb_shell("id", as_root=False)
    return "uid=0(root)" in out

def get_device_info():
    props = {}
    rc, out, err = adb_shell("getprop", as_root=False)
    if rc == 0:
        for line in out.splitlines():
            m = re.match(r'\[(.*?)\]: \[(.*?)\]', line)
            if m:
                props[m.group(1)] = m.group(2)
                
    info = {
        "model": props.get("ro.product.model", "Unknown"),
        "device": props.get("ro.product.device", props.get("ro.product.system.device", "Unknown")),
        "platform": props.get("ro.board.platform", "Unknown"),
        "android_version": props.get("ro.build.version.release", "Unknown"),
        "sdk": props.get("ro.build.version.sdk", "Unknown"),
        "rom_id": props.get("ro.build.display.id", "Unknown"),
        "baseband": props.get("gsm.version.baseband", "Unknown"),
        "operator": props.get("gsm.sim.operator.alpha", "Unknown")
    }
    return info

def verify_hardware_safety(info):
    """
    Absolute hardware safety verification prior to executing low-level modifications
    """
    platform = info.get("platform", "").lower()
    model = info.get("model", "").lower()
    device = info.get("device", "").lower()
    baseband = info.get("baseband", "").lower()
    
    # 1. Strictly block MediaTek platforms (e.g. LeEco Le 2 X620 / Helio X20)
    if "mt" in platform or "helio" in platform:
        return False, f"CRITICAL HAZARD: Target device uses MediaTek platform ({platform}), NOT Qualcomm Snapdragon! Operation aborted to prevent bricking."
        
    # 2. Check LeEco S2 / Le 2 model lineage (X520, X526, X527, X528, X52X)
    supported_names = ["s2", "le_s2", "le_s2_ww", "superior_s2", "x520", "x526", "x527", "x528", "x52x", "le2", "le 2"]
    is_known_s2 = any(name in device or name in model for name in supported_names)
    
    # 3. Verify Qualcomm Snapdragon 652 / MSM8976 architecture:
    # Note: On custom AOSP/LineageOS ROMs for LeEco S2, Qualcomm HAL frequently aliases the BSP to 'msm8952'
    is_qualcomm_s2_soc = (platform in ["msm8976", "msm8952", "msm8956"]) or ("8976" in baseband)
    
    if not is_qualcomm_s2_soc:
        return False, f"WARNING: Target device uses platform {platform} (unverified for Snapdragon 652 / MSM8976)."
        
    if is_known_s2:
        return True, f"Fully compatible: {info.get('model')} ({info.get('device')}) - Snapdragon 652 (MSM8976)"
    else:
        return True, f"Qualcomm MSM8976 platform confirmed, but device model is {model}/{device}. Proceed with caution."

def enable_diag_port():
    # Attempt direct root and setprop
    adb_exec(["root"])
    adb_shell("setprop sys.usb.config diag,adb", as_root=True)
    time.sleep(2)
    return True

def disable_diag_port():
    adb_shell("setprop sys.usb.config mtp,adb", as_root=True)
    return True

def get_by_name_dir():
    """
    Automatically resolve by-name partition directory across Android versions (A8/A9/A10/A11)
    """
    candidates = [
        "/dev/block/bootdevice/by-name",
        "/dev/block/platform/soc/7824900.sdhci/by-name",
        "/dev/block/platform/soc.0/7824900.sdhci/by-name",
        "/dev/block/platform/7824900.sdhci/by-name"
    ]
    for c in candidates:
        rc, out, _ = adb_shell(f"[ -d {c} ] && echo 1 || echo 0", as_root=True)
        if "1" in out:
            return c
    return "/dev/block/bootdevice/by-name"

def backup_efs(dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    by_name_dir = get_by_name_dir()
    partitions = ["modemst1", "modemst2", "fsg"]
    backed_up = []
    
    for part in partitions:
        remote_path = f"/sdcard/{part}.img"
        dev_path = f"{by_name_dir}/{part}"
        
        # Dump partition via dd
        rc, out, err = adb_shell(f"dd if={dev_path} of={remote_path} bs=4096", as_root=True)
        if rc != 0:
            return False, f"Failed to dump partition {part}: {err}"
            
        # Pull to PC
        local_file = os.path.join(dest_dir, f"{part}.img")
        rc, out, err = adb_exec(["pull", remote_path, local_file])
        adb_shell(f"rm -f {remote_path}", as_root=True)
        
        if not os.path.exists(local_file) or os.path.getsize(local_file) < 1000000:
            return False, f"Backup file {part}.img is invalid or truncated!"
        backed_up.append(part)
        
    return True, f"Successfully backed up {len(backed_up)} partitions ({', '.join(backed_up)}) to {dest_dir}"

def restore_efs(src_dir):
    partitions = ["modemst1", "modemst2", "fsg"]
    by_name_dir = get_by_name_dir()
    for part in partitions:
        local_file = os.path.join(src_dir, f"{part}.img")
        if not os.path.exists(local_file):
            return False, f"Missing required partition file {part}.img in backup directory!"
            
    for part in partitions:
        local_file = os.path.join(src_dir, f"{part}.img")
        remote_path = f"/sdcard/{part}.img"
        dev_path = f"{by_name_dir}/{part}"
        
        # Push to device
        rc, out, err = adb_exec(["push", local_file, remote_path])
        if rc != 0:
            return False, f"Failed to transfer {part}.img to device!"
            
        # Overwrite partition via dd
        rc, out, err = adb_shell(f"dd if={remote_path} of={dev_path} bs=4096", as_root=True)
        adb_shell(f"rm -f {remote_path}", as_root=True)
        if rc != 0:
            return False, f"Failed to flash partition {part}: {err}"
            
    return True, "Successfully restored original EFS partitions!"

def setup_android_telephony_volte():
    """
    Configure VoLTE flags in siminfo and inject IMS APNs by pulling, modifying, and pushing telephony.db.
    Automatically adapts to all Android versions (7/8/9/10/11/12).
    """
    import sqlite3
    import tempfile
    
    # 1. Set System & Persist Props (Universal for Qualcomm MSM)
    props = [
        ("persist.dbg.ims_volte_enable", "1"),
        ("persist.dbg.volte_avail_ovr", "1"),
        ("persist.radio.calls.on.ims", "1"),
        ("persist.vendor.radio.volte_switch", "1"),
        ("persist.radio.is_wps_over_ims", "1")
    ]
    for k, v in props:
        adb_shell(f"setprop {k} {v}", as_root=True)
        
    # 2. Locate telephony.db across Android generations
    db_candidates = [
        "/data/user_de/0/com.android.providers.telephony/databases/telephony.db",
        "/data/data/com.android.providers.telephony/databases/telephony.db"
    ]
    target_remote_db = None
    for p in db_candidates:
        rc, out, err = adb_shell(f"[ -f {p} ] && echo 1 || echo 0", as_root=True)
        if "1" in out:
            target_remote_db = p
            break
            
    if not target_remote_db:
        return False
        
    temp_dir = tempfile.gettempdir()
    local_db = os.path.join(temp_dir, "telephony_tool_patch.db")
    remote_tmp = "/sdcard/telephony_temp.db"
    
    adb_shell(f"cp {target_remote_db} {remote_tmp}", as_root=True)
    adb_exec(["pull", remote_tmp, local_db])
    adb_shell(f"rm -f {remote_tmp}", as_root=True)
    
    if not os.path.exists(local_db):
        return False
        
    try:
        conn = sqlite3.connect(local_db)
        c = conn.cursor()
        
        # 3. Check actual schema columns in siminfo table (adapts to A8, A9, A10, A11)
        c.execute("PRAGMA table_info(siminfo)")
        available_sim_cols = [r[1] for r in c.fetchall()]
        
        sim_updates = []
        for col in ["volte_vt_enabled", "vt_ims_enabled", "wfc_ims_enabled"]:
            if col in available_sim_cols:
                sim_updates.append(f"{col}=1")
                
        if sim_updates:
            # Enable for all SIMs (Slot 1 & Slot 2)
            c.execute(f"UPDATE siminfo SET {', '.join(sim_updates)}")
        
        # 4. Check actual schema columns in carriers table (APN)
        c.execute("PRAGMA table_info(carriers)")
        available_cols = [r[1] for r in c.fetchall()]
        
        # Remove old IMS APNs to insert clean, updated records
        c.execute("DELETE FROM carriers WHERE apn='ims' OR type='ims'")
        
        # Get next available ID
        c.execute("SELECT MAX(_id) FROM carriers")
        max_id_row = c.fetchone()
        next_id = (max_id_row[0] or 3500) + 1
        
        # Predefined major carriers (Vietnam)
        carriers_to_add = [
            {"name": "Viettel IMS", "numeric": "45204", "mcc": "452", "mnc": "04", "carrier_id": 1899},
            {"name": "VinaPhone IMS", "numeric": "45202", "mcc": "452", "mnc": "02", "carrier_id": 1900},
            {"name": "MobiFone IMS", "numeric": "45201", "mcc": "452", "mnc": "01", "carrier_id": 1901},
        ]
        
        # Dynamically detect active SIM operator if not in default carrier list
        rc_num, curr_sim_numeric, _ = adb_shell("getprop gsm.sim.operator.numeric", as_root=False)
        curr_num = curr_sim_numeric.strip().split(",")[0].strip()
        if curr_num and len(curr_num) >= 5 and curr_num not in ["45204", "45202", "45201"]:
            rc_name, curr_sim_name, _ = adb_shell("getprop gsm.sim.operator.alpha", as_root=False)
            sim_label = curr_sim_name.strip().split(",")[0].strip() or "Carrier"
            carriers_to_add.append({
                "name": f"{sim_label} IMS",
                "numeric": curr_num,
                "mcc": curr_num[:3],
                "mnc": curr_num[3:],
                "carrier_id": 1
            })
            
        for carr in carriers_to_add:
            desired_values = {
                "_id": next_id,
                "name": carr["name"],
                "numeric": carr["numeric"],
                "mcc": carr["mcc"],
                "mnc": carr["mnc"],
                "apn": "ims",
                "type": "ims",
                "current": None,
                "protocol": "IPV4V6",
                "roaming_protocol": "IPV4V6",
                "carrier_enabled": 1,
                "bearer": 0,
                "bearer_bitmask": 0,
                "sub_id": -1,
                "carrier_id": carr["carrier_id"],
                "edited": 1,
                "user_visible": 1,
                "user_editable": 1
            }
            next_id += 1
            insert_cols = [col for col in desired_values if col in available_cols]
            placeholders = ", ".join(["?"] * len(insert_cols))
            vals = [desired_values[col] for col in insert_cols]
            
            sql = f"INSERT INTO carriers ({', '.join(insert_cols)}) VALUES ({placeholders})"
            c.execute(sql, vals)
        
        # Upgrade default data APNs to dual IPv4/IPv6 protocol
        if "protocol" in available_cols and "roaming_protocol" in available_cols:
            c.execute("UPDATE carriers SET protocol='IPV4V6', roaming_protocol='IPV4V6' WHERE apn IN ('v-internet', 'm3-world', 'm-wap', 'm-iMax', 'wintel')")
            
        conn.commit()
        conn.close()
        
        # Push back to device and restore permissions
        adb_exec(["push", local_db, remote_tmp])
        adb_shell(f"cp {remote_tmp} {target_remote_db}", as_root=True)
        adb_shell(f"chmod 660 {target_remote_db}", as_root=True)
        adb_shell(f"chown radio:radio {target_remote_db} || chown 1001:1001 {target_remote_db}", as_root=True)
        adb_shell(f"rm -f {remote_tmp}", as_root=True)
        os.remove(local_db)
        return True
    except Exception as e:
        if os.path.exists(local_db):
            os.remove(local_db)
        return False

def query_ims_registration():
    """
    Multi-tier IMS status detection mechanism.
    Compatible across Android 8, 9, 10, 11, 12.
    """
    # Tier 1: Query Qualcomm QImsService in logcat
    rc, out_qims, _ = adb_shell("logcat -d -s QImsService:I", as_root=False)
    
    is_registered = ("registered = 1" in out_qims) or ("Status = 2" in out_qims and "networkMode = 14" in out_qims)
    voice_ok = ("voice true" in out_qims.lower()) or ("type = 0 status = 2" in out_qims)
    video_ok = ("video true" in out_qims.lower()) or ("type = 1 status = 2" in out_qims)
    
    # Tier 2: Universal Android Phone Dumpsys (Fallback if logcat buffer rotated)
    if not is_registered:
        rc_dump, out_dump, _ = adb_shell("dumpsys phone", as_root=False)
        reg_indicators = [
            "isImsRegistered=true", 
            "mImsServiceRegistrationState=1",
            "mImsRegistrationTech=14",
            "mIsImsRegistered=true",
            "isImsRegistered: true"
        ]
        if any(ind.lower() in out_dump.lower() for ind in reg_indicators):
            is_registered = True
            
        if not voice_ok and any(k in out_dump.lower() for k in ["mImsVoiceCapable=true", "isvoicecapable=true", "isvolteenabled=true"]):
            voice_ok = True
            
    # Tier 3: Telephony Registry Dumpsys
    if not is_registered:
        rc_reg, out_reg, _ = adb_shell("dumpsys telephony.registry", as_root=False)
        if "mImsRegistrationTech=14" in out_reg or "registered = 1" in out_reg:
            is_registered = True
            
    return {
        "registered": is_registered,
        "voice": voice_ok,
        "video": video_ok,
        "raw": out_qims[-300:] if out_qims else ""
    }
