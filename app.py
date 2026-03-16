import streamlit as st
from google import genai
from openai import OpenAI
import os
import speech_recognition as sr
import random
from streamlit_javascript import st_javascript 

# 1. 페이지 설정
st.set_page_config(page_title="AI 대본 생성기", layout="wide")

# ✅ 브라우저 전용 저장소 함수 (서버 파일 저장 로직 삭제)
def get_local_storage(key):
    return st_javascript(f"localStorage.getItem('{key}');")

def set_local_storage(key, val):
    st_javascript(f"localStorage.setItem('{key}', '{val}');")

# 카테고리 데이터 (기존 유지)
CATEGORIES = {
    "애니메이션": ["판타지", "액션", "일상", "로맨스", "SF", "코미디", "스포츠", "시대극"],
    "내레이션": ["다큐멘터리", "드라마", "오디오북"],
    "게임": [], "광고": ["상업광고", "공익광고", "기업홍보"],
    "라디오 드라마": [], "어색한 대본": []
}

GENRE_GUIDES = {
    "애니메이션": "캐릭터 개성 극대화, 감정 진폭이 큰 연기 중심.",
    "내레이션": "신뢰감 있는 톤, 정확한 정보 전달과 절제된 호흡.",
    "게임": "짧고 강렬한 임팩트, 시네마틱한 말투.",
    "광고": "청각적 훅(Hook) 중심, 빠르고 정확한 딕션.",
    "라디오 드라마": "목소리만으로 공간감을 만드는 일상 연기.",
    "어색한 대본": "순발력과 발음 교정 훈련용."
}

# 세션 상태 초기화
if "current_script" not in st.session_state: st.session_state.current_script = ""
if "prev_main_category" not in st.session_state: st.session_state.prev_main_category = "랜덤 선택"
if "show_manage_keys" not in st.session_state: st.session_state.show_manage_keys = False
if "custom_url" not in st.session_state: st.session_state.custom_url = ""

# --- 2. 상단 헤더 및 AI 설정 ---
col_title, col_setup = st.columns([4, 1])
with col_title:
    st.title("🎙️ AI 대본 생성기")

with col_setup:
    with st.popover("⚙️ AI 설정"):
        ai_providers = ["Google Gemini", "OpenAI (ChatGPT)", "기타 / 로컬 AI (OpenAI 호환)"]
        ai_provider = st.selectbox("사용할 AI 서비스", ai_providers)
        
        if ai_provider == "기타 / 로컬 AI (OpenAI 호환)":
            st.session_state.custom_url = st.text_input("API Base URL", value=st.session_state.custom_url)
        
        # ✅ [핵심] 서버 파일 대신 브라우저 저장소에서만 키를 읽어옴
        stored_key = get_local_storage(f"stored_key_{ai_provider}")
        keys = [stored_key] if (stored_key and stored_key != "null") else []

        st.write("---")
        st.markdown("### 🔑 API 키 관리")
        
        if keys:
            st.success("✅ 브라우저에 키가 안전하게 저장되어 있습니다.")
            if st.button("👁️ 등록된 키 보기/삭제"):
                st.session_state.show_manage_keys = not st.session_state.show_manage_keys
            
            if st.session_state.show_manage_keys:
                c1, c2 = st.columns([3, 1])
                c1.code(f"{keys[0][:6]}...{keys[0][-4:]}", language=None)
                if c2.button("🗑️ 삭제"):
                    set_local_storage(f"stored_key_{ai_provider}", "") # 브라우저 저장소 비움
                    st.rerun()
        else:
            st.info("등록된 키가 없습니다. 본인의 API 키를 입력해주세요.")

        new_key = st.text_input("새 API 키 등록 (내 브라우저에만 저장)", type="password")
        if st.button("➕ 등록 및 기억하기", use_container_width=True):
            if new_key:
                set_local_storage(f"stored_key_{ai_provider}", new_key) # 브라우저 저장소에 기록
                st.rerun()
        
        # 모델 선택
        if ai_provider == "Google Gemini":
            selected_model = st.selectbox("모델", ["gemini-2.5-flash", "gemini-2.0-flash"])
        elif ai_provider == "OpenAI (ChatGPT)":
            selected_model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4o"])
        else:
            selected_model = st.text_input("모델 명칭", value="llama3")

# --- 3. 사이드바 및 4. AI 호출 ---
with st.sidebar:
    st.markdown("### 🎭 대본 설정")
    user_gender = st.radio("나의 성별", ["남성", "여성"], horizontal=True)
    main_category = st.selectbox("🎯 대분류 선택", ["랜덤 선택"] + list(CATEGORIES.keys()))
    
    if main_category != st.session_state.prev_main_category:
        st.session_state.current_script = ""; st.session_state.prev_main_category = main_category
    
    sub_category = None
    if main_category != "랜덤 선택":
        sub_items = CATEGORIES.get(main_category, [])
        if sub_items: sub_category = st.selectbox(f"📂 세부 항목", ["랜덤"] + sub_items)
    has_partner = main_category in ["애니메이션", "라디오 드라마"] and st.checkbox("상대 배역 포함", value=True)

def call_ai(prompt):
    # ✅ 브라우저에서 가져온 키를 즉시 사용
    if not keys or not keys[0]: return "NO_KEY"
    
    try:
        if ai_provider == "Google Gemini":
            client = genai.Client(api_key=keys[0])
            return client.models.generate_content(model=selected_model, contents=prompt).text
        elif ai_provider == "OpenAI (ChatGPT)":
            client = OpenAI(api_key=keys[0])
            return client.chat.completions.create(model=selected_model, messages=[{"role": "user", "content": prompt}]).choices[0].message.content
        else:
            client = OpenAI(api_key=keys[0], base_url=st.session_state.custom_url)
            return client.chat.completions.create(model=selected_model, messages=[{"role": "user", "content": prompt}]).choices[0].message.content
    except Exception as e:
        return f"ERROR: {str(e)}"

# --- 5. 대본 생성 및 출력 ---
if st.button("✨ 새로운 대본 생성하기", use_container_width=True):
    final_main = main_category if main_category != "랜덤 선택" else random.choice(list(CATEGORIES.keys()))
    final_sub = sub_category if sub_category not in ["랜덤", None] else (random.choice(CATEGORIES[final_main]) if CATEGORIES[final_main] else "")
    sub_text = f"({final_sub})" if final_sub else ""
    p_style = "2인극" if has_partner else "1인극"
    genre_guide = GENRE_GUIDES.get(final_main, "")
    
    prompt = f"[{final_main}] {sub_text} 장르 성우 대본 작성. 스타일: {p_style}. {genre_guide} 양식: ### 📋 캐릭터 정보\n### 📖 연습 대본"
    
    with st.spinner("AI가 대본을 생성중입니다..."):
        result = call_ai(prompt)
        if result == "NO_KEY": st.error("⚙️ AI 설정에서 API 키를 먼저 등록해주세요.")
        elif "ERROR" in result: st.error(f"API 호출 중 오류가 발생했습니다. 키를 확인해주세요. ({result})")
        else: st.session_state.current_script = result; st.rerun()

if st.session_state.current_script:
    st.markdown(st.session_state.current_script)
    st.divider()
    audio_value = st.audio_input("연습 녹음")
    if audio_value:
        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_value) as source: audio_data = r.record(source)
            st.write(f"🗣️ **인식 내용:** {r.recognize_google(audio_data, language='ko-KR')}")
        except: st.error("인식 실패")