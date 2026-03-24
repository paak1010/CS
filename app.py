import streamlit as st
import pandas as pd
import datetime
import io
import os

st.set_page_config(page_title="완벽 자동화 수주업로드", layout="wide")
st.title("🚀 원클릭 수주업로드 자동화")
st.markdown("매번 귀찮게 마스터 엑셀을 올릴 필요 없습니다. **오늘 포털에서 다운받은 발주 원본(RAW) 파일만 던져 넣으세요!**")

# [복구완료] 두 번째 '서식' 시트의 17개 컬럼으로 완벽하게 맞춤
FINAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 'LOT', '특이사항1', 'Type', '특이사항2']
REAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금       액', '부  가   세', 'LOT', '특이사항', 'Type', '특이사항']

order_date = st.date_input("수주일자 지정", datetime.date.today())
order_date_str = order_date.strftime("%Y%m%d")

def find_file(keyword):
    for f in os.listdir('.'):
        if keyword in f and (f.endswith('.xlsx') or f.endswith('.csv')):
            return f
    return None

@st.cache_data
def load_brain():
    products, stores, missing = {}, {}, []
    
    bgf_file = find_file('BGF')
    gs_file = find_file('지에스')
    k7_file = find_file('코리아세븐')
    
    if not bgf_file: missing.append('BGF 서식 엑셀 (이름에 "BGF" 포함 요망)')
    if not gs_file: missing.append('GS 서식 엑셀 (이름에 "지에스" 포함 요망)')
    if not k7_file: missing.append('코리아세븐 서식 엑셀 (이름에 "코리아세븐" 포함 요망)')

    for f in [bgf_file, gs_file, k7_file]:
        if not f: continue
        xls = pd.ExcelFile(f)
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            if '바코드' in df.columns and '제품코드' in df.columns:
                for _, r in df.dropna(subset=['바코드']).iterrows():
                    barcode = str(r['바코드']).replace('.0','').strip()
                    products[barcode] = {
                        'mecode': str(r['제품코드']).strip(),
                        'name': str(r['상품명']).strip() if '상품명' in df.columns else ''
                    }
            if '점포명' in df.columns and '점포코드' in df.columns:
                for _, r in df.dropna(subset=['점포명']).iterrows():
                    store = str(r['점포명']).strip()
                    stores[store] = str(r['점포코드']).strip()
                    
    return products, stores, missing

def detect_and_load(file):
    is_csv = file.name.endswith('.csv')
    df_test = pd.read_csv(file, header=None, nrows=5) if is_csv else pd.read_excel(file, header=None, nrows=5)
    val00 = str(df_test.iloc[0, 0]).strip()
    
    file.seek(0)
    if val00 == '주문서':
        return 'GS', (pd.read_csv(file, header=1) if is_csv else pd.read_excel(file, header=1))
    elif val00 in ['주문서 리스트', '문서명', 'ORDERS']:
        return 'K7', (pd.read_csv(file, header=None) if is_csv else pd.read_excel(file, header=None))
    else:
        header_idx = 1 if '번호' in val00 and '센터' not in str(df_test.iloc[0, 1]) else 0
        return 'BGF', (pd.read_csv(file, header=header_idx) if is_csv else pd.read_excel(file, header=header_idx))

# ====== 메인 앱 실행 ======
products_dict, stores_dict, missing_files = load_brain()

if missing_files:
    st.error("❌ GitHub 서버에 기준표(마스터 엑셀)가 없습니다! 아래 파일을 GitHub 저장소에 꼭 업로드해주세요.")
    for m in missing_files: st.write(f"- {m}")

st.write("---")
raw_files = st.file_uploader("📥 오늘 처리할 RAW 파일(DATA, ordview, ORDERS 등)들을 끌어다 놓으세요.", accept_multiple_files=True)

