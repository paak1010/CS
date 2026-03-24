import streamlit as st
import pandas as pd
import datetime
import io

st.set_page_config(page_title="통합 수주업로드 자동 변환기", layout="wide")
st.title("📦 편의점 통합 수주업로드 시스템 (BGF/GS/코리아세븐)")
st.markdown("플랫폼별로 다른 발주 데이터를 **동일한 사내 수주업로드 양식**으로 일괄 변환합니다.")

# 공통 최종 서식 컬럼 정의 (스페이스바 공백까지 완벽 유지)
FINAL_COLUMNS = [
    '출고구분', '수주일자', '납품일자', '발주처코드', '배송코드', 
    '상품코드', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 'LOT', 'Invoice NO.'
]

# 공통 수주일자 선택
order_date = st.date_input("수주일자 지정 (공통 적용)", datetime.date.today())
order_date_str = order_date.strftime("%Y%m%d")

def load_data(file, header_idx=0):
    if file.name.endswith('.csv'):
        return pd.read_csv(file, header=header_idx)
    else:
        return pd.read_excel(file, header=header_idx)

def convert_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# 탭 구성
tab1, tab2, tab3 = st.tabs(["🟢 BGF 데이터", "🔵 GS 데이터", "🟠 코리아세븐(세븐일레븐) 데이터"])

