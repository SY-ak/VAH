import streamlit as st
import json
from google import genai
from openai import OpenAI
import speech_recognition as sr
import random
import re

# 1. 페이지 설정
st.set_page_config(page_title="AI 대본 생성기", layout="wide")

from streamlit_javascript import st_javascript

def get_local_storage(key):
    val = st_javascript(f"localStorage.getItem('{key}');")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return ""

def set_local_storage(key, val):
    safe_val = val.replace("'", "\\'")
    st_javascript(f"localStorage.setItem('{key}', '{safe_val}');")

def clear_local_storage(key):
    st_javascript(f"localStorage.removeItem('{key}');")

# 카테고리 및 가이드 데이터
CATEGORIES = {
    "애니메이션": ["판타지", "액션", "일상", "로맨스", "SF", "코미디", "스포츠", "시대극"],
    "내레이션": ["다큐멘터리", "드라마", "오디오북"],
    "게임": [],
    "광고": ["상업광고", "공익광고", "기업홍보"],
    "라디오 드라마": [],
    "어색한 대본": []
}

GENRE_GUIDES = {
    "애니메이션": "캐릭터 개성 극대화, 감정 진폭이 큰 연기 중심.",
    "내레이션": "정확한 정보 전달 (내용은 정통성을 지키되, 톤만 캐릭터 성격에 맞출 것).",
    "게임": "짧고 강렬한 임팩트, 시네마틱한 전개.",
    "광고": "청각적 훅(Hook) 중심.",
    "라디오 드라마": "목소리만으로 공간감을 만드는 연기.",
    "어색한 대본": "순발력과 발음 교정 훈련용."
}

# 긍정/부정/다양한 성격 밸런스 패치
PERSONALITIES = [
    # 긍정 / 밝음 / 따뜻함
    "명랑, 긍정 에너지가 넘치고 해맑은", "다정다감, 따뜻하고 배려심 깊은", 
    "순수, 아이같이 티 없고 솔직한", "친절, 누구에게나 상냥한 톤의", 
    "호탕, 시원시원하고 털털한", "열정적, 꿈을 향해 달리는 희망찬",
    "듬직, 언제나 내 편이 되어주는 든든한", "당돌, 할 말은 다 하는 사이다 같은",
    # 매력 / 개성 / 여유
    "능글맞은, 여유롭고 장난기 많은", "우아, 기품 있고 세련된 말투의",
    "허당, 완벽해 보이나 은근히 빈틈이 있는", "카리스마, 좌중을 압도하는 리더형",
    "지적, 논리적이고 차분한 전문가 스타일", "신비, 비밀을 간직한 듯 몽환적인",
    "사색적, 철학적이고 깊이 있는", "엉뚱, 4차원적이고 상상력이 풍부한",
    "하이텐션, 쉴 새 없이 떠드는 텐션 높은", "느릿느릿, 만사태평하고 여유로운",
    # 강렬 / 부정 / 독특함
    "열혈, 불타오르는 에너지의", "냉소적, 시니컬하고 차가운",
    "껄렁껄렁, 세상 불만 많고 삐딱한", "소심, 늘 주눅들어 있고 눈치 보는",
    "거만, 귀족적이고 남을 내려다보는", "극도로 진지, 유머감각 제로인 FM 원칙주의자",
    "우울, 세상 다 산 느낌의 허무한", "예민, 신경질적이고 날이 서 있는",
    "허세 가득, 실속 없이 잘난 척하는", "무미건조, 감정 없는 AI나 기계 같은",
    "광기 어린, 무언가에 집착하고 번뜩이는", "음흉, 속을 알 수 없고 꿍꿍이가 있는"
]

AI_PROVIDERS = ["Google Gemini", "OpenAI (ChatGPT)", "기타 / 로컬 AI (OpenAI 호환)"]

# 세션 상태 초기화
if "current_script" not in st.session_state:
    st.session_state.current_script = ""
if "prev_main_category" not in st.session_state:
    st.session_state.prev_main_category = "랜덤 선택"
if "custom_url" not in st.session_state:
    st.session_state.custom_url = ""
