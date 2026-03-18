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

# 카테고리 데이터
CATEGORIES = {
    "애니메이션": ["판타지", "액션", "일상", "로맨스", "SF", "코미디", "스포츠", "시대극"],
    "내레이션": ["다큐멘터리", "드라마", "오디오북"],
    "게임": [],
    "광고": ["상업광고", "공익광고", "기업홍보"],
    "라디오 드라마": [],
    "어색한 대본": []
}

# 장르적 특성을 극대화하기 위한 '장르별 전용 작법 가이드'
GENRE_WRITING_GUIDES = {
    "애니메이션": "일본 애니메이션이나 웹툰 특유의 과장되고 극적인 대사, 감정이 폭발하는 독백이나 대화 위주. 일상적인 말투보다는 만화적인 상상력과 서사가 돋보이게 작성할 것.",
    "내레이션": "KBS/EBS 다큐멘터리나 오디오북처럼 극도로 정제된 문어체. 감정을 배제한 철학적이거나 객관적인 정보 전달, 무겁고 진지하고 고급스러운 어휘만 사용할 것.",
    "게임": "AAA급 대작 RPG 게임의 시네마틱 컷씬이나 보스전 직전에 나올 법한 비장하고 서사적이며 무게감 있는 대사. 세계관의 깊이가 느껴지게 작성할 것.",
    "광고": "유튜브 스킵 불가 광고나 TV 상업/공익 광고처럼 짧고 자극적인 훅(Hook). 소비자의 이목을 단번에 끄는 카피라이팅 중심의 역동적이고 세일즈 목적이 뚜렷한 대사.",
    "라디오 드라마": "오직 목소리만으로 상황과 공간감이 느껴져야 함. 효과음(문 열리는 소리, 발소리 등)이 연상되는 아주 일상적이고 자연스러운 구어체와 호흡 중심.",
    "어색한 대본": "성우의 발음과 순발력을 테스트하기 위해, 발음하기 매우 어려운 단어들의 연속, 잰말놀이(간장공장 공장장 등), 의도적으로 문맥이 꼬여있는 아나운서 테스트용 글."
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
        
        # 장르 작법 가이드 가져오기
        genre_writing_guide = GENRE_WRITING_GUIDES.get(final_main, "")

        # 나이대 4구간 중 하나를 선택한 뒤, 해당 구간 안에서 구체적인 나이를 랜덤으로 뽑습니다.
        age_ranges = [
            (7, 19),   # 소년/소녀 (10대 이하)
            (20, 39),  # 청년 (20~30대)
            (40, 59),  # 중년 (40~50대)
            (60, 85)   # 노년 (60대 이상)
        ]
        selected_range = random.choice(age_ranges)
        specific_age = random.randint(selected_range[0], selected_range[1])
        target_age_group = f"{specific_age}세"
        
        target_personality = random.choice(PERSONALITIES)

        # 🚨 프롬프트: 이름과 외형을 AI가 직접 지어내도록 확실하게 지시문 변경
        prompt = f"""
당신은 대한민국 최고의 [{final_main}] 장르 전문 대본 작가입니다.
이번에 집필할 대본의 장르는 [{final_main} {sub_text}], 스타일은 [{p_style}]입니다.

[강제 부여 캐릭터 설정]
- 성별: {user_gender}
- 연령: {target_age_group}
- 성격 및 말투 컨셉: {target_personality}

[대본 집필 핵심 원칙 (절대 엄수)]
1. 🚨 캐릭터 설정과 대본 내용의 '완벽한 차단':
   - 당신은 글을 쓰는 작가일 뿐, 이 대본을 어떤 성우가 읽게 될지(나이, 성격 등)는 절대 신경 쓰지 마십시오!
   - 하단에 표시될 성우의 성격(예: 껄렁함, 다정함 등)이나 나이(예: 10대, 60대 등)에 맞춰서 대본의 말투나 내용을 유치하게 바꾸거나 변질시키면 절대 안 됩니다. 
   - 대본의 어휘, 분위기, 상황은 오직 아래 [장르별 작법 가이드]에만 100% 종속되어야 합니다.

2. 🚨 장르별 작법 가이드 ({final_main}):
   - {genre_writing_guide}
   - 이전 장르의 느낌이 1%라도 섞이면 안 됩니다. 무조건 위 가이드라인에 명시된 특징을 극대화하여 정통 스타일로 쓰십시오.

3. 분량 및 대본 형태 (절대 엄수): 
   - 전체 대사는 **최소 8문장 이상**으로 풍성하고 깊이 있게 작성하십시오.
   - 산문(문단) 형태의 작성을 절대 금지합니다.
   - 성우의 호흡을 위해 **모든 문장(마침표, 물음표, 느낌표)이 끝날 때마다 반드시 강제로 줄바꿈(엔터)**을 하십시오. 한 줄에 여러 문장을 쓰지 마십시오.
   - 지문은 `:gray[*(지문)*]` 형식으로 대본 전체에서 2~3회만 단독 줄로 분리하십시오.
   - 이름 표기: 1인극은 **:blue[이름]**, 2인극은 **:blue[이름]**과 **:green[이름]** 사용. 이름 다음에도 무조건 줄바꿈.

4. 🚨 캐릭터 정보 창작 규칙 (매우 중요):
   - 아래 양식의 '[창작할 이름]'과 '[구체적인 외형 묘사]' 부분은 빈칸입니다. AI가 직접 극의 분위기에 어울리는 이름과 옷차림/인상착의를 지어내어 채워 넣어야 합니다.
   - 절대 '이름'이나 '[외형 창작]'이라는 단어를 글자 그대로 출력하지 마십시오. (올바른 예시: 김철수 (24세, 남성, 낡은 트렌치코트를 입고 피곤한 눈매를 가진, 다정다감한...))
   - 대본에 등장하는 인물의 이름과 캐릭터 정보의 이름을 정확하게 일치시키십시오.

[출력 양식]
### 📋 캐릭터 정보
[창작할 이름] ({target_age_group}, {user_gender}, [구체적인 외형 묘사], {target_personality})

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
                
                # 2차 안전장치: 마침표/물음표/느낌표 뒤에 줄바꿈 강제 처리
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