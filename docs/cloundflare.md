
```markdown
# คู่มือการตั้งค่าและวิเคราะห์ความปลอดภัย: SSH ผ่าน Cloudflare Tunnel บน NAS

คู่มือฉบับนี้อธิบายวิธีการตั้งค่าเพื่อเชื่อมต่อ SSH เข้ามายัง NAS ขององค์กรอย่างไร้พอร์ตเปิด (Zero Port Forwarding) โดยใช้ **Cloudflare Tunnel (Cloudflare Access)** เพื่อป้องกันการโจมตีประเภทสแกนพอร์ตและการพยายามสุ่มรหัสผ่าน (Brute-force Attacks) จากอินเทอร์เน็ตภายนอก 100%

---

## 1. การประเมินความปลอดภัย (Security Assessment) 🔒

การเชื่อมต่อ SSH ผ่าน Cloudflare Tunnel ถือเป็นหนึ่งในรูปแบบที่มีความปลอดภัยสูงที่สุดในปัจจุบัน (Zero Trust Architecture) ด้วยจุดเด่นดังนี้:

1. **ไม่ต้องเปิดพอร์ตเราเตอร์ (No Open Ports):** ไม่จำเป็นต้องทํา Port Forwarding พอร์ต 22 หรือพอร์ตอื่นใดบนเราเตอร์ขององค์กร ทำให้บอทสแกนพอร์ตจากภายนอกไม่สามารถตรวจพบช่องทางเข้าสู่ระบบได้
2. **ระบบยืนยันตัวตนก่อนเข้าถึงเครื่องจริง (Pre-Authentication):** ผู้ใช้งานต้องผ่านระบบการสกรีนสิทธิ์ของ Cloudflare Access ก่อน (เช่น การยืนยันตัวตนผ่าน OTP ทางอีเมลบริษัท หรือ Identity Provider อื่นๆ) หากไม่ผ่านขั้นตอนนี้ ทราฟฟิกจะไม่สามารถเดินทางเข้าไปถึงหน้าต่างกรอกรหัสผ่าน SSH ของระบบ NAS ได้เลย
3. **การบันทึกประวัติการใช้งาน (Audit Logging):** ระบบของ Cloudflare จะบันทึกข้อมูล IP, อีเมล และช่วงเวลาที่มีการพยายามเชื่อมต่อเข้ามาโดยละเอียด ช่วยให้ง่ายต่อการตรวจสอบย้อนหลัง

---

## 2. แผนผังการทำงาน (Architecture)


```

[ เครื่องคอมพิวเตอร์ของคุณ ]
│ (รันคำสั่ง ssh และเรียกผ่าน cloudflared ในเครื่องตนเอง)
▼
[ Cloudflare Zero Trust (ตรวจสอบสิทธิ์การเข้าถึงผ่านระบบอีเมล/OTP) ]
│ (ส่งทราฟฟิกผ่านอุโมงค์ที่เข้ารหัสปลอดภัยสูง)
▼
[ cloudflared container บน NAS ]
│ (ส่งสัญญาณ SSH ต่อภายในเครือข่ายวงแลน)
▼
[ SSH Service (Port 22) บน NAS ]

