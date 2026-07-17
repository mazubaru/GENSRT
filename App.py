import streamlit as st
import google.generativeai as genai
import json
import re
from datetime import timedelta

# --- ฟังก์ชันช่วย ---
def format_srt_time(seconds):
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    secs = td.seconds % 60
    millis = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def clean_json_response(text):
    """ลบ Markdown block ที่ AI อาจจะแถมมา เช่น ```json ... ```"""
    text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*|\s*```$', '', text, flags=re.MULTILINE)
    return text.strip()

def generate_srt(chunks, chars_per_sec, min_dur, max_dur, gap):
    srt_lines = []
    current_time = 0.0
    for i, text in enumerate(chunks):
        # คำนวณเวลาตามความยาวของ "คำที่หั่นถูกต้องแล้ว"
        duration = len(text) / chars_per_sec
        duration = max(min_dur, min(duration, max_dur))
        
        start_time = current_time
        end_time = start_time + duration
        
        srt_lines.append(f"{i+1}\n{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n{text}\n")
        current_time = end_time + gap
    return "\n".join(srt_lines)

# --- UI Streamlit ---
st.set_page_config(page_title="Smart Text to SRT", layout="centered")
st.title("🧠 Smart Text to Short SRT")
st.caption("ใช้ AI ช่วยแก้ไขคำผิด/สระหาย และหั่นข้อความเป็นคำสั้นๆ ตามบริบทก่อนสร้าง SRT")

# 1. API Key
with st.expander("⚙️ ตั้งค่า Gemini API Key (คลิกเพื่อกรอก)", expanded=False):
    api_key = st.text_input("ใส่ Gemini API Key ของคุณ:", type="password")
    st.caption("สามารถขอ Key ฟรีได้ที่ [Google AI Studio](https://aistudio.google.com/app/apikey)")

# 2. รับข้อความ
st.subheader("1. ข้อความต้นฉบับ (Raw Text)")
input_method = st.radio("เลือกวิธีใส่ข้อความ", ("พิมพ์/วางเอง", "อัปโหลดไฟล์ .txt"), horizontal=True)

raw_text = ""
if input_method == "พิมพ์/วางเอง":
    raw_text = st.text_area("วางข้อความที่ถอดเสียงมา (อาจมีคำผิดหรือสระหาย)", height=150, 
                            placeholder="เช่น ทำอะไรให้ดู ปาดเดียวรู้เรื่อง ปึง ไม่ต้องเกลี่ย...")
else:
    uploaded_file = st.file_uploader("เลือกไฟล์ .txt", type=["txt"])
    if uploaded_file:
        raw_text = uploaded_file.read().decode("utf-8")

# 3. ตั้งค่าเวลา
st.subheader("2. ตั้งค่าความเร็วซับไตเติ้ล")
col1, col2 = st.columns(2)
with col1:
    chars_per_sec = st.slider("ความเร็วอ่าน (ตัวอักษร/วิ)", 3.0, 10.0, 5.0, 0.5)
    min_duration = st.slider("เวลาแสดงขั้นต่ำ (วิ)", 0.3, 1.5, 0.6, 0.1)
with col2:
    max_duration = st.slider("เวลาแสดงสูงสุด (วิ)", 1.0, 4.0, 2.0, 0.1)
    gap = st.slider("เวลาคั่นระหว่างท่อน (วิ)", 0.0, 0.5, 0.1, 0.05)

# 4. ปุ่มประมวลผล
if st.button("🚀 สร้างไฟล์ SRT ด้วย AI", type="primary", use_container_width=True):
    if not api_key:
        st.error("กรุณาใส่ Gemini API Key ในส่วนตั้งค่าก่อนครับ!")
    elif not raw_text.strip():
        st.warning("กรุณาใส่ข้อความก่อนนะครับ!")
    else:
        with st.spinner("🧠 AI กำลังตรวจสอบคำผิดและหั่นข้อความตามบริบท..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Prompt ที่สั่งให้ AI แก้คำผิดและหั่นคำ
                prompt = f"""
                คุณคือผู้ช่วยสร้างซับไตเติลมืออาชีพ
                Tugas:
                1. ตรวจสอบและแก้ไขข้อความต่อไปนี้มีคำผิด สระหาย หรือตัวสะกดผิด (เช่น ปึง -> ปึ้ง, ลูกบวช -> ลูกบวบ, ไดมอนด์ชาย -> ไดมอนด์ฉ่ำ) ให้ถูกต้องตามบริบทของภาษาไทย
                2. นำข้อความที่แก้ไขแล้ว มาหั่นเป็นท่อนสั้นๆ (ท่อนละ 1-4 คำ) สำหรับทำซับไตเติลสไตล์ TikTok/Reels ที่คนอ่านทันและมีความหมายสมบูรณ์ในแต่ละท่อน
                3. ส่งผลลัพธ์เป็น JSON Array ของสตริงเท่านั้น เช่น ["ทำอะไร", "ให้ดู", "ปาดเดียว", "รู้เรื่อง", "ปึ้ง"]
                
                ห้ามมีข้อความอธิบายอื่นๆ นอกเหนือจาก JSON Array
                
                ข้อความต้นฉบับ:
                {raw_text}
                """
                
                response = model.generate_content(prompt)
                json_str = clean_json_response(response.text)
                chunks = json.loads(json_str)
                
                # สร้าง SRT
                srt_content = generate_srt(chunks, chars_per_sec, min_duration, max_duration, gap)
                
                st.success(f"สำเร็จ! AI แก้ไขและหั่นข้อความเป็น {len(chunks)} ท่อน")
                
                # แสดงผล
                with st.expander("👀 ดูรายการคำที่ AI หั่นให้ (คลิกเพื่อขยาย)"):
                    st.json(chunks)
                
                with st.expander("👀 ดูตัวอย่างเนื้อหา SRT"):
                    st.code(srt_content, language="text")
                
                st.download_button(
                    label="📥 ดาวน์โหลดไฟล์ .srt",
                    data=srt_content,
                    file_name="smart_subtitle.srt",
                    mime="text/plain",
                    use_container_width=True
                )
                
            except json.JSONDecodeError:
                st.error("AI ส่งค่ากลับมาไม่อยู่ในรูปแบบ JSON กรุณาลองใหม่อีกครั้ง")
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาด: {e}")
