import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import io
import os
import re

# [필수] 1. 페이지 설정 (무조건 맨 위)
st.set_page_config(page_title="편의점 수주업로드 시스템", page_icon="🏪", layout="wide")

# 2. 상수 및 컬럼 양식 정의 (이게 정확해야 양식이 바뀝니다)
LOGO_URL = "https://tse2.mm.bing.net/th/id/OIP.Yoy5rHyBGX6zIO_Tf0Cg_AHaBW?rs=1&pid=ImgDetMain&o=7&rm=3"
FINAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금      액', '부  가   세', 'LOT', '특이사항1', 'Type', '특이사항2']
REAL_COLUMNS = ['출고구분', '수주일자', '납품일자', '발주처코드', '발주처', '배송코드', '배송지', '상품코드', '상품명', 'UNIT수량', 'UNIT단가', '금      액', '부  가   세', 'LOT', '특이사항', 'Type', '특이사항']

# 3. 사이드바 로고 및 안내
with st.sidebar:
    st.image(LOGO_URL, use_container_width=True)
    st.divider()
    st.subheader("⚙️ 작업 설정")
    st.info("1. 파일 업로드 시 자동 변환\n2. 하단 다운로드 버튼 클릭")
    st.caption("Developed by Jay")

# 4. 메인 타이틀
st.title("🏪 편의점 수주업로드 자동화 시스템")
st.divider()

# 5. 파일 업로드
raw_files = st.file_uploader("RAW 파일들을 업로드하세요.", accept_multiple_files=True)

if raw_files:
    combined_dfs = []
    
    for file in raw_files:
        # --- 여기에 본인의 detect_and_load 및 데이터 처리 로직이 들어갑니다 ---
        # (편의상 예시 데이터 프레임을 생성하는 구조로 설명드립니다)
        # 중요: 각 플랫폼(BGF, GS, K7)별로 추출한 df_final을 만든 후...
        
        # 임시 예시 (본인 로직에서 나온 결과라고 가정)
        df_temp = pd.DataFrame(columns=['상품코드', 'UNIT수량']) # 실제 데이터가 담긴 DF
        # ... 데이터 처리 로직 수행 ...
        
        combined_dfs.append(df_temp)

    if combined_dfs:
        # 모든 데이터 통합
        df_combined = pd.concat(combined_dfs, ignore_index=True)
        
        # [핵심] 양식 강제 맞춤 로직
        # 1. 없는 컬럼은 빈 값으로 생성
        for col in FINAL_COLUMNS:
            if col not in df_combined.columns:
                df_combined[col] = ""
        
        # 2. 정해진 순서대로 컬럼 재배치
        df_combined = df_combined[FINAL_COLUMNS]
        
        # 3. 다운로드용 파일 생성 시 컬럼명 변경 (REAL_COLUMNS 적용)
        df_excel = df_combined.copy()
        df_excel.columns = REAL_COLUMNS # 여기서 최종 엑셀 양식 이름으로 바뀜
        
        # 미리보기
        st.subheader("📊 변환 데이터 확인")
        st.dataframe(df_excel, use_container_width=True)
        
        # 엑셀 변환 (xlsxwriter 사용)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_excel.to_excel(writer, index=False, sheet_name='서식')
        
        # 다운로드 버튼
        st.download_button(
            label="📥 통합 양식 다운로드",
            data=output.getvalue(),
            file_name=f"통합_수주업로드_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