if "input_key_counter" not in st.session_state:
    st.session_state.input_key_counter = 0

if "keys_loaded" not in st.session_state:
    st.session_state.keys_loaded = False

for p in AI_PROVIDERS:
    skey = f"session_api_keys_{p}"
    if skey not in st.session_state:
        st.session_state[skey] = []

# --- 2. 사이드바: 대본 설정 ---
with st.sidebar:
    st.markdown("### 🎭 대본 설정")
    user_gender = st.radio("나의 성별", ["남성", "여성"], horizontal=True, key="user_gender_state")
    main_cat_list = ["랜덤 선택"] + list(CATEGORIES.keys())
    main_category = st.selectbox("🎯 대분류 선택", main_cat_list, key="main_category_state")

    if main_category != st.session_state.prev_main_category:
        st.session_state.current_script = ""
        st.session_state.prev_main_category = main_category

    sub_category = None
    if main_category != "랜덤 선택":
        sub_items = CATEGORIES.get(main_category, [])
        if sub_items:
            sub_category = st.selectbox("📂 세부 항목", ["랜덤"] + sub_items, key=f"sub_category_state_{main_category}")

    has_partner = main_category in ["애니메이션", "라디오 드라마"] and st.checkbox("상대 배역 포함", value=True, key="has_partner_state")

# --- 3. 상단 헤더 및 AI 설정 (Popover) ---
col_title, col_setup = st.columns([4, 1])

with col_title:
    st.title("🎙️ AI 대본 생성기")

with col_setup:
    with st.popover("⚙️ AI 설정"):
        ai_provider = st.selectbox("사용할 AI 서비스", AI_PROVIDERS, key="ai_provider_state")

        if ai_provider == "기타 / 로컬 AI (OpenAI 호환)":
            st.session_state.custom_url = st.text_input(
                "API Base URL",
                value=st.session_state.custom_url,
                placeholder="예: http://localhost:11434/v1",
                key="custom_url_state"
            )

        if ai_provider == "Google Gemini":
            selected_model = st.selectbox("모델", ["gemini-2.5-flash", "gemini-2.0-flash"], key="gemini_model_state")
        elif ai_provider == "OpenAI (ChatGPT)":
            selected_model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4o"], key="openai_model_state")
        else:
            selected_model = st.text_input(
                "모델 명칭",
                value="llama3",
                placeholder="사용할 모델 이름을 입력하세요",
                key="local_model_state"
            )

        session_key_name = f"session_api_keys_{ai_provider}"
        ls_key_name = f"api_keys_{ai_provider}"

        if not st.session_state.keys_loaded:
            for p in AI_PROVIDERS:
                ls_val = get_local_storage(f"api_keys_{p}")
                if ls_val:
                    try:
                        st.session_state[f"session_api_keys_{p}"] = json.loads(ls_val)
                    except json.JSONDecodeError:
                        if ls_val.strip():
                            st.session_state[f"session_api_keys_{p}"] = [ls_val.strip()]
            st.session_state.keys_loaded = True

        current_keys = st.session_state[session_key_name]

        st.write("---")
        st.markdown("### 🔑 API 키 관리")

        new_key = st.text_input(
            "새 API 키 추가",
            type="password",
            placeholder="sk-... 또는 AIza...",
            key=f"new_key_input_{st.session_state.input_key_counter}" 
        )
        if st.button("➕ 등록하기", use_container_width=True):
            if new_key and new_key.strip():
                if new_key.strip() not in current_keys:
                    current_keys.append(new_key.strip())
                    set_local_storage(ls_key_name, json.dumps(current_keys))
                    st.session_state.input_key_counter += 1
                    st.rerun()
                else:
                    st.warning("이미 등록된 키입니다.")
            else:
                st.warning("키를 입력해주세요.")

        st.markdown("<br>", unsafe_allow_html=True) 

        if current_keys:
            st.success(f"✅ 등록된 키: {len(current_keys)}개")
            st.caption("위에서부터 순서대로 사용되며, 할당량 초과 시 자동으로 다음 키로 전환됩니다.")
            
            for i, k in enumerate(current_keys):
                c1, c2 = st.columns([4, 1])
                c1.code(f"[{i+1}] {k[:6]}...{k[-4:]}")
                if c2.button("🗑️", key=f"del_{ai_provider}_{i}"):
                    current_keys.pop(i)
                    set_local_storage(ls_key_name, json.dumps(current_keys))
                    st.rerun()

            if st.button("🗑️ 모든 키 삭제", use_container_width=True):
                st.session_state[session_key_name] = []
                set_local_storage(ls_key_name, "[]")
                st.rerun()
        else:
            st.info("등록된 키가 없습니다.")

