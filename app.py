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
    "내레이션": "KBS/EBS 다큐멘터리나 오디오북처럼 극도로 정제된 문어체. 감정을 배제하고 철저히 객관적이고 신뢰감 있는 정보 전달이나 서사를 진행할 것. 무겁고 진지하며 고급스러운 어휘 사용.",
    "게임": "AAA급 대작 RPG 게임의 시네마틱 컷씬이나 보스전 직전에 나올 법한 비장하고 서사적이며 무게감 있는 대사. 세계관의 깊이가 느껴지게 작성할 것.",
    "광고": "유튜브 스킵 불가 광고나 TV 상업/공익 광고처럼 짧고 자극적인 훅(Hook). 소비자의 이목을 단번에 끄는 카피라이팅 중심의 역동적이고 세일즈 목적이 뚜렷한 대사.",
    "라디오 드라마": "오직 목소리만으로 상황과 공간감이 느껴져야 함. 효과음(문 열리는 소리, 발소리 등)이 연상되는 아주 일상적이고 자연스러운 구어체와 호흡 중심.",
    "어색한 대본": "성우의 발음과 순발력을 테스트하기 위해, 발음하기 매우 어려운 단어들의 연속, 잰말놀이(간장공장 공장장 등), 의도적으로 문맥이 꼬여있는 아나운서 테스트용 글."
}

# 🚨 무한한 다양성을 위한 랜덤 키워드 풀 (서로 조합되어 완전히 새로운 소재 창조)
CORE_KEYWORDS = [
    "시간", "기억", "우주", "심해", "요리", "음악", "꿈", "기계", "마법", "자연", 
    "도시", "학교", "가족", "비밀", "여행", "동물", "거울", "그림자", "빛", "어둠", 
    "소리", "침묵", "기후", "역사", "신화", "스포츠", "돈", "권력", "사랑", "이별", 
    "질투", "희생", "인공지능", "외계인", "바이러스", "진화", "멸종", "전쟁", "평화", 
    "축제", "장례식", "결혼", "도둑", "경찰", "탐정", "보물", "저주", "축복", "사막", 
    "빙하", "정글", "화산", "거짓말", "진실", "기차", "편지", "거인", "소인", "착각"
]

PERSONALITIES = [
    # 긍정 / 밝음 / 따뜻함
    "명랑, 긍정 에너지가 넘치고 해맑은", "다정다감, 따뜻하고 배려심 깊은", 
    "순수, 아이같이 티 없고 솔직한", "친절, 누구에게나 상냥한 톤의", 
    "호탕, 시원시원하고 털털한", "열정적, 꿈을 향해 달리는 희망찬",
    "듬직, 언제나 내 편이 되어주는 든든한", "당돌, 할 말 상상 다 하는 사이다 같은",
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
# 🚨 버튼 순서를 변경하기 위해 col_setup과 col_info의 배치 순서를 바꿨습니다.
col_title, col_setup, col_info = st.columns([5, 1.5, 1.5])

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

# 🚨 오른쪽 끝으로 이동한 'API 키란?' 섹션
with col_info:
    with st.popover("❓ API 키란?"):
        st.markdown("### 🔑 API 키란?")
        st.write("API 키는 AI 서비스를 사용하기 위해 필요한 일종의 **'출입증'**입니다. 이 앱이 Google이나 OpenAI의 인공지능 모델에 접속해서 대본을 생성할 수 있도록 권한을 부여하는 역할을 합니다.")
        
        st.divider()
        
        st.markdown("### 🌟 Gemini API 키 무료 발급 가이드")
        st.markdown("1. [Google AI Studio (링크)](https://aistudio.google.com/app/apikey)에 접속하여 구글 계정으로 로그인합니다.")
        st.markdown("2. 화면 좌측 또는 상단의 **'Get API key'** 메뉴를 클릭합니다.")
        st.markdown("3. 파란색 **'Create API key'** 버튼을 누르고 새 프로젝트에서 키를 생성합니다.")
        st.markdown("4. 화면에 나타난 긴 문자열(`AIza...`로 시작)을 복사합니다.")
        st.markdown("5. 현재 창으로 돌아와 옆의 **[⚙️ AI 설정]** 메뉴를 누르고 복사한 키를 등록해주세요!")

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
        
        genre_writing_guide = GENRE_WRITING_GUIDES.get(final_main, "")
        
        kw1, kw2 = random.sample(CORE_KEYWORDS, 2)

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

        prompt = f"""
당신은 대한민국 최고의 [{final_main}] 장르 전문 대본 작가입니다.
이번에 집필할 대본의 장르는 [{final_main} {sub_text}], 스타일은 [{p_style}]입니다.

[강제 부여 캐릭터 설정]
- 성별: {user_gender}
- 연령: {target_age_group}
- 성격 및 말투 컨셉: {target_personality}

[대본 집필 핵심 원칙 (절대 엄수)]
1. 🚨 무한한 다양성을 위한 랜덤 키워드 융합 (가장 중요):
   - 이번 대본은 반드시 **[{kw1}]**와(과) **[{kw2}]**이라는 두 가지 키워드를 결합하여 독창적인 상황과 주제를 창작하십시오.
   - 키워드 단어 자체를 대본에 꼭 적을 필요는 없습니다. 이 두 단어에서 파생되는 '상황, 배경, 소재, 갈등'을 활용해 상상력을 발휘하십시오.
   - 장르의 뻔한 클리셰(예: 다큐멘터리=철학/문명 비판, 애니=마왕성 등)에 절대 갇히지 말고, 매번 위 키워드를 바탕으로 한 완전히 새로운 디테일의 대본을 쓰십시오.

2. 🚨 장르적 특성의 절대 유지:
   - 소재가 무엇이든 글의 문체와 형태는 아래 가이드를 100% 따르십시오.
   - {genre_writing_guide}

3. 🚨 캐릭터 설정과 대본 내용의 '완벽한 차단':
   - 당신은 대본 작가일 뿐, 성우가 누구인지 신경 쓰지 마십시오!
   - 성우의 성격(예: 껄렁함, 다정함 등)이나 나이(10대, 60대 등)에 맞춰서 대본 자체의 말투, 어휘, 내용을 변질시키면 안 됩니다. 대본은 오직 선택된 장르의 정통성을 유지해야 합니다.

4. 분량 및 대본 형태 (절대 엄수): 
   - 전체 대사는 **최소 8문장 이상**으로 길게 작성하십시오.
   - 산문(문단) 형태를 절대 금지합니다. **모든 문장(마침표, 물음표, 느낌표)이 끝날 때마다 반드시 강제로 줄바꿈(엔터)**을 하십시오.
   - 지문은 `:gray[*(지문)*]` 형식으로 대본 전체에서 2~3회만 단독 줄로 분리하십시오.
   - 이름 표기: 1인극은 **:blue[이름]**, 2인극은 **:blue[이름]**과 **:green[이름]** 사용. 이름 다음에도 무조건 줄바꿈.

5. 🚨 캐릭터 정보 창작 규칙:
   - 아래 양식의 '[창작할 이름]'과 '[구체적인 외형 묘사]' 빈칸을 직접 지어내어 채워 넣으십시오.
   - 절대 '이름'이나 '[외형 창작]'이라는 단어를 글자 그대로 출력하지 마십시오.

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