if raw_files and not missing_files:
    for file in raw_files:
        try:
            with st.spinner(f"[{file.name}] 변환 중..."):
                platform, df_raw = detect_and_load(file)
                df_final = pd.DataFrame(columns=FINAL_COLUMNS)
                
                if platform == 'BGF':
                    df_raw['납품일자'] = df_raw['납품예정일자'].astype(str).str[:8]
                    df_raw['상품 코드'] = df_raw['상품 코드'].astype(str).str.strip()
                    df_raw['센터명'] = df_raw['센터명'].astype(str).str.strip()
                    
                    df_final['납품일자'] = df_raw['납품일자']
                    df_final['발주처'] = df_raw['센터명']
                    df_final['배송지'] = df_raw['센터명']
                    df_final['발주처코드'] = df_raw['센터명'].apply(lambda x: stores_dict.get(x, ''))
                    df_final['배송코드'] = df_final['발주처코드']
                    df_final['상품코드'] = df_raw['상품 코드'].apply(lambda x: products_dict.get(x, {}).get('mecode', ''))
                    df_final['상품명'] = df_raw['상품 코드'].apply(lambda x: products_dict.get(x, {}).get('name', ''))
                    mask = df_final['상품명'] == ''
                    df_final.loc[mask, '상품명'] = df_raw.loc[mask, '상품명'] if '상품명' in df_raw.columns else ''
                    
                    df_final['UNIT수량'] = pd.to_numeric(df_raw['총수량'], errors='coerce').fillna(0).astype(int)
                    df_final['UNIT단가'] = pd.to_numeric(df_raw['납품원가'], errors='coerce').fillna(0).astype(int)
                    df_final['금       액'] = df_final['UNIT수량'] * df_final['UNIT단가']
                    
                elif platform == 'GS':
                    df_raw['납품일자'] = df_raw['납품일자'].astype(str).str.replace('-', '') 
                    df_raw['배송처'] = df_raw['배송처'].astype(str).str.strip()
                    df_raw['상품코드'] = df_raw['상품코드'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

                    df_final['납품일자'] = df_raw['납품일자']
                    df_final['발주처'] = df_raw['배송처']
                    df_final['배송지'] = df_raw['배송처']
                    df_final['발주처코드'] = df_raw['배송처'].apply(lambda x: stores_dict.get(x, ''))
                    df_final['배송코드'] = df_final['발주처코드']
                    df_final['상품코드'] = df_raw['상품코드'].apply(lambda x: products_dict.get(x, {}).get('mecode', ''))
                    df_final['상품명'] = df_raw['상품코드'].apply(lambda x: products_dict.get(x, {}).get('name', ''))
                    mask = df_final['상품명'] == ''
                    df_final.loc[mask, '상품명'] = df_raw.loc[mask, '상품명_x'] if '상품명_x' in df_raw.columns else (df_raw.loc[mask, '상품명'] if '상품명' in df_raw.columns else '')

                    df_final['UNIT단가'] = pd.to_numeric(df_raw['발주단가'], errors='coerce').fillna(0).astype(int)
                    df_final['금       액'] = pd.to_numeric(df_raw['발주금액'], errors='coerce').fillna(0).astype(int)
                    df_final['UNIT수량'] = (df_final['금       액'] / df_final['UNIT단가'].replace(0, 1)).astype(int)

                elif platform == 'K7':
                    records, current_date = [], ""
                    for idx, row in df_raw.iterrows():
                        col0 = str(row[0]).strip()
                        if col0 == 'ORDERS':
                            current_date = str(row[7]).strip().replace('-', '')
                        elif str(row[1]).strip().startswith('880'):
                            barcode = str(row[1]).strip().replace('.0', '')
                            store = str(row[3]).strip()
                            price = pd.to_numeric(str(row[7]).replace(',', ''), errors='coerce')
                            total = pd.to_numeric(str(row[8]).replace(',', ''), errors='coerce')
                            qty = int(total / price) if price and price > 0 else 0
                            records.append({'납품일자': current_date, '바코드': barcode, '점포명': store, 'UNIT단가': price, '금       액': total, 'UNIT수량': qty})
                    
                    df_k7 = pd.DataFrame(records)
                    if not df_k7.empty:
                        df_final['납품일자'] = df_k7['납품일자']
                        df_final['발주처코드'] = 81032000 
                        df_final['발주처'] = "(주)코리아세븐"
                        df_final['배송지'] = df_k7['점포명']
                        df_final['배송코드'] = df_k7['점포명'].apply(lambda x: stores_dict.get(x, ''))
                        df_final['상품코드'] = df_k7['바코드'].apply(lambda x: products_dict.get(x, {}).get('mecode', ''))
                        df_final['상품명'] = df_k7['바코드'].apply(lambda x: products_dict.get(x, {}).get('name', ''))
                        df_final['UNIT수량'] = df_k7['UNIT수량']
                        df_final['UNIT단가'] = df_k7['UNIT단가']
                        df_final['금       액'] = df_k7['금       액']

                # 공통 포맷 마감
                df_final['출고구분'] = 0
                df_final['수주일자'] = order_date_str
                df_final['부  가   세'] = (pd.to_numeric(df_final['금       액'], errors='coerce').fillna(0) * 0.1).astype(int)
                df_final['LOT'] = ''
                df_final['특이사항1'] = ''
                df_final['Type'] = ''
                df_final['특이사항2'] = ''
                df_final.fillna('', inplace=True)

                # 화면 UI 출력 (17열 폼 뷰)
                st.success(f"✅ {platform} 데이터 변환 완료!")
                st.dataframe(df_final, use_container_width=True)
                
                # 엑셀 저장 시에는 특이사항 중복 허용하여 실제 서식과 100% 동일하게
                df_excel = df_final.copy()
                df_excel.columns = REAL_COLUMNS
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_excel.to_excel(writer, index=False, sheet_name='서식')
                
                st.download_button(
                    label=f"📥 수주업로드 다운로드 ({platform})",
                    data=output.getvalue(),
                    file_name=f"수주업로드_{order_date_str}_{platform}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{file.name}"
                )
        except Exception as e:
            st.error(f"❌ {file.name} 처리 중 오류가 발생했습니다: {e}")