```
*(อ้างอิงโครงสร้างสถาปัตยกรรมความปลอดภัย SSH ผ่าน Cloudflare Access และ Tunnel)*

---

## 3. ขั้นตอนการตั้งค่าทีละสเต็ป (Step-by-Step Setup)

### ส่วนที่ 1: ตั้งค่าบน Cloudflare Zero Trust Dashboard

1. ไปที่หน้าจัดการ **Cloudflare Zero Trust Dashboard** (`one.dash.cloudflare.com`)
2. ไปที่เมนู **Access** -> **Applications** -> กดปุ่ม **Add an Application**
3. เลือกรูปแบบประเภทการเชื่อมต่อเป็น **Self-Hosted**
4. กรอกรายละเอียดแอปพลิเคชัน:
   * **Application Name:** `NAS-SSH`
   * **Subdomain:** `ssh`
   * **Domain:** `tjglobal.biz`
5. ในขั้นตอน **Policies** (การกำหนดสิทธิ์ผู้เข้าใช้งาน):
   * ตั้งชื่อนโยบาย เช่น `Allow-Owner`
   * ในส่วนของ **Configure rules** เลือกเงื่อนไข **Include** -> **Emails** -> กรอกอีเมลที่อนุญาตให้ใช้งานสิทธิ์ SSH เท่านั้น
6. ในหน้าสุดท้าย **Additional Settings**:
   * เลื่อนลงมาที่หัวข้อ **SaaS integrations / Browser rendering**
   * ในส่วน **Session Duration** เลือกเวลาที่คุณต้องการให้ระบบจำสถานะการล็อกอิน (เช่น 1 Day)
   * กด **Save Application**

---

### ส่วนที่ 2: ผูกโดเมนย่อยเข้ากับอุโมงค์ (Tunnel)

1. ไปที่เมนู **Networks** -> **Tunnels** -> เลือก Tunnel ของคุณ -> กดปุ่ม **Configure**
2. คลิกไปที่แท็บ **Public Hostname** -> กด **Add a public hostname**
3. ตั้งค่าการส่งสัญญาณทราฟฟิก (Routing):
   * **Subdomain:** `ssh`
   * **Domain:** `tjglobal.biz`
   * **Type:** เลือกเป็น **SSH** (สำคัญมาก)
   * **URL:** `localhost:22` (หรือ IP ขาในของ NAS ที่รันพอร์ต SSH อยู่ เช่น `192.168.1.100:22`)
4. กด **Save Hostname** (ระบบจะสร้างค่า CNAME Record ใน DNS ให้โดยอัตโนมัติ)

---

### ส่วนที่ 3: ตั้งค่าที่เครื่องคอมพิวเตอร์ของคุณ (Client Side)

เนื่องจากระบบถูกครอบด้วย Cloudflare Access ตัวโปรแกรม SSH Client ทั่วไปจะไม่สามารถเรียกตรงๆ ได้ทันที คุณจำเป็นต้องตั้งค่าเครื่องคอมพิวเตอร์เครื่องหลักของคุณเสียก่อน:

1. **ติดตั้ง `cloudflared` บนเครื่องของคุณ:**
   * **macOS (ผ่าน Homebrew):** รันคำสั่ง `brew install cloudflare/cloudflare/cloudflared`
   * **Windows:** ดาวน์โหลดตัวติดตั้ง `.exe` ได้จากเว็บไซต์ของ Cloudflare

2. **แก้ไขไฟล์ Config ของ SSH บนเครื่องคอมพิวเตอร์ของคุณ:**
   * เปิดไฟล์ `~/.ssh/config` (บน Mac) หรือ `C:\Users\Username\.ssh\config` (บน Windows) ขึ้นมาแก้ไข
   * เพิ่มการตั้งค่าเพื่อบอกปลายทางว่าเมื่อเรียกหา `ssh.tjglobal.biz` ให้ส่งผ่านโปรแกรม `cloudflared` ก่อน:

```text
# การตั้งค่าสำหรับเชื่อมต่อเข้า NAS บริษัท ผ่าน Cloudflare Tunnel
Host ssh.tjglobal.biz
    # กำหนดพาธของ cloudflared ตามโครงสร้าง Homebrew ของเครื่องคุณ
    ProxyCommand /usr/local/opt/cloudflared/bin/cloudflared access ssh --hostname %h

```

*(หมายเหตุ: หากเป็นเครื่อง macOS ชิป Apple Silicon ที่ติดตั้ง Homebrew แบบปกติ พาธปกติจะเป็น `/opt/homebrew/bin/cloudflared` ส่วนผู้ใช้งานระบบปฏิบัติการ Windows ให้ใช้พาธจริงที่วางไฟล์ `cloudflared.exe` เช่น `ProxyCommand C:\bin\cloudflared.exe access ssh --hostname %h`)*

---

## 4. วิธีการใช้งานเข้าเชื่อมต่อ

หลังจากตั้งค่าทุกส่วนเสร็จสิ้นแล้ว เมื่อต้องการทำงานให้เปิดหน้าต่าง Terminal หรือ Command Prompt บนคอมพิวเตอร์ของคุณแล้วรันคำสั่งปกติ:

```bash
ssh thaijintan@ssh.tjglobal.biz

```

### สิ่งที่จะเกิดขึ้นตามลำดับเมื่อเรียกใช้งานคำสั่ง:

1. ระบบจะเปิดหน้าต่างเว็บเบราว์เซอร์ของคุณขึ้นมาอัตโนมัติเพื่อตรวจสอบสิทธิ์กับ **Cloudflare Access**
2. ให้ทำการยืนยันตัวตน (เช่น ตรวจสอบ OTP จากกล่องข้อความอีเมลของคุณ)
3. เมื่อผ่านการตรวจสอบบนหน้าเว็บเรียบร้อยแล้ว หน้าต่าง Terminal จะขยับให้คุณกรอกรหัสผ่านประจำตัวของระบบ NAS (User: `thaijintan`) และล็อกอินเข้าควบคุมระบบได้อย่างปลอดภัยทันที

```

```

[การตั้งค่า Cloudflare Tunnel ง่ายๆ](https://www.sync.co.th/blog/%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B8%95%E0%B8%B1%E0%B9%89%E0%B8%87%E0%B8%84%E0%B9%88%E0%B8%B2-cloudflare-tunnel-%E0%B8%87%E0%B9%88%E0%B8%B2%E0%B8%A2%E0%B9%86/45)