# --- 4. AI 호출 및 자동 키 전환 함수 ---
def call_ai(prompt):
    keys = st.session_state.get(f"session_api_keys_{ai_provider}", [])
    if not keys:
        return "NO_KEYS"

    last_error = ""

    for i, key in enumerate(keys):
        try:
            if ai_provider == "Google Gemini":
                client = genai.Client(api_key=key)
                res = client.models.generate_content(model=selected_model, contents=prompt).text
            elif ai_provider == "OpenAI (ChatGPT)":
                client = OpenAI(api_key=key, timeout=30.0)
                res = client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content
            else:
                client = OpenAI(api_key=key, base_url=st.session_state.custom_url, timeout=30.0)
                res = client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content
            return res 
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "quota" in error_msg or "limit" in error_msg or "429" in error_msg or "exhausted" in error_msg:
                last_error = "API_QUOTA_EXHAUSTED"
                if i < len(keys) - 1:
                    st.toast(f"⚠️ {i+1}번 키 할당량 초과. {i+2}번 키로 자동 전환하여 시도합니다...", icon="🔄")
                    continue 
                else:
                    break 
            
            elif "auth" in error_msg or "api key" in error_msg or "invalid" in error_msg or "401" in error_msg or "403" in error_msg:
                last_error = "API_KEY_INVALID"
                if i < len(keys) - 1:
                    st.toast(f"⚠️ {i+1}번 키 인증 오류. {i+2}번 키로 자동 전환하여 시도합니다...", icon="🔄")
                    continue
                else:
                    break
                    
            else:
                if "timeout" in error_msg:
                    last_error = "API_ERROR:서버 응답 시간 초과 (30초)"
                else:
                    last_error = f"API_ERROR:{str(e)}"
                break 

    return last_error 

# --- 5. 대본 생성 메인 로직 ---
current_keys_main = st.session_state.get(f"session_api_keys_{ai_provider}", [])

if not current_keys_main:
    st.warning("⚙️ 오른쪽 상단의 **AI 설정**에서 API 키를 먼저 등록해주세요.")
