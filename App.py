import streamlit as st
from datetime import timedelta
import re

# --- ฟังก์ชันช่วย (Helper Functions) ---
def format_srt_time(seconds):
    """แปลงวินาทีให้เป็นรูปแบบเวลาของ SRT"""
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    secs = td.seconds % 60
    millis = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def chunk_text_smart(text, max_chars=15):
    """
    ฟังก์ชันหั่นข้อความ (แบบพื้นฐาน)
    หากต้องการหั่นคำภาษาไทยที่แม่นยำขึ้น แนะนำให้ใช้ PyThaiNLP หรือเรียก Gemini API ตรงนี้
    """
    lines = text.split('\n')
    chunks = []
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # ถ้าบรรทัดสั้นกว่าที่กำหนด ให้ใช้ทั้งบรรทัด
        if len(line) <= max_chars:
            chunks.append(line)
        else:
            # ลองแยกด้วยช่องว่างก่อน (สำหรับข้อความที่มี Space)
            words = line.split()
            if len(words) > 1: 
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_chars:
                        current_chunk += (" " if current_chunk else "") + word
                    else:
                        if current_chunk: chunks.append(current_chunk)
                        current_chunk = word
                if current_chunk: chunks.append(current_chunk)
            else: 
                # ถ้าไม่มี Space เลย (ภาษาไทยล้วน) ให้ตัดตามจำนวนตัวอักษร
                for i in range(0, len(line), max_chars):
                    chunks.append(line[i:i+max_chars])
    return chunks

def generate_srt(chunks, chars_per_sec, min_dur, max_dur, gap):
    """สร้างเนื้อหาไฟล์ SRT"""
    srt_lines = []
    current_time = 0.0
    for i, text in enumerate(chunks):
        duration = len(text) / chars_per_sec
        duration = max(min_dur, min(duration, max_dur)) # Clamp ค่า
        
        start_time = current_time
        end_time = start_time + duration
        
        srt_lines.append(f"{i+1}\n{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n{text}\n")
        current_time = end_time + gap
        
    return "\n".join(srt_lines)

# --- ส่วนแสดงผลหน้าเว็บ (Streamlit UI) ---
st.set_page_config(page_title="Text to Short SRT", layout="centered")
st.title("📝 Text to Short SRT Generator")
st.caption("แปลงข้อความยาวๆ เป็นซับไตเติ้ลคำสั้นๆ สไตล์ TikTok/Reels (ไม่ต้องใช้ไฟล์เสียง)")

# 1. ส่วนรับข้อมูล
st.subheader("1. ใส่ข้อความต้นฉบับ")
input_method = st.radio("เลือกวิธีใส่ข้อความ", ("พิมพ์/วางข้อความเอง", "อัปโหลดไฟล์ .txt"), horizontal=True)

raw_text = ""
if input_method == "พิมพ์/วางข้อความเอง":
    raw_text = st.text_area("ใส่ข้อความของคุณที่นี่", height=150, placeholder="เช่น ทำอะไรให้ดู ปาดเดียวรู้เรื่อง ปึ้ง ไม่ต้องเกลี่ย...")
else:
    uploaded_file = st.file_uploader("เลือกไฟล์ .txt", type=["txt"])
    if uploaded_file:
        raw_text = uploaded_file.read().decode("utf-8")
        st.text_area("เนื้อหาที่อ่านได้:", raw_text, height=150)

# 2. ส่วนตั้งค่า
st.subheader("2. ตั้งค่าการคำนวณเวลา")
col1, col2 = st.columns(2)
with col1:
    chars_per_sec = st.slider("ความเร็วในการอ่าน (ตัวอักษร/วินาที)", 3.0, 10.0, 5.0, 0.5)
    min_duration = st.slider("เวลาแสดงขั้นต่ำ (วินาที)", 0.3, 1.5, 0.6, 0.1)
with col2:
    max_duration = st.slider("เวลาแสดงสูงสุด (วินาที)", 1.0, 4.0, 2.0, 0.1)
    gap = st.slider("เวลาคั่นระหว่างท่อน (วินาที)", 0.0, 0.5, 0.1, 0.05)

max_chars = st.slider("ความยาวสูงสุดต่อท่อน (จำนวนตัวอักษร)", 5, 30, 15)

# 3. ปุ่มประมวลผลและดาวน์โหลด
if st.button("🚀 สร้างไฟล์ SRT", type="primary", use_container_width=True):
    if not raw_text.strip():
        st.warning("กรุณาใส่ข้อความก่อนนะครับ!")
    else:
        with st.spinner("กำลังหั่นข้อความและคำนวณเวลา..."):
            chunks = chunk_text_smart(raw_text, max_chars=max_chars)
            srt_content = generate_srt(chunks, chars_per_sec, min_duration, max_duration, gap)
            
            st.success(f"สร้างสำเร็จ! (ทั้งหมด {len(chunks)} ท่อน)")
            
            # แสดงตัวอย่าง
            with st.expander("👀 ดูตัวอย่างเนื้อหา SRT (คลิกเพื่อขยาย)"):
                st.code(srt_content, language="text")
            
            # ปุ่มดาวน์โหลด
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ .srt",
                data=srt_content,
                file_name="my_short_subtitle.srt",
                mime="text/plain",
                use_container_width=True
            )
