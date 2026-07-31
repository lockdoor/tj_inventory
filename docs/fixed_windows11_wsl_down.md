# 🛠️ วิธีแก้ไข WSL / Docker Desktop ค้าง (Stuck/Zombie State) บน Windows 10/11

**อาการ:** เปิด WSL ไม่ขึ้น (Terminal หมุนค้าง), สั่ง `wsl --shutdown` ไม่ตอบสนอง, หรือ Docker Desktop ค้าง

**วิธีแก้ไข:** รันคำสั่งต่อไปนี้ใน **PowerShell (Run as Administrator)** ตามลำดับ

## 1. วิธีแก้เบื้องต้น: รีสตาร์ต Virtual Machine Services

หยุดและเปิดใหม่ Service ที่ควบคุมระบบ Virtual Machine ของ Windows เพื่อเคลียร์สถานะค้าง

```powershell
net stop vmcompute
net start vmcompute
net stop wslservice
net start wslservice

```

## 2. กรณีที่ Service ค้างในสถานะ "Starting or stopping" (Zombie Service)

หากคำสั่งในข้อ 1 ฟ้องว่า *The service is starting or stopping. Please try again later.* แปลว่าต้องบังคับฆ่า Process ของ Service นั้นทิ้ง

**ค้นหา PID ของ wslservice:**

```powershell
sc.exe queryex wslservice

```

*(ดูเลข `PID` จากผลลัพธ์ เช่น `PID : 1234`)*

**สั่งฆ่า PID นั้นทิ้ง (เปลี่ยน 1234 เป็นเลขที่ได้):**

```powershell
taskkill /f /pid 1234

```

**สั่ง Start Service ใหม่:**

```powershell
net start wslservice

```

## 3. บังคับปิด Docker Desktop ที่แอบดึงทรัพยากร WSL ไว้

หาก Docker Desktop แฮงก์และดึง WSL ค้างไว้ ให้บังคับปิด Process ของ Docker ทั้งหมด

```powershell
taskkill /f /im "Docker Desktop.exe"
taskkill /f /im "com.docker.backend.exe"

```

## 4. วิธีขั้นเด็ดขาด (ไม้ตาย): รีเซ็ต Hyper-V Network Adapters

หากทำ 3 วิธีแรกแล้วยังค้าง แสดงว่า Driver เครือข่ายจำลองของ Hyper-V ค้างระดับ Kernel ต้องใช้คำสั่งสั่งปิดเปิดการ์ดแลนจำลองของ WSL และรีเซ็ตบริการเครือข่าย

**รีเซ็ต Network Adapter ของ WSL:**

```powershell
Get-NetAdapter -Name "*WSL*" | Disable-NetAdapter -Confirm:$false
Get-NetAdapter -Name "*WSL*" | Enable-NetAdapter -Confirm:$false

```

**รีสตาร์ต Host Network Service (HNS):**

```powershell
net stop hns
net start hns

```

## 5. ทดสอบเปิด WSL อีกครั้ง

หลังจากทำตามขั้นตอน (โดยเฉพาะข้อ 4) ให้ลองรันคำสั่งเพื่อเข้าใช้งาน WSL อีกครั้ง

```powershell
wsl

```