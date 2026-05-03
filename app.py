import streamlit as st
import pdfplumber
import anthropic
import io
import os
from datetime import datetime

st.set_page_config(
    page_title="HPB サロンレポート分析",
    page_icon="💇",
    layout="wide"
)

st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 0.25rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .upload-section {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 2rem;
        border: 2px dashed #dee2e6;
        text-align: center;
    }
    .result-box {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e9ecef;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">💇 HPB サロンレポート 自動分析ツール</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ホットペッパービューティーのサロンレポートPDFをアップロードするだけで、AI が強み・課題・改善提案を自動生成します。</div>', unsafe_allow_html=True)

# Sidebar: API Key
with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.text_input(
        "Anthropic API キー",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="APIキーが環境変数 ANTHROPIC_API_KEY に設定されている場合は不要です"
    )
    st.markdown("---")
    st.markdown("**分析項目**")
    st.markdown("- 📊 KPIトレンド（予約数・売上・客単価）")
    st.markdown("- 🔍 エリア平均との比較")
    st.markdown("- 👥 顧客属性（年齢・性別・新規/リピート）")
    st.markdown("- 📈 CVR・ACR分析")
    st.markdown("- 💡 優先度付き改善提案")

def extract_pdf_text(file_bytes: bytes) -> tuple[str, int]:
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = len(pdf.pages)
        text_parts = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n\n".join(text_parts), pages

ANALYSIS_PROMPT = """あなたは美容サロン経営の専門コンサルタントです。
以下はHOT PEPPER Beauty（ホットペッパービューティー）のサロンレポートデータです。
このデータを分析して、サロンオーナーが「次に何をすべきか」が明確にわかるレポートを日本語で作成してください。

【レポートデータ】
{text}

【出力ルール】
- 数値を必ず引用しながら根拠を示す
- 抽象的なアドバイスは禁止。「何を・どうやって・いつまでに」を明記する
- エリア平均と比較できる項目は必ず比較する
- プランの変更がある場合はその影響を考慮する
- 口コミ・ブログ・スタイル数などのコンテンツ面も評価する

【出力フォーマット】

## 📋 基本情報
サロン名、掲載エリア、プラン、データ取得日を一覧で表示

## 📊 直近トレンドサマリー（6ヶ月）
主要KPI（NET予約数・売上・客単価・総PV数）の直近6ヶ月推移を表形式で示し、トレンドを一言評価する

## ✅ 好調な点（3〜5項目）
- 各項目に具体的な数値と「なぜ良いか」の理由を記載
- エリア平均や前月比を必ず添える

## ⚠️ 課題（3〜5項目）
- 各項目に具体的な数値と「なぜ問題か・放置するとどうなるか」を記載
- 緊急度（高・中・低）を明示

## 🚀 改善アクションプラン（優先度順）

### 🔴 今すぐやること（今月中）
具体的なアクション × 2〜3件

### 🟡 来月までにやること
具体的なアクション × 2〜3件

### 🟢 3ヶ月以内に取り組むこと
具体的なアクション × 1〜2件

## 💬 総評
このサロンの現状を3〜4行でまとめ、最も重要なメッセージを伝える
"""

# Main area
uploaded_file = st.file_uploader(
    "サロンレポートPDF をドラッグ＆ドロップ、またはクリックして選択",
    type="pdf",
    help="HOT PEPPER Beauty のサロンレポートPDFに対応しています"
)

if uploaded_file:
    file_bytes = uploaded_file.read()

    with st.spinner("PDFを読み込み中..."):
        try:
            text, num_pages = extract_pdf_text(file_bytes)
        except Exception as e:
            st.error(f"PDFの読み込みに失敗しました: {e}")
            st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("ページ数", f"{num_pages} ページ")
    col2.metric("抽出文字数", f"{len(text):,} 文字")
    col3.metric("ファイルサイズ", f"{len(file_bytes)/1024:.1f} KB")

    with st.expander("📄 抽出されたテキスト（確認用）", expanded=False):
        st.text_area("", text[:3000] + ("..." if len(text) > 3000 else ""), height=200)

    st.markdown("---")

    if st.button("🔍 AI分析を開始する", type="primary", use_container_width=True):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            st.error("APIキーを設定してください（サイドバー または 環境変数 ANTHROPIC_API_KEY）")
            st.stop()

        client = anthropic.Anthropic(api_key=key)
        prompt = ANALYSIS_PROMPT.format(text=text)

        st.markdown("## 🤖 AI 分析レポート")
        st.caption(f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")

        result_container = st.empty()
        full_response = ""

        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text_chunk in stream.text_stream:
                    full_response += text_chunk
                    result_container.markdown(full_response + "▌")

            result_container.markdown(full_response)

            st.markdown("---")
            st.download_button(
                label="📥 分析レポートをダウンロード（テキスト）",
                data=full_response,
                file_name=f"salon_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                mime="text/markdown",
                use_container_width=True
            )

        except anthropic.AuthenticationError:
            st.error("APIキーが無効です。正しいキーを入力してください。")
        except Exception as e:
            st.error(f"分析中にエラーが発生しました: {e}")

else:
    st.info("👆 上のエリアにPDFをアップロードしてください")
    st.markdown("""
    **対応レポート形式**
    - HOT PEPPER Beauty サロンレポート（月次）
    - 複数ページのPDFに対応

    **分析にかかる時間**
    - 約30〜60秒
    """)
