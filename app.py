import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import io
import os
import re

# --- 1. 웹 로고 주소 설정 ---
import streamlit as st

# 로고 URL

# CSS 주입: 로고 이미지의 높이를 강제로 조절 (기본값은 보통 2rem 내외)
st.markdown(
    """
    <style>
        [data-testid="stLogo"] {
            height: 10rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.logo(LOGO_URL)

# --- 2. 페이지 기본 설정 (사이드바 기본 닫힘 적용!) ---
st.set_page_config(page_title="편의점 수주업로드 시스템", page_icon="🏪", layout="wide", initial_sidebar_state="collapsed")

# --- 3. 커스텀 CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;}    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. 로고 및 타이틀 영역 (비율 조정으로 덮어짐 방지) ---
col1, col2 = st.columns([1.5, 8.5])
with col1:
    st.image(LOGO_URL, use_container_width=True) 

with col2:
    st.title("🏪 편의점 수주업로드 자동화 시스템")
    st.markdown("편의점 3사(BGF, GS, 세븐일레븐) Raw Data를 사내 표준 양식으로 자동 변환합니다.")

st.divider() 

# --- 5. 왼쪽 사이드바 (사용 설명서) ---
with st.sidebar:
    st.header("💡 사용 안내")
    st.info("""
    1. 각 편의점 사이트에서 엑셀 데이터 다운로드
    2. GS와 코리아세븐 엑셀 파일: "다른 이름으로 저장" → ".xlsx로 파일 형식 변경" 
    3. 3개의 파일을 우측 업로드 창에 드래그
    4. 자동 입력된 데이터 확인 후 통합 파일 다운로드
    5. 서식업로드 파일 양식에 맞추어 Ctrl+C, Ctrl+Alt+V (값 붙여넣기)
    """)
    st.success("✅ **마스터 파일 연동 완료**\n(서버에서 제품/점포명 자동 참조 중)")
    st.caption("※ 모든 편의점의 수주일자는 무조건 오늘 날짜로 자동 세팅됩니다.")
    st.caption("Developed by Jay")

# --- 6. 데이터 처리 로직 및 업로드 영역 ---
FINAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금        액', '부  가   세', 'LOT', '특이사항1', 'Type', '특이사항2']
REAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금        액', '부  가   세', 'LOT', '특이사항', 'Type', '특이사항']

kst = timezone(timedelta(hours=9))
today_date_str = datetime.now(kst).strftime("%Y%m%d")
today_compact_str = datetime.now(kst).strftime("%Y%m%d")

def format_date_yyyymmdd(val):
    if pd.isna(val) or str(val).strip().lower() in ['nan', '']: return ''
    digits = re.sub(r'\D', '', str(val))
    if len(digits) >= 8: return digits[:8]
    return str(val)

def clean_key(val):
    if pd.isna(val): return ""
    return re.sub(r'\s+', '', str(val).replace('.0', '')).strip()

def find_file(keyword):
    for f in os.listdir('.'):
        if keyword in f and (f.endswith('.xlsx') or f.endswith('.csv')): return f
    return None

@st.cache_data
def load_brain():
    products, stores, missing = {}, {}, []
    bgf_file, gs_file, k7_file = find_file('BGF'), find_file('지에스'), find_file('코리아세븐')
    
    if not bgf_file: missing.append('BGF 서식 엑셀 (이름에 "BGF" 포함 요망)')
    if not gs_file: missing.append('GS 서식 엑셀 (이름에 "지에스" 포함 요망)')
    if not k7_file: missing.append('코리아세븐 서식 엑셀 (이름에 "코리아세븐" 포함 요망)')

    for f in [bgf_file, gs_file, k7_file]:
        if not f: continue
        xls = pd.ExcelFile(f)
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
            df.columns = df.columns.astype(str).str.strip() 
            if '바코드' in df.columns and '제품코드' in df.columns:
                for _, r in df.dropna(subset=['바코드']).iterrows():
                    products[clean_key(r['바코드'])] = {'mecode': str(r['제품코드']).strip(), 'name': str(r['상품명']).strip() if '상품명' in df.columns else ''}
            if '점포명' in df.columns and '점포코드' in df.columns:
                for _, r in df.dropna(subset=['점포명']).iterrows():
                    stores[clean_key(r['점포명'])] = str(r['점포코드']).replace('.0','').strip()
    return products, stores, missing

def detect_and_load(file):
    is_csv = file.name.endswith('.csv')
    df_test = pd.read_csv(file, header=None, nrows=5, dtype=str) if is_csv else pd.read_excel(file, header=None, nrows=5, dtype=str)
    if df_test.empty: return 'UNKNOWN', pd.DataFrame()
    val00 = str(df_test.iloc[0, 0]).strip()
    file.seek(0)
    if val00 == '주문서':
        df = pd.read_csv(file, header=1, dtype=str) if is_csv else pd.read_excel(file, header=1, dtype=str)
        df.columns = df.columns.astype(str).str.strip()
        return 'GS', df
    elif val00 in ['주문서 리스트', '문서명', 'ORDERS']:
        return 'K7', (pd.read_csv(file, header=None, dtype=str) if is_csv else pd.read_excel(file, header=None, dtype=str))
    else:
        df = pd.read_csv(file, header=0, dtype=str) if is_csv else pd.read_excel(file, header=0, dtype=str)
        df.columns = df.columns.astype(str).str.strip()
        if '상품 코드' in df.columns:
            df = df[df['상품 코드'].notna()]
            df = df[~df['상품 코드'].astype(str).str.contains('상품')] 
            df = df[df['상품 코드'].astype(str).str.strip() != '']
            df = df[df['상품 코드'].astype(str).str.strip().str.lower() != 'nan']
        return 'BGF', df

products_dict, stores_dict, missing_files = load_brain()

# 메인 화면 업로드 영역
st.subheader("📥 원본(RAW) 파일 업로드")
if missing_files:
    st.error("❌ 서버에 기준표(마스터 엑셀)가 없습니다! 폴더에 파일이 있는지 확인해주세요.")
    for m in missing_files: st.write(f"- {m}")
else:
    raw_files = st.file_uploader("오늘 처리할 RAW 파일들을 한 번에 모두 끌어다 놓으세요.", accept_multiple_files=True)

if raw_files and not missing_files:
    combined_dfs = []
    for file in raw_files:
        try:
            with st.spinner(f"[{file.name}] 변환 중..."):
                platform, df_raw = detect_and_load(file)
                df_final = pd.DataFrame()
                
                if platform == 'BGF':
                    df_final['납품일자'] = df_raw.get('납품예정일자', pd.Series(dtype=str)).apply(format_date_yyyymmdd)
                    df_final['수주일자'] = today_date_str
                    df_final['발주처'] = df_raw['센터명'].astype(str).str.strip()
                    df_final['배송지'] = df_final['발주처']
                    df_final['발주처코드'] = df_raw['센터명'].apply(lambda x: stores_dict.get(clean_key(x), ''))
                    df_final['배송코드'] = df_final['발주처코드']
                    df_final['상품코드'] = df_raw['상품 코드'].apply(lambda x: products_dict.get(clean_key(x), {}).get('mecode', ''))
                    df_final['상품명'] = df_raw['상품 코드'].apply(lambda x: products_dict.get(clean_key(x), {}).get('name', ''))
                    mask = df_final['상품명'] == ''
                    if '상품명' in df_raw.columns: df_final.loc[mask, '상품명'] = df_raw.loc[mask, '상품명']
                    df_final['UNIT수량'] = pd.to_numeric(df_raw['총수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
                    df_final['UNIT단가'] = pd.to_numeric(df_raw['납품원가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
                    df_final['금        액'] = df_final['UNIT수량'] * df_final['UNIT단가']
                    
                elif platform == 'GS':
                    df_final['납품일자'] = df_raw.get('납품일자', pd.Series(dtype=str)).apply(format_date_yyyymmdd)
                    df_final['수주일자'] = today_date_str
                    if '납품처' in df_raw.columns: df_final['발주처'] = df_raw['납품처'].astype(str).str.strip()
                    else: df_final['발주처'] = df_raw['배송처'].astype(str).str.strip()
                    df_final['배송지'] = df_final['발주처']
                    df_final['발주처코드'] = df_final['발주처'].apply(lambda x: stores_dict.get(clean_key(x), ''))
                    df_final['배송코드'] = df_final['발주처코드']
                    df_final['상품코드'] = df_raw['상품코드'].apply(lambda x: products_dict.get(clean_key(x), {}).get('mecode', ''))
                    df_final['상품명'] = df_raw['상품코드'].apply(lambda x: products_dict.get(clean_key(x), {}).get('name', ''))
                    mask = df_final['상품명'] == ''
                    if '상품명_x' in df_raw.columns: df_final.loc[mask, '상품명'] = df_raw.loc[mask, '상품명_x']
                    elif '상품명' in df_raw.columns: df_final.loc[mask, '상품명'] = df_raw.loc[mask, '상품명']
                    df_final['UNIT단가'] = pd.to_numeric(df_raw['발주단가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
                    df_final['금        액'] = pd.to_numeric(df_raw['발주금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
                    df_final['UNIT수량'] = (df_final['금        액'] / df_final['UNIT단가'].replace(0, 1)).astype(int)

                elif platform == 'K7':
                    records, current_delivery_date = [], ""
                    for idx, row in df_raw.iterrows():
                        col0 = str(row[0]).strip()
                        if col0 == 'ORDERS':
                            current_delivery_date = format_date_yyyymmdd(row[7]) if len(row) > 7 else ""
                        elif str(row[1]).strip().startswith('880') or str(row[0]).replace('.0', '').isdigit():
                            barcode = clean_key(row[1])
                            store = str(row[3]).strip()
                            price = pd.to_numeric(str(row[7]).replace(',', ''), errors='coerce')
                            total = pd.to_numeric(str(row[8]).replace(',', ''), errors='coerce')
                            qty = int(total / price) if pd.notna(price) and price > 0 else 0
                            records.append({'수주일자': today_date_str, '납품일자': current_delivery_date, '바코드': barcode, '점포명': store, 'UNIT단가': price if pd.notna(price) else 0, '금        액': total if pd.notna(total) else 0, 'UNIT수량': qty})
                    
                    df_k7 = pd.DataFrame(records)
                    if not df_k7.empty:
                        df_final['납품일자'] = df_k7['납품일자']
                        df_final['수주일자'] = df_k7['수주일자']
                        df_final['발주처코드'] = '81032000'
                        df_final['발주처'] = "(주)코리아세븐"
                        df_final['배송지'] = df_k7['점포명']
                        df_final['배송코드'] = df_k7['점포명'].apply(lambda x: stores_dict.get(clean_key(x), ''))
                        df_final['상품코드'] = df_k7['바코드'].apply(lambda x: products_dict.get(x, {}).get('mecode', ''))
                        df_final['상품명'] = df_k7['바코드'].apply(lambda x: products_dict.get(x, {}).get('name', ''))
                        df_final['UNIT수량'] = df_k7['UNIT수량']
                        df_final['UNIT단가'] = df_k7['UNIT단가']
                        df_final['금        액'] = df_k7['금        액']

                st.toast(f"✅ {file.name} ({platform}) 변환 성공!")
                combined_dfs.append(df_final)

        except Exception as e:
            st.error(f"❌ {file.name} 처리 중 오류가 발생했습니다: {e}")

    if combined_dfs:
        st.write("---")
        st.subheader("📊 편의점 통합 데이터 미리보기")
        
        df_combined = pd.concat(combined_dfs, ignore_index=True)
        df_combined['출고구분'] = 0
        if '금        액' in df_combined.columns:
            df_combined['부  가   세'] = (pd.to_numeric(df_combined['금        액'], errors='coerce').fillna(0) * 0.1).astype(int)
        
        for col in FINAL_COLUMNS:
            if col not in df_combined.columns: df_combined[col] = ''
        
        df_combined = df_combined[FINAL_COLUMNS]
        df_combined.fillna('', inplace=True)

        st.dataframe(df_combined, use_container_width=True, height=400)
        
        df_excel = df_combined.copy()
        df_excel.columns = REAL_COLUMNS
        
        # --- 추가된 핵심 로직: 특정 컬럼을 엑셀에서 순수 숫자로 강제 변환 ---
        cols_to_numeric = ['수주일자', '납품일자', '발주처코드', '배송코드']
        for col in cols_to_numeric:
            if col in df_excel.columns:
                # errors='coerce'로 문자는 무시하고, astype('Int64')를 써서 빈 칸이 있어도 .0 소수점이 안 붙게 함
                df_excel[col] = pd.to_numeric(df_excel[col], errors='coerce').astype('Int64')
        # -----------------------------------------------------------------
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_excel.to_excel(writer, index=False, sheet_name='서식')
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            st.download_button(
                label=f"📥 통합 수주업로드 일괄 다운로드 (총 {len(df_combined)}건)",
                data=output.getvalue(),
                file_name=f"통합_수주업로드_{today_compact_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )

# --- 7. 하단 개발자 서명 ---
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #a0a0a0; font-size: 0.9rem; font-family: sans-serif;'>developed by Jay</div>", unsafe_allow_html=True)
