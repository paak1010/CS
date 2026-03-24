import streamlit as st
import pandas as pd
import datetime
import io
import os

st.set_page_config(page_title="통합 수주업로드 시스템", layout="wide")
st.title("📦 편의점 통합 수주업로드 시스템 (원클릭 버전)")
st.markdown("발주 RAW 데이터 **1개만 업로드**하면, 서버에 저장된 마스터 정보를 자동으로 매핑하여 변환합니다.")

# 최종 서식 컬럼 정의
FINAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 'LOT', '특이사항1', 'Type', '특이사항2']
REAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 'LOT', '특이사항', 'Type', '특이사항']

order_date = st.date_input("수주일자 지정", datetime.date.today())
order_date_str = order_date.strftime("%Y%m%d")

def convert_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='서식')
    return output.getvalue()

# [중요] 서버에 미리 올려둔 마스터 파일을 백그라운드에서 자동으로 읽어오는 함수
@st.cache_data
def load_master(file_name):
    try:
        return pd.read_csv(file_name)
    except FileNotFoundError:
        st.error(f"⚠️ 서버에 {file_name} 파일이 없습니다. GitHub에 업로드 해주세요!")
        return pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["🟢 BGF 데이터", "🔵 GS 데이터", "🟠 코리아세븐 데이터"])

# ==========================================
# 탭 1 : BGF
# ==========================================
with tab1:
    bgf_raw = st.file_uploader("🟢 BGF RAW 데이터 업로드 (Excel/CSV)", type=['csv', 'xlsx'], key='b1')
    
    if bgf_raw:
        try:
            # 1. 서버에서 마스터 데이터 몰래 불러오기
            df_product = load_master("bgf_prod.csv")
            df_store = load_master("bgf_store.csv")

            if not df_product.empty and not df_store.empty:
                with st.spinner('변환 중...'):
                    temp_df = pd.read_excel(bgf_raw, nrows=2) if not bgf_raw.name.endswith('.csv') else pd.read_csv(bgf_raw, nrows=2)
                    header_idx = 1 if '번호' in str(temp_df.columns[0]) and '센터 코드' not in str(temp_df.columns[1]) else 0
                    df_raw = pd.read_csv(bgf_raw, header=header_idx) if bgf_raw.name.endswith('.csv') else pd.read_excel(bgf_raw, header=header_idx)

                    # 매핑 로직 (기존과 동일)
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
                    df_final.fillna('', inplace=True)
                    df_final.columns = REAL_COLUMNS

                st.success("✨ 변환 완료!")
                st.download_button("📥 통합 수주업로드 다운로드 (BGF)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_BGF.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 2 : GS
# ==========================================
with tab2:
    gs_raw = st.file_uploader("🔵 GS RAW 데이터 업로드 (Excel/CSV)", type=['csv', 'xlsx'], key='g1')
    
    if gs_raw:
        try:
            df_product = load_master("gs_prod.csv")
            df_store = load_master("gs_store.csv")

            if not df_product.empty and not df_store.empty:
                with st.spinner('변환 중...'):
                    df_raw = pd.read_csv(gs_raw, header=1) if gs_raw.name.endswith('.csv') else pd.read_excel(gs_raw, header=1)
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
                    df_final.fillna('', inplace=True)
                    df_final.columns = REAL_COLUMNS

                st.success("✨ 변환 완료!")
                st.download_button("📥 통합 수주업로드 다운로드 (GS)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_GS.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 3 : 코리아세븐
# ==========================================
with tab3:
    k7_raw = st.file_uploader("🟠 코리아세븐 RAW 업로드 (ORDERS)", type=['csv', 'xlsx'], key='k1')
    
    if k7_raw:
        try:
            df_master = load_master("k7_master.csv")

            if not df_master.empty:
                with st.spinner('변환 중...'):
                    df_raw_k7 = pd.read_csv(k7_raw, header=None) if k7_raw.name.endswith('.csv') else pd.read_excel(k7_raw, header=None)
                    records, current_delivery_date = [], ""

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
                            records.append({'납품일자': current_delivery_date, '바코드': barcode, '점포명': store_name, 'UNIT단가': unit_price, '금       액': total_price, 'UNIT수량': qty})
                    
                    df_k7 = pd.DataFrame(records)
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
                    df_final.fillna('', inplace=True)
                    df_final.columns = REAL_COLUMNS

                st.success("✨ 변환 완료!")
                st.download_button("📥 통합 수주업로드 다운로드 (코리아세븐)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_코리아세븐.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")