else:
    if st.button("✨ 새로운 대본 생성하기", use_container_width=True):
        final_main = main_category if main_category != "랜덤 선택" else random.choice(list(CATEGORIES.keys()))
        final_sub = sub_category if sub_category not in ["랜덤", None] else (
            random.choice(CATEGORIES[final_main]) if CATEGORIES[final_main] else ""
        )
        sub_text = f"({final_sub})" if final_sub else ""
        p_style = "2인극" if has_partner else "1인극"
        genre_guide = GENRE_GUIDES.get(final_main, "")

        age_categories = ["소년/소녀 (10대 이하)", "청년 (20~30대)", "중년 (40~50대)", "노년 (60대 이상)"]
        target_age_group = random.choice(age_categories)
        
        target_personality = random.choice(PERSONALITIES)

        prompt = f"""
성우 공채 전문 작가로서 [{final_main}] 장르 대본을 집필하라.
장르: {final_main} {sub_text}, 스타일: {p_style}.

[핵심 지침 (매우 중요)]:
1. 대본 내용과 캐릭터 성격의 완벽한 분리:
   - 대본의 **스토리, 주제, 상황**은 반드시 [{final_main}] 장르에 맞는 '정통적이고 평범한 내용'으로 설정하라.
   - 단, 그 대본을 낭독하는 캐릭터의 **말투와 톤**만 [{target_personality}] 컨셉을 적용하라.
   - 🚨 캐릭터 성격 때문에 대본의 장르나 내용 자체가 변질되어선 안 된다!
     (예시: 다큐멘터리 내레이션에 '열혈' 성격이 부여되었다면, 대본의 내용은 평범하고 진지한 우주 다큐멘터리여야 한다. 단지 그 다큐를 열혈 스포츠 중계처럼 과장되고 뜨거운 말투로 낭독하고 있을 뿐이다. 대본 내용 자체가 액션물로 바뀌면 안 됨.)

2. 분량 (절대 엄수): 
   - 전체 대사는 **최소 8문장 이상**으로 풍성하고 길게 작성하라. 내용이 빈약하고 짧게 끝나면 실패한 대본이다.

3. 🚨 줄바꿈 및 대본 형태 (절대 엄수): 
   - **산문(문단) 형태의 작성을 절대 금지한다.**
   - 성우의 호흡을 위해 **모든 문장(마침표, 물음표, 느낌표)이 끝날 때마다 반드시 강제로 줄바꿈(엔터)**을 하라.
   - 한 줄에 여러 문장을 연달아 쓰지 말고, 무조건 **한 줄에 한 문장 혹은 반 문장**만 작성하라.
   - [올바른 출력 예시]:
     낡은 담벼락, 빛바랜 간판,
     그리고 사람들의 이야기가 숨 쉬고 있죠.
     
     :gray[*(미소)*]
     
     마치 잠시 멈춰 서서...

4. 캐릭터 설정: **이름 (나이, 성별, 외형, 말투)** 형식으로 한 줄 요약.
   - 필수 조건: 성별은 **{user_gender}**, 연령대는 **{target_age_group}**.
5. 지문: `:gray[*(지문)*]` 형식으로 대본 전체에서 2~3회만 드물게 사용하며, 지문은 대사와 섞지 말고 단독 줄로 분리하라.
6. 이름 표기: 1인극은 **:blue[이름]**, 2인극은 **:blue[이름]**과 **:green[이름]** 사용. 이름 다음에도 무조건 줄바꿈을 하라.
7. HTML 태그 사용 금지. {genre_guide}

양식:
### 📋 캐릭터 정보
### 📖 연습 대본
"""
        result = None
        with st.spinner("AI가 연습용 대본을 생성중입니다..."):
            result = call_ai(prompt)

        if result == "NO_KEYS":
            st.error("API 키가 없습니다. AI 설정에서 키를 등록해주세요.")
        elif result == "API_KEY_INVALID":
            st.error("🔑 등록된 API 키가 유효하지 않습니다. 오타가 없는지 확인해주세요.")
        elif result == "API_QUOTA_EXHAUSTED":
            st.error("🚫 등록된 모든 API 키의 할당량이 소진되었습니다. 새로운 키를 추가하거나 잠시 후 다시 시도해주세요.")
        elif result and result.startswith("API_ERROR:"):
            st.error(f"오류 발생: {result.replace('API_ERROR:', '')}")
        else:
            if result:
                result = result.replace("\\n", "\n")
                
                # 2차 안전장치: AI가 고집을 부릴 경우를 대비해 파이썬에서 줄바꿈 강제 처리
                # 말줄임표(...) 등을 보호하기 위해 정규식(Regex)을 사용하여 문장 끝에서만 엔터를 치도록 고도화
                result = re.sub(r'(?<=[.?!])\s+(?=[^\n])', '\n\n', result)

                st.session_state.current_script = result

if st.session_state.current_script:
    st.markdown(st.session_state.current_script)
    st.divider()
    st.markdown("### 🎤 내 낭독 인식 내용")
    audio_value = st.audio_input("연습 녹음")
    if audio_value:
        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_value) as source:
                audio_data = r.record(source)
            recognized = r.recognize_google(audio_data, language='ko-KR')
            st.write(f"🗣️ **인식 내용:** {recognized}")
        except sr.UnknownValueError:
            st.error("음성을 인식하지 못했습니다. 더 크고 명확하게 말씀해주세요.")
        except sr.RequestError:
            st.error("음성 인식 서버에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.")
        except Exception as e:
            st.error(f"오류 발생: {str(e)}")