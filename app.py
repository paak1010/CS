import streamlit as st
import pandas as pd
import datetime
import io

st.set_page_config(page_title="통합 수주업로드 자동 변환기", layout="wide")
st.title("📦 편의점 통합 수주업로드 시스템 (최종본)")
st.markdown("BGF, GS, 코리아세븐 발주 데이터를 **사내 최종 수주업로드 서식**으로 일괄 변환합니다.")

# 최종 서식 컬럼 정의 (스페이스 공백 및 중복된 '특이사항' 컬럼명까지 원본 완벽 반영)
FINAL_COLUMNS = [
    '출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', 
    '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 
    'LOT', '특이사항1', 'Type', '특이사항2'
]
REAL_COLUMNS = [
    '출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', 
    '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 
    'LOT', '특이사항', 'Type', '특이사항'
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
        df.to_excel(writer, index=False, sheet_name='서식')
    return output.getvalue()

# 탭 구성
tab1, tab2, tab3 = st.tabs(["🟢 BGF 데이터", "🔵 GS 데이터", "🟠 코리아세븐 데이터"])

# ==========================================
# 탭 1 : BGF 발주 데이터 처리 (일반/ASN 통합)
# ==========================================
with tab1:
    st.subheader("BGF 발주 데이터 처리")
    c1, c2, c3 = st.columns(3)
    with c1: bgf_raw = st.file_uploader("1. BGF RAW", type=['csv', 'xlsx'], key='b1')
    with c2: bgf_prod = st.file_uploader("2. BGF 제품코드", type=['csv', 'xlsx'], key='b2')
    with c3: bgf_store = st.file_uploader("3. BGF 점포명", type=['csv', 'xlsx'], key='b3')

    if bgf_raw and bgf_prod and bgf_store:
        try:
            temp_df = pd.read_excel(bgf_raw, nrows=2) if not bgf_raw.name.endswith('.csv') else pd.read_csv(bgf_raw, nrows=2)
            header_idx = 1 if '번호' in str(temp_df.columns[0]) and '센터 코드' not in str(temp_df.columns[1]) else 0
            
            df_raw = load_data(bgf_raw, header_idx=header_idx)
            df_product = load_data(bgf_prod)
            df_store = load_data(bgf_store)

            with st.spinner('최종 서식으로 변환 중...'):
                df_raw['납품일자'] = df_raw['납품예정일자'].astype(str).str[:8]
                df_raw['상품 코드'] = df_raw['상품 코드'].astype(str).str.strip()
                df_product['바코드'] = df_product['바코드'].astype(str).str.strip()
                
                df_mapped = pd.merge(df_raw, df_product[['바코드', '제품코드', '상품명']].drop_duplicates('바코드'), left_on='상품 코드', right_on='바코드', how='left')
                df_mapped = pd.merge(df_mapped, df_store[['점포명', '점포코드']].drop_duplicates(), left_on='센터명', right_on='점포명', how='left')

                df_final = pd.DataFrame(columns=FINAL_COLUMNS)
                df_final['출고구분'] = 0
                df_final['수주일자'] = order_date_str
                df_final['납품일자'] = df_mapped['납품일자']
                df_final['발주처코드'] = df_mapped['점포코드']
                df_final['발주처'] = df_mapped['센터명']
                df_final['배송코드'] = df_mapped['점포코드']
                df_final['배송지'] = df_mapped['센터명']
                df_final['상품코드'] = df_mapped['제품코드']
                df_final['상품명'] = df_mapped['상품명_y'] if '상품명_y' in df_mapped.columns else df_mapped['상품명']
                df_final['UNIT수량'] = pd.to_numeric(df_mapped['총수량'], errors='coerce').fillna(0).astype(int)
                df_final['UNIT단가'] = pd.to_numeric(df_mapped['납품원가'], errors='coerce').fillna(0).astype(int)
                df_final['금       액'] = df_final['UNIT수량'] * df_final['UNIT단가']
                df_final['부  가   세'] = (df_final['금       액'] * 0.1).astype(int)
                df_final['LOT'] = ''
                df_final['특이사항1'] = ''
                df_final['Type'] = ''
                df_final['특이사항2'] = ''
                
                df_final.columns = REAL_COLUMNS

            st.dataframe(df_final)
            st.download_button("📥 통합 수주업로드 다운로드 (BGF)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_BGF.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 2 : GS 리테일 발주 데이터 처리
# ==========================================
with tab2:
    st.subheader("GS 발주 데이터 처리")
    c1, c2, c3 = st.columns(3)
    with c1: gs_raw = st.file_uploader("1. GS RAW", type=['csv', 'xlsx'], key='g1')
    with c2: gs_prod = st.file_uploader("2. GS 제품코드", type=['csv', 'xlsx'], key='g2')
    with c3: gs_store = st.file_uploader("3. GS 점포명", type=['csv', 'xlsx'], key='g3')

    if gs_raw and gs_prod and gs_store:
        try:
            df_raw = load_data(gs_raw, header_idx=1) 
            df_product = load_data(gs_prod)
            df_store = load_data(gs_store)

            with st.spinner('최종 서식으로 변환 중...'):
                df_raw['납품일자'] = df_raw['납품일자'].astype(str).str.replace('-', '') 
                df_raw['배송처'] = df_raw['배송처'].astype(str).str.strip()
                df_store['점포명'] = df_store['점포명'].astype(str).str.strip()
                
                df_raw['상품코드'] = df_raw['상품코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_product['바코드'] = df_product['바코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

                df_mapped = pd.merge(df_raw, df_store[['점포명', '점포코드']].drop_duplicates(), left_on='배송처', right_on='점포명', how='left')
                df_mapped = pd.merge(df_mapped, df_product[['바코드', '제품코드', '상품명']].drop_duplicates('바코드'), left_on='상품코드', right_on='바코드', how='left')

                df_final = pd.DataFrame(columns=FINAL_COLUMNS)
                df_final['출고구분'] = 0
                df_final['수주일자'] = order_date_str
                df_final['납품일자'] = df_mapped['납품일자']
                df_final['발주처코드'] = df_mapped['점포코드']
                df_final['발주처'] = df_mapped['배송처']
                df_final['배송코드'] = df_mapped['점포코드']
                df_final['배송지'] = df_mapped['배송처']
                df_final['상품코드'] = df_mapped['제품코드']
                df_final['상품명'] = df_mapped['상품명_y'] if '상품명_y' in df_mapped.columns else df_mapped['상품명']
                df_final['UNIT단가'] = pd.to_numeric(df_mapped['발주단가'], errors='coerce').fillna(0).astype(int)
                df_final['금       액'] = pd.to_numeric(df_mapped['발주금액'], errors='coerce').fillna(0).astype(int)
                df_final['UNIT수량'] = (df_final['금       액'] / df_final['UNIT단가']).fillna(0).astype(int)
                df_final['부  가   세'] = (df_final['금       액'] * 0.1).astype(int)
                df_final['LOT'] = ''
                df_final['특이사항1'] = ''
                df_final['Type'] = ''
                df_final['특이사항2'] = ''

                df_final.columns = REAL_COLUMNS

            st.dataframe(df_final)
            st.download_button("📥 통합 수주업로드 다운로드 (GS)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_GS.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 3 : 코리아세븐 발주 데이터 처리
# ==========================================
with tab3:
    st.subheader("코리아세븐 발주 데이터 처리")
    c1, c2 = st.columns(2)
    with c1: k7_raw = st.file_uploader("1. 코리아세븐 RAW", type=['csv', 'xlsx'], key='k1')
    with c2: k7_master = st.file_uploader("2. 코리아세븐 마스터", type=['csv', 'xlsx'], key='k2')

    if k7_raw and k7_master:
        try:
            with st.spinner('최종 서식으로 변환 중...'):
                df_raw_k7 = load_data(k7_raw, header_idx=None)
                
                records = []
                current_delivery_date = ""

                for idx, row in df_raw_k7.iterrows():
                    col0 = str(row[0]).strip()
                    if col0 == 'ORDERS':
                        current_delivery_date = str(row[7]).strip().replace('-', '')
                    
                    elif str(row[1]).strip().startswith('880'):
                        barcode = str(row[1]).strip()
                        store_name = str(row[3]).strip()
                        unit_price = pd.to_numeric(str(row[7]).replace(',', ''), errors='coerce')
                        total_price = pd.to_numeric(str(row[8]).replace(',', ''), errors='coerce')
                        qty = int(total_price / unit_price) if unit_price and unit_price > 0 else 0
                        
                        records.append({
                            '납품일자': current_delivery_date,
                            '바코드': barcode,
                            '점포명': store_name,
                            'UNIT단가': unit_price,
                            '금       액': total_price,
                            'UNIT수량': qty
                        })
                
                df_k7 = pd.DataFrame(records)
                df_master = load_data(k7_master)
                
                df_k7_prod = df_master[['바코드', '제품코드', '상품명']].dropna(subset=['바코드']).drop_duplicates('바코드')
                df_k7_store = df_master[['점포명', '점포코드']].dropna(subset=['점포명']).drop_duplicates('점포명')

                df_k7['바코드'] = df_k7['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)
                df_k7_prod['바코드'] = df_k7_prod['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)

                df_mapped = pd.merge(df_k7, df_k7_prod, on='바코드', how='left')
                df_mapped = pd.merge(df_mapped, df_k7_store, on='점포명', how='left')

                df_final = pd.DataFrame(columns=FINAL_COLUMNS)
                df_final['출고구분'] = 0
                df_final['수주일자'] = order_date_str
                df_final['납품일자'] = df_mapped['납품일자']
                df_final['발주처코드'] = 81032000 
                df_final['발주처'] = "(주)코리아세븐"
                df_final['배송코드'] = df_mapped['점포코드']
                df_final['배송지'] = df_mapped['점포명_x'] if '점포명_x' in df_mapped.columns else df_mapped['점포명']
                df_final['상품코드'] = df_mapped['제품코드']
                df_final['상품명'] = df_mapped['상품명']
                df_final['UNIT수량'] = df_mapped['UNIT수량']
                df_final['UNIT단가'] = df_mapped['UNIT단가']
                df_final['금       액'] = df_mapped['금       액']
                df_final['부  가   세'] = (df_final['금       액'] * 0.1).astype(int)
                df_final['LOT'] = ''
                df_final['특이사항1'] = ''
                df_final['Type'] = ''
                df_final['특이사항2'] = ''

                df_final.columns = REAL_COLUMNS

            st.dataframe(df_final)
            st.download_button("📥 통합 수주업로드 다운로드 (코리아세븐)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_코리아세븐.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")
