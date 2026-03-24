import streamlit as st
import pandas as pd
import datetime
import io

st.set_page_config(page_title="통합 수주업로드 자동 변환기", layout="wide")
st.title("📦 편의점 통합 수주업로드 (단일 파일 버전)")
st.markdown("RAW 데이터를 붙여넣은 **서식 엑셀 파일 딱 1개**만 업로드하세요. 파일 안의 [제품코드], [점포명] 시트를 자동으로 참조하여 엑셀을 완성합니다.")

FINAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 'LOT', '특이사항1', 'Type', '특이사항2']
REAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 'LOT', '특이사항', 'Type', '특이사항']

order_date = st.date_input("수주일자 지정 (공통 적용)", datetime.date.today())
order_date_str = order_date.strftime("%Y%m%d")

def convert_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='서식')
    return output.getvalue()

# 엑셀 파일 안에서 키워드로 시트 이름을 찾아주는 마법의 함수
def get_sheet_name(sheets, keywords):
    for s in sheets:
        for k in keywords:
            if k.lower() in s.lower():
                return s
    return None

tab1, tab2, tab3 = st.tabs(["🟢 BGF 데이터", "🔵 GS 데이터", "🟠 코리아세븐 데이터"])

# ==========================================
# 탭 1 : BGF (파일 1개 업로드)
# ==========================================
with tab1:
    bgf_file = st.file_uploader("🟢 BGF 엑셀 파일 업로드 (내부에 DATA, 제품코드, 점포명 시트 포함)", type=['xlsx'], key='b1')
    if bgf_file:
        try:
            xls = pd.ExcelFile(bgf_file)
            sheets = xls.sheet_names
            
            # 시트 이름 자동 인식
            s_data = get_sheet_name(sheets, ['data', 'raw'])
            s_prod = get_sheet_name(sheets, ['제품', '상품'])
            s_store = get_sheet_name(sheets, ['점포', '센터'])
            
            if not s_data or not s_prod or not s_store:
                st.error(f"⚠️ 엑셀 파일 안에서 필수 시트를 찾지 못했습니다. (현재 엑셀에 있는 시트: {sheets})")
            else:
                with st.spinner("엑셀 안의 시트들을 자동으로 참조하고 있습니다..."):
                    # ASN 파일처럼 첫 줄이 비어있거나 번호가 있는 경우 자동 인식
                    temp_df = pd.read_excel(xls, sheet_name=s_data, nrows=2)
                    header_idx = 1 if '번호' in str(temp_df.columns[0]) and '센터 코드' not in str(temp_df.columns[1]) else 0
                    
                    df_raw = pd.read_excel(xls, sheet_name=s_data, header=header_idx)
                    df_product = pd.read_excel(xls, sheet_name=s_prod)
                    df_store = pd.read_excel(xls, sheet_name=s_store)

                    # 전처리 및 병합
                    df_raw['납품일자'] = df_raw['납품예정일자'].astype(str).str[:8]
                    df_raw['상품 코드'] = df_raw['상품 코드'].astype(str).str.strip()
                    df_product['바코드'] = df_product['바코드'].astype(str).str.strip()
                    
                    df_mapped = pd.merge(df_raw, df_product[['바코드', '제품코드', '상품명']].drop_duplicates('바코드'), left_on='상품 코드', right_on='바코드', how='left')
                    df_mapped = pd.merge(df_mapped, df_store[['점포명', '점포코드']].drop_duplicates(), left_on='센터명', right_on='점포명', how='left')

                    # 최종 서식
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

                st.success(f"✨ 변환 완료! (참조한 시트: 원본[{s_data}], 제품[{s_prod}], 점포[{s_store}])")
                st.download_button("📥 통합 수주업로드 다운로드 (BGF)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_BGF.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 2 : GS (파일 1개 업로드)
# ==========================================
with tab2:
    gs_file = st.file_uploader("🔵 GS 엑셀 파일 업로드 (내부에 DATA, 제품코드, 점포명 시트 포함)", type=['xlsx'], key='g1')
    if gs_file:
        try:
            xls = pd.ExcelFile(gs_file)
            sheets = xls.sheet_names
            
            s_data = get_sheet_name(sheets, ['data', 'raw'])
            s_prod = get_sheet_name(sheets, ['제품', '상품'])
            s_store = get_sheet_name(sheets, ['점포', '센터'])
            
            if not s_data or not s_prod or not s_store:
                st.error(f"⚠️ 엑셀 파일 안에서 필수 시트를 찾지 못했습니다. (현재 엑셀에 있는 시트: {sheets})")
            else:
                with st.spinner("엑셀 안의 시트들을 자동으로 참조하고 있습니다..."):
                    # GS는 주문서 글자 때문에 2번째 줄(header=1)부터 인식
                    temp_df = pd.read_excel(xls, sheet_name=s_data, nrows=2)
                    header_idx = 1 if '주문서' in str(temp_df.columns[0]) else 0
                    
                    df_raw = pd.read_excel(xls, sheet_name=s_data, header=header_idx)
                    df_product = pd.read_excel(xls, sheet_name=s_prod)
                    df_store = pd.read_excel(xls, sheet_name=s_store)

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

                st.success(f"✨ 변환 완료! (참조한 시트: 원본[{s_data}], 제품[{s_prod}], 점포[{s_store}])")
                st.download_button("📥 통합 수주업로드 다운로드 (GS)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_GS.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 탭 3 : 코리아세븐 (파일 1개 업로드)
# ==========================================
with tab3:
    k7_file = st.file_uploader("🟠 코리아세븐 엑셀 파일 업로드 (내부에 주문서 시트와 마스터 시트 포함)", type=['xlsx'], key='k1')
    if k7_file:
        try:
            xls = pd.ExcelFile(k7_file)
            sheets = xls.sheet_names
            
            s_data = get_sheet_name(sheets, ['order', 'data', 'raw', '210311', '주문'])
            s_master = get_sheet_name(sheets, ['마스터', 'master', '제품', '점포'])
            
            if not s_data or not s_master:
                st.error(f"⚠️ 엑셀 파일 안에서 필수 시트를 찾지 못했습니다. (현재 엑셀에 있는 시트: {sheets})")
            else:
                with st.spinner("엑셀 안의 시트들을 자동으로 참조하고 있습니다..."):
                    df_raw_k7 = pd.read_excel(xls, sheet_name=s_data, header=None)
                    df_master = pd.read_excel(xls, sheet_name=s_master)
                    
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

                st.success(f"✨ 변환 완료! (참조한 시트: 원본[{s_data}], 마스터[{s_master}])")
                st.download_button("📥 통합 수주업로드 다운로드 (코리아세븐)", data=convert_to_excel(df_final), file_name=f"수주업로드_{order_date_str}_코리아세븐.xlsx")
        except Exception as e:
            st.error(f"오류 발생: {e}")