# ==========================================
# 탭 1 : BGF 일반/ASN 데이터 처리 (통합)
# ==========================================
with tab1:
    st.subheader("BGF 발주 데이터 처리")
    st.info("💡 일반 DATA 엑셀과 ASN 다운로드 파일 모두 사용 가능합니다. (헤더 자동 인식)")
    c1, c2, c3 = st.columns(3)
    with c1: bgf_raw = st.file_uploader("1. BGF RAW 데이터", type=['csv', 'xlsx'], key='b1')
    with c2: bgf_prod = st.file_uploader("2. BGF 제품코드", type=['csv', 'xlsx'], key='b2')
    with c3: bgf_store = st.file_uploader("3. BGF 점포명", type=['csv', 'xlsx'], key='b3')

    if bgf_raw and bgf_prod and bgf_store:
        try:
            # ASN과 일반 파일 헤더 차이 자동 처리 (1번째 행이 '번호'로 시작하는지 체크)
            temp_df = pd.read_excel(bgf_raw, nrows=2) if not bgf_raw.name.endswith('.csv') else pd.read_csv(bgf_raw, nrows=2)
            header_idx = 1 if '번호' in str(temp_df.columns[0]) and '센터 코드' not in str(temp_df.columns[1]) else 0
            
            df_raw = load_data(bgf_raw, header_idx=header_idx)
            df_product = load_data(bgf_prod)
            df_store = load_data(bgf_store)

            with st.spinner('변환 중...'):
                df_raw['납품일자'] = df_raw['납품예정일자'].astype(str).str[:8]
                df_raw['상품 코드'] = df_raw['상품 코드'].astype(str).str.strip()
                df_product['바코드'] = df_product['바코드'].astype(str).str.strip()
                
                df_mapped = pd.merge(df_raw, df_product[['바코드', '제품코드']].drop_duplicates(), left_on='상품 코드', right_on='바코드', how='left')
                df_mapped = pd.merge(df_mapped, df_store[['점포명', '점포코드']].drop_duplicates(), left_on='센터명', right_on='점포명', how='left')

                df_final = pd.DataFrame(columns=FINAL_COLUMNS)
                df_final['출고구분'] = 0
                df_final['수주일자'] = order_date_str
                df_final['납품일자'] = df_mapped['납품일자']
                df_final['발주처코드'] = df_mapped['점포코드']
                df_final['배송코드'] = df_mapped['점포코드']
                df_final['상품코드'] = df_mapped['제품코드']
                df_final['UNIT수량'] = pd.to_numeric(df_mapped['총수량'], errors='coerce').fillna(0)
                df_final['UNIT단가'] = pd.to_numeric(df_mapped['납품원가'], errors='coerce').fillna(0)
                df_final['금       액'] = df_final['UNIT수량'] * df_final['UNIT단가']
                df_final['부  가   세'] = (df_final['금       액'] * 0.1).astype(int)
                df_final['LOT'] = ''
                df_final['Invoice NO.'] = ''

            st.dataframe(df_final)
            st.download_button("📥 통합 양식 다운로드 (BGF)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_BGF.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 2 : GS 리테일 발주 데이터 처리
# ==========================================
with tab2:
    st.subheader("GS 발주 데이터 처리")
    c1, c2, c3 = st.columns(3)
    with c1: gs_raw = st.file_uploader("1. GS RAW (DATA)", type=['csv', 'xlsx'], key='g1')
    with c2: gs_prod = st.file_uploader("2. GS 제품코드", type=['csv', 'xlsx'], key='g2')
    with c3: gs_store = st.file_uploader("3. GS 점포명", type=['csv', 'xlsx'], key='g3')

    if gs_raw and gs_prod and gs_store:
        try:
            df_raw = load_data(gs_raw, header_idx=1) # GS는 2번째 줄이 헤더
            df_product = load_data(gs_prod)
            df_store = load_data(gs_store)

            with st.spinner('변환 중...'):
                df_raw['납품일자'] = df_raw['납품일자'].astype(str).str.replace('-', '') 
                df_raw['배송처'] = df_raw['배송처'].astype(str).str.strip()
                df_store['점포명'] = df_store['점포명'].astype(str).str.strip()
                
                df_raw['상품코드'] = df_raw['상품코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_product['바코드'] = df_product['바코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

                df_mapped = pd.merge(df_raw, df_store[['점포명', '점포코드']].drop_duplicates(), left_on='배송처', right_on='점포명', how='left')
                df_mapped = pd.merge(df_mapped, df_product[['바코드', '제품코드']].drop_duplicates(), left_on='상품코드', right_on='바코드', how='left')

                df_final = pd.DataFrame(columns=FINAL_COLUMNS)
                df_final['출고구분'] = 0
                df_final['수주일자'] = order_date_str
                df_final['납품일자'] = df_mapped['납품일자']
                df_final['발주처코드'] = df_mapped['점포코드']
                df_final['배송코드'] = df_mapped['점포코드']
                df_final['상품코드'] = df_mapped['제품코드']
                # GS 데이터의 단가와 금액 연산
                df_final['UNIT단가'] = pd.to_numeric(df_mapped['발주단가'], errors='coerce').fillna(0).astype(int)
                df_final['금       액'] = pd.to_numeric(df_mapped['발주금액'], errors='coerce').fillna(0).astype(int)
                df_final['UNIT수량'] = (df_final['금       액'] / df_final['UNIT단가']).fillna(0).astype(int)
                df_final['부  가   세'] = (df_final['금       액'] * 0.1).astype(int)
                df_final['LOT'] = ''
                df_final['Invoice NO.'] = ''

            st.dataframe(df_final)
            st.download_button("📥 통합 양식 다운로드 (GS)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_GS.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 3 : 코리아세븐 (세븐일레븐) 발주 데이터 처리
# ==========================================
with tab3:
    st.subheader("코리아세븐(세븐일레븐) 발주 데이터 처리")
    st.info("💡 코리아세븐은 발주 데이터 형식이 특이하므로, 전용 알고리즘을 통해 납품일자와 수량을 자동 매핑합니다.")
    
    c1, c2 = st.columns(2)
    with c1: k7_raw = st.file_uploader("1. 코리아세븐 RAW (ORDERS...)", type=['csv', 'xlsx'], key='k1')
    with c2: k7_master = st.file_uploader("2. 코리아세븐 마스터 (통합 파일)", type=['csv', 'xlsx'], key='k2')

    if k7_raw and k7_master:
        try:
            with st.spinner('코리아세븐 전용 알고리즘으로 변환 중...'):
                # 1. 헤더 없이 RAW 데이터를 읽어서 순차적 탐색 (위아래 행 묶기)
                df_raw_k7 = load_data(k7_raw, header_idx=None)
                
                records = []
                current_delivery_date = ""

                for idx, row in df_raw_k7.iterrows():
                    col0 = str(row[0]).strip()
                    
                    # 'ORDERS' 행을 만나면 해당 그룹의 납품일자를 메모해 둠
                    if col0 == 'ORDERS':
                        current_delivery_date = str(row[7]).strip().replace('-', '') # 7번째 열이 납품일
                    
                    # 상품 바코드(880~)로 시작하는 행을 만나면 데이터 적재
                    elif str(row[1]).strip().startswith('880'):
                        barcode = str(row[1]).strip()
                        store_name = str(row[3]).strip()
                        
                        # 단가 및 총금액에서 콤마(,) 제거 후 숫자로 변환
                        unit_price = pd.to_numeric(str(row[7]).replace(',', ''), errors='coerce')
                        total_price = pd.to_numeric(str(row[8]).replace(',', ''), errors='coerce')
                        
                        # UNIT수량 역산 (금액 / 단가)
                        qty = int(total_price / unit_price) if unit_price and unit_price > 0 else 0
                        
                        records.append({
                            '납품일자': current_delivery_date,
                            '바코드': barcode,
                            '점포명': store_name,
                            'UNIT단가': unit_price,
                            '금       액': total_price,
                            'UNIT수량': qty
                        })
                
                # 추출된 데이터를 데이터프레임으로 변환
                df_k7 = pd.DataFrame(records)

                # 2. 마스터 파일 매핑
                df_master = load_data(k7_master)
                # 코리아세븐 마스터는 제품정보와 점포정보가 한 파일에 들어있음
                df_k7_prod = df_master[['바코드', '제품코드']].dropna().drop_duplicates()
                df_k7_store = df_master[['점포명', '점포코드']].dropna().drop_duplicates()

                df_k7['바코드'] = df_k7['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)
                df_k7_prod['바코드'] = df_k7_prod['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)

                df_mapped = pd.merge(df_k7, df_k7_prod, on='바코드', how='left')
                df_mapped = pd.merge(df_mapped, df_k7_store, on='점포명', how='left')

                # 3. 최종 통합 양식 구성
                df_final = pd.DataFrame(columns=FINAL_COLUMNS)
                df_final['출고구분'] = 0
                df_final['수주일자'] = order_date_str
                df_final['납품일자'] = df_mapped['납품일자']
                
                # 코리아세븐 특성: 발주처코드는 81032000 고정, 배송코드는 센터별 코드
                df_final['발주처코드'] = 81032000 
                df_final['배송코드'] = df_mapped['점포코드']
                
                df_final['상품코드'] = df_mapped['제품코드']
                df_final['UNIT수량'] = df_mapped['UNIT수량']
                df_final['UNIT단가'] = df_mapped['UNIT단가']
                df_final['금       액'] = df_mapped['금       액']
                df_final['부  가   세'] = (df_final['금       액'] * 0.1).astype(int)
                df_final['LOT'] = ''
                df_final['Invoice NO.'] = ''

            st.dataframe(df_final)
            st.download_button("📥 통합 양식 다운로드 (코리아세븐)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_코리아세븐.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")
