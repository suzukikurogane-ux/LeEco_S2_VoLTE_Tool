# LeEco Le S2 / Le 2 (MSM8976) • VoLTE & IMS Enabler Tool

---

## 1. Overview
An automated 1-Click utility designed to persistently enable VoLTE (Voice over LTE) and IMS capabilities on **LeEco devices powered by Qualcomm Snapdragon 652 (MSM8976)**.

The tool interfaces directly with the **Hexagon Modem EFS** using standard **Qualcomm DIAG protocol (HDLC framing)**:
* Disables SIP Precondition negotiation (`qipcall_precondition_enable = 00`) for seamless IMS bearer establishment.
* Disables mandatory QoS precondition requirement (`qipcall_qos_enabled = 00`).
* Flashes verified MMTel Voice & Video Call service profile databases (`qipcall_config_items`, `qp_ims_reg_config_db`).
* Sets voice domain preference to IMS LTE prioritized (`voice_domain_pref = 03`).
* Provisions dedicated `ims` APN and enables dual-SIM VoLTE flags in Android Telephony Provider.

---

## 2. Supported Devices
* **Fully Compatible & Tested:**
  * LeEco Le S2 (`Le X520`)
  * LeEco Le 2 (`Le X526`)
  * LeEco Le 2 (`Le X527`)
  * LeEco Le S2 (`Le X528`)
* ⚠️ **SAFETY GUARDRAIL (ANTI-BRICK):**
  * **DO NOT RUN ON:** LeEco Le 2 MediaTek Helio X20 edition (`Le X620`).
  * The tool includes automated SoC hardware validation and will immediately halt if a MediaTek platform is detected.

---

## 3. Prerequisites
1. **Target Device:**
   * Powered on normally to Android home screen (No Fastboot or TWRP required).
   * Bootloader unlocked with **Root access (Magisk)**.
   * **USB Debugging** enabled in *Settings ➔ Developer Options*.
   * Accept any USB Debugging / SuperUser prompt on the phone display.
2. **SIM & Carrier Network:**
   * Universal multi-carrier support (Viettel, VinaPhone/Wintel/iTel, MobiFone/FPT, and global carriers).
   * Ensure VoLTE service is activated with your mobile operator.
3. **Host Computer (Windows):**
   * **No Python installation required:** The portable edition includes an embedded official Python runtime.
   * Qualcomm USB Diagnostics Driver installed.

---

## 4. Step-by-Step Instructions

### Step 1: Launch Tool
* Connect your phone to your PC via USB cable.
* Double-click **`run_tool.bat`**.
* Grant SuperUser / USB Debugging permissions on your phone screen when prompted.

### Step 2: Compatibility Audit
* Select Option **`1`** (`Device & Hardware Compatibility Audit`).
* The tool will verify Snapdragon 652 architecture and display green verification status.

### Step 3: Automated VoLTE Provisioning (1-Click)
* Select Option **`3`** (`Automated VoLTE Provisioning`).
* The process performs four automated operations:
  1. **Pre-flight EFS Backup:** Dumps `modemst1`, `modemst2`, `fsg` to `backups/` directory.
  2. **Qualcomm Diag Activation:** Automatically triggers diagnostic serial interface.
  3. **NV Item Flashing:** Flashes and verifies 34 standardized VoLTE NV items to Hexagon modem EFS.
  4. **Telephony & IMS APN Setup:** Injects IMS APNs and updates SQLite telephony database.
* When prompted, type **`Y`** to reboot the phone and apply changes.

---

## 5. Verification After Reboot
1. Open phone dialer and enter `*#*#4636#*#*`.
2. Tap **Phone Information** ➔ 3-dots menu ➔ **IMS Service Status**.
3. Verify:
   * *IMS Registration:* **Registered**
   * *Voice over LTE:* **Available**
4. Place a test phone call. The status bar will retain the **4G/LTE** indicator throughout the call with crystal-clear HD Voice AMR-WB quality.

---

## 6. Rollback / Restore
If you ever wish to revert your modem to stock factory state:
* Launch tool and select Option **`4`** (`Restore EFS from Previous Archive`).
* Select the desired partition backup and type `YES` to restore.
