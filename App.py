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
    text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*|\s*```$', '', text, flags=re.MULTILINE)
    return text.strip()

def generate_srt(chunks, mode, chars_per_sec, total_video_seconds, gap):
    srt_lines = []
    current_time = 0.0
    
    if mode == "🎯 ปรับให้พอดีกับความยาววิดีโอ (Sync to Video)" and total_video_seconds > 0:
        total_chars = sum(len(c) for c in chunks)
        if total_chars == 0: return ""
        
        # 1. หาเวลาที่ต้องใช้คั่นทั้งหมด (ไม่คิดตัวคั่นหลังท่อนสุดท้าย)
        total_gaps_time = (len(chunks) - 1) * gap
        available_time = total_video_seconds - total_gaps_time
        if available_time < 0: 
            available_time = 0
            
        for i, text in enumerate(chunks):
            char_ratio = len(text) / total_chars
            duration = char_ratio * available_time
            
            start_time = current_time
            end_time = start_time + duration
            
            # 2. ป้องกันปัญหาเสี้ยววินาทีปัดเศษในโปรแกรมตัดต่อ: 
            # ถ้าเป็นท่อนสุดท้าย บังคับให้ end_time เท่ากับความยาววิดีโอเป๊ะๆ
            if i == len(chunks) - 1:
                end_time = float(total_video_seconds)
            
            srt_lines.append(f"{i+1}\n{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n{text}\n")
            
            current_time = end_time + gap
            
    else:
        for i, text in enumerate(chunks):
            duration = len(text) / chars_per_sec
            start_time = current_time
            end_time = start_time + duration
            srt_lines.append(f"{i+1}\n{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n{text}\n")
            current_time = end_time + gap
            
    return "\n".join(srt_lines)

# --- UI Streamlit ---
st.set_page_config(page_title="Smart Text to SRT", layout="centered")
st.markdown(
    """
    <style>
    /* สร้างพื้นหลังสไตล์ Dark Industrial/Grunge Concrete */
    .stApp {
        background-color: #121212;
        background-image: 
            /* Layer 1: รอยคราบและแสงเงาแบบสุ่ม (Vignette & Grunge Shadows) */
            radial-gradient(circle at 20% 30%, rgba(40, 40, 40, 0.4) 0%, transparent 60%),
            radial-gradient(circle at 80% 70%, rgba(20, 20, 20, 0.6) 0%, transparent 50%),
            /* Layer 2: ลายเส้นตัดแนวตั้ง/แนวนอนบางๆ เลียนแบบผ้ากระสอบหรือปูนดิบ */
            linear-gradient(rgba(255, 255, 255, 0.03) 0px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.03) 0px, transparent 1px),
            /* Layer 3: เม็ด Noise ถี่ๆ สไตล์ขาวดำดิจิทัล */
            radial-gradient(rgba(255, 255, 255, 0.05) 0px, transparent 0);
        
        /* ตั้งค่าขนาดของลายเพื่อให้เกิด Texture ถี่ๆ */
        background-size: 100% 100%, 100% 100%, 20px 20px, 20px 20px, 4px 4px;
        background-attachment: fixed;
    }
    
    /* ปรับแต่งตัวอักษรให้คมชัด อ่านง่าย ทะลุพื้นหลังมืด */
    h1, h2, h3, p, span, label {
        color: #f0f0f0 !important;
        font-family: 'Helvetica Neue', sans-serif;
        text-shadow: 2px 2px 5px rgba(0, 0, 0, 0.9);
    }
    
    /* กล่องข้อความและ Input ต่างๆ ปรับให้โมเดิร์นกึ่งโปร่งแสง */
    .stTextArea textarea, .stTextInput input, .stSelectbox div {
        background-color: rgba(25, 25, 25, 0.75) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
    }

    /* ตกแต่งส่วนหัว (Caption) */
    .stMarkdown p {
        color: #b3b3b3 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("🧠 Smart Text to Short SRT")

# 1. API Key
with st.expander("⚙️ ตั้งค่า Gemini API Key", expanded=False):
    api_key = st.text_input("ใส่ Gemini API Key ของคุณ:", type="password")
    st.caption("ขอ Key ฟรีได้ที่ [Google AI Studio](https://aistudio.google.com/app/apikey)")

# 2. รับข้อความ
st.subheader("1. ข้อความต้นฉบับ (Raw Text)")
input_method = st.radio("เลือกวิธีใส่ข้อความ", ("พิมพ์/วางเอง", "อัปโหลดไฟล์ .txt"), horizontal=True)

raw_text = ""
if input_method == "พิมพ์/วางเอง":
    raw_text = st.text_area("วางข้อความที่ถอดเสียงมา", height=150, 
                            placeholder="เช่น ทำอะไรให้ดู ปาดเดียวรู้เรื่อง ปึง ไม่ต้องเกลี่ย...")
else:
    uploaded_file = st.file_uploader("เลือกไฟล์ .txt", type=["txt"])
    if uploaded_file:
        raw_text = uploaded_file.read().decode("utf-8")

# 3. ตั้งค่าเวลา
st.subheader("2. ตั้งค่าความยาวและจังหวะซับไตเติ้ล")
timing_mode = st.radio("โหมดการคำนวณเวลา", 
                       ("🎯 ปรับให้พอดีกับความยาววิดีโอ (Sync to Video)", "⏱️ ความเร็วในการอ่านคงที่ (Fixed Speed)"), 
                       horizontal=True)

gap = st.slider("เวลาคั่นระหว่างท่อน (วินาที)", 0.0, 0.5, 0.1, 0.05)

if timing_mode.startswith("🎯"):
    col1, col2 = st.columns(2)
    with col1:
        total_minutes = st.number_input("ความยาววิดีโอ (นาที)", min_value=0, value=1)
    with col2:
        total_seconds_input = st.number_input("ความยาววิดีโอ (วินาที)", min_value=0, max_value=59, value=30)
    total_video_seconds = (total_minutes * 60) + total_seconds_input
    chars_per_sec = 5.0 
else:
    total_video_seconds = 0
    chars_per_sec = st.slider("ความเร็วในการอ่าน (ตัวอักษร/วินาที)", 3.0, 15.0, 5.0, 0.5)

# 4. ปุ่มประมวลผล
if st.button("🚀 สร้างไฟล์ SRT ด้วย AI", type="primary", use_container_width=True):
    if not api_key:
        st.error("กรุณาใส่ Gemini API Key ในส่วนตั้งค่าก่อนครับ!")
    elif not raw_text.strip():
        st.warning("กรุณาใส่ข้อความก่อนนะครับ!")
    else:
       with st.spinner("🧠 AI กำลังตรวจสอบคำผิดและหั่นข้อความ..."):
            try:
                genai.configure(api_key=api_key)
                
                # เปลี่ยนชื่อโมเดลตรงนี้เป็นรุ่นที่สมบูรณ์และเปิดใช้งานแล้ว
                model_name = "gemini-3.5-flash" 
                
                try:
                    config = genai.types.GenerationConfig(
                        response_mime_type="application/json"
                    )
                    
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        generation_config=config
                    )
                except Exception as e:
                    st.error(f"ไม่สามารถตั้งค่าโมเดล {model_name} ได้: {e}")
                    st.stop()
                
                prompt = f"""
                คุณคือผู้ช่วยสร้างซับไตเติลมืออาชีพ
                Tugas:
                1. ตรวจสอบและแก้ไขข้อความต่อไปนี้มีคำผิด สระหาย หรือตัวสะกดผิด ให้ถูกต้องตามบริบทของภาษาไทย
                2. นำข้อความที่แก้ไขแล้ว มาหั่นเป็นท่อนสั้นๆ (ท่อนละ 1-4 คำ) สำหรับทำซับไตเติลสไตล์ TikTok/Reels
                3. ส่งผลลัพธ์เป็น JSON Array ของสตริงเท่านั้น เช่น ["ทำอะไร", "ให้ดู", "ปาดเดียว", "รู้เรื่อง", "ปึ้ง"]
                ห้ามมีข้อความอธิบายอื่นๆ นอกเหนือจาก JSON Array
                
                ข้อความต้นฉบับ:
                {raw_text}
                """
                
                response = model.generate_content(prompt)
                json_str = clean_json_response(response.text)
                chunks = json.loads(json_str)
                
                # สร้าง SRT
                srt_content = generate_srt(chunks, timing_mode, chars_per_sec, total_video_seconds, gap)
                
                st.success(f"สำเร็จ! AI หั่นข้อความเป็น {len(chunks)} ท่อน")
                
                with st.expander("👀 ดูรายการคำที่ AI หั่นให้"):
                    st.json(chunks)
                
                with st.expander("👀 ดูตัวอย่างเนื้อหา SRT"):
                    st.code(srt_content, language="text")
                
                st.download_button(
                    label="📥 ดาวน์โหลดไฟล์ .srt",
                    data=srt_content,
                    file_name="smart_subtitle_synced.srt",
                    mime="text/plain",
                    use_container_width=True
                )
                
            except json.JSONDecodeError:
                st.error("AI ส่งค่ากลับมาไม่อยู่ในรูปแบบ JSON กรุณาลองใหม่อีกครั้ง (บางครั้ง AI อาจตอบยาวเกินไป)")
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")
