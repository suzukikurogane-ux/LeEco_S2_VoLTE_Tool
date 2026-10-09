import serial
import serial.tools.list_ports
import struct
import time
import os

CRC_TABLE = []
def init_crc_table():
    global CRC_TABLE
    if CRC_TABLE:
        return
    for i in range(256):
        curr = i
        for _ in range(8):
            if curr & 1:
                curr = (curr >> 1) ^ 0x8408
            else:
                curr >>= 1
        CRC_TABLE.append(curr)

init_crc_table()

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc = (crc >> 8) ^ CRC_TABLE[(crc ^ b) & 0xFF]
    return (~crc) & 0xFFFF

def escape_hdlc(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b == 0x7E:
            out.extend([0x7D, 0x5E])
        elif b == 0x7D:
            out.extend([0x7D, 0x5D])
        else:
            out.append(b)
    return bytes(out)

def unescape_hdlc(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0x7D:
            i += 1
            if i < n:
                out.append(data[i] ^ 0x20)
        else:
            out.append(b)
        i += 1
    return bytes(out)

def send_diag_cmd(ser, payload: bytes, timeout=2.0) -> bytes:
    crc = crc16(payload)
    pkt = payload + struct.pack('<H', crc)
    framed = escape_hdlc(pkt) + b'\x7E'
    ser.write(framed)
    
    start_time = time.time()
    buf = bytearray()
    while time.time() - start_time < timeout:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf.extend(chunk)
            if b'\x7E' in buf:
                parts = buf.split(b'\x7E')
                for p in parts[:-1]:
                    if p:
                        unframed = unescape_hdlc(p)
                        if len(unframed) >= 3:
                            data = unframed[:-2]
                            received_crc = struct.unpack('<H', unframed[-2:])[0]
                            if crc16(data) == received_crc:
                                return bytes(data)
                buf = parts[-1]
        time.sleep(0.01)
    return b""

def efs_hello(ser):
    payload = struct.pack('<BBHHIIII', 75, 19, 0, 0, 0, 0, 0, 0)
    resp = send_diag_cmd(ser, payload)
    return resp

def efs_mkdir(ser, path):
    p_bytes = path.encode('ascii') + b'\x00'
    payload = struct.pack('<BBHH', 75, 19, 8, 0o777) + p_bytes
    resp = send_diag_cmd(ser, payload)
    if resp and len(resp) >= 8:
        return struct.unpack('<I', resp[4:8])[0]
    return -1

def ensure_parent_dirs(ser, path):
    parts = path.strip('/').split('/')[:-1]
    curr = ""
    for p in parts:
        curr += "/" + p
        efs_mkdir(ser, curr)

def efs_unlink(ser, path):
    p_bytes = path.encode('ascii') + b'\x00'
    send_diag_cmd(ser, struct.pack('<BBH', 75, 19, 6) + p_bytes)

def efs_write_file(ser, path: str, data: bytes):
    ensure_parent_dirs(ser, path)
    p_bytes = path.encode('ascii') + b'\x00'
    payload = struct.pack('<BBHII', 75, 19, 2, 0x241, 0o666) + p_bytes
    resp = send_diag_cmd(ser, payload)
    if not resp or len(resp) < 12:
        return False, "EFS Open error: No response from modem"
    fd, errno = struct.unpack('<iI', resp[4:12])
    if fd < 0:
        return False, f"EFS Open failed (errno {errno})"
        
    offset = 0
    chunk_size = 512
    while offset < len(data):
        chunk = data[offset : offset + chunk_size]
        w_payload = struct.pack('<BBHII', 75, 19, 5, fd, offset) + chunk
        w_resp = send_diag_cmd(ser, w_payload)
        if not w_resp or len(w_resp) < 20:
            send_diag_cmd(ser, struct.pack('<BBHI', 75, 19, 3, fd))
            return False, "Failed to write data chunk to EFS"
        r_fd, r_offset, bytes_written, w_errno = struct.unpack('<iiii', w_resp[4:20])
        if bytes_written <= 0 or w_errno != 0:
            send_diag_cmd(ser, struct.pack('<BBHI', 75, 19, 3, fd))
            return False, f"EFS write error: errno={w_errno}"
        offset += bytes_written
        
    send_diag_cmd(ser, struct.pack('<BBHI', 75, 19, 3, fd))
    return True, "OK"

def efs_read_file(ser, path: str):
    p_bytes = path.encode('ascii') + b'\x00'
    payload = struct.pack('<BBHII', 75, 19, 2, 0, 0) + p_bytes
    resp = send_diag_cmd(ser, payload)
    if not resp or len(resp) < 12:
        return None, "Open failed: no response"
    fd, errno = struct.unpack('<iI', resp[4:12])
    if fd < 0:
        return None, f"Open failed: errno {errno}"
        
    data = bytearray()
    offset = 0
    chunk_size = 512
    while True:
        r_payload = struct.pack('<BBHIII', 75, 19, 4, fd, chunk_size, offset)
        r_resp = send_diag_cmd(ser, r_payload)
        if not r_resp or len(r_resp) < 20:
            break
        r_fd, r_offset, bytes_read, r_errno = struct.unpack('<iiii', r_resp[4:20])
        if bytes_read <= 0 or r_errno != 0:
            break
        data.extend(r_resp[20 : 20 + bytes_read])
        offset += bytes_read
        if bytes_read < chunk_size:
            break
    send_diag_cmd(ser, struct.pack('<BBHI', 75, 19, 3, fd))
    return bytes(data), "OK"

def find_diag_port():
    """
    Automatically search for Qualcomm Diagnostics port in Device Manager
    """
    ports = list(serial.tools.list_ports.comports())
    candidates = []
    
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        name = p.device
        
        # Check for Qualcomm VID (05c6) or Diag keywords
        if "05c6" in hwid or "qualcomm" in desc or "diag" in desc or "901d" in hwid or "9091" in hwid:
            candidates.append(name)
            
    if len(candidates) == 1:
        return candidates[0]
    return candidates
