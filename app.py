import streamlit as st
from groq import Groq
import whisper
import imageio_ffmpeg
import numpy as np
import tempfile
import os
import subprocess
import base64
from datetime import datetime
from fpdf import FPDF

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "LINESeedJP_A_TTF_Rg.ttf")
FONT_BOLD_PATH = os.path.join(BASE_DIR, "LINESeedJP_A_TTF_Bd.ttf")

def load_audio_with_ffmpeg(file_path, sr=16000):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-i", file_path, "-ar", str(sr), "-ac", "1", "-f", "s16le", "-loglevel", "quiet", "-"]
    out = subprocess.run(cmd, capture_output=True)
    audio = np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("small")

def generate_pdf(summary_text, title, date_str):
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.add_font("JP", "", FONT_PATH)
    pdf.add_font("JP", "B", FONT_BOLD_PATH)
    W = pdf.w - pdf.l_margin - pdf.r_margin

    # タイトル
    pdf.set_font("JP", "B", 18)
    pdf.cell(W, 14, "議事録", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("JP", "", 11)
    pdf.cell(W, 8, f"会議名：{title}　　日付：{date_str}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    for line in summary_text.split("\n"):
        raw = line.strip()
        if not raw:
            pdf.ln(2)
            continue
        if raw.startswith("[") and raw.endswith("]"):
            heading = raw[1:-1]
            pdf.ln(3)
            pdf.set_font("JP", "B", 12)
            pdf.multi_cell(W, 8, heading, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("JP", "", 10)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(2)
        else:
            pdf.set_font("JP", "", 10)
            while len(raw) > 0:
                pdf.multi_cell(W, 7, raw, new_x="LMARGIN", new_y="NEXT")
                break

    return bytes(pdf.output())

def show_pdf(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        st.image(img_bytes, use_container_width=True)


st.set_page_config(page_title="MeetLog", page_icon="🎙️", layout="centered")

st.markdown("""
<style>
header {visibility: hidden;}
[data-testid="stToolbar"] {display: none !important;}
.stAppToolbar {display: none !important;}
</style>
""", unsafe_allow_html=True)

# パスワード認証
try:
    correct_password = st.secrets["APP_PASSWORD"]
    api_key = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error("設定が不完全です。管理者にお問い合わせください。")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Raleway:ital,wght@1,800&display=swap" rel="stylesheet">
    <h1 style="font-family:'Raleway',sans-serif;font-style:italic;font-weight:800;font-size:3rem;letter-spacing:2px;margin-bottom:0;">🎙️ MeetLog</h1>
    <p style="color:gray;margin-top:0;">AI議事録 自動生成</p>
    """, unsafe_allow_html=True)
    st.markdown("---")
    password_input = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン", use_container_width=True):
        if password_input == correct_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Raleway:ital,wght@1,800&display=swap" rel="stylesheet">
<h1 style="font-family:'Raleway',sans-serif;font-style:italic;font-weight:800;font-size:3rem;letter-spacing:2px;margin-bottom:0;">🎙️ MeetLog</h1>
<p style="color:gray;margin-top:0;">AI議事録 自動生成</p>
""", unsafe_allow_html=True)
st.success("🔒 音声データはこのPCの中だけで処理されます。外部に送信されません。")

with st.sidebar:
    st.header("📌 使い方")
    st.markdown("1. 会議名・日付・固有名詞を入力")
    st.markdown("2. 音声ファイルをアップロード")
    st.markdown("3. 議事録を作成ボタンを押す")
    st.markdown("4. 画面で確認 → PDFでダウンロード")
    st.markdown("---")
    st.markdown("**対応形式**")
    st.markdown("MP3 / MP4 / WAV / M4A / MOV / FLAC")
    st.markdown("---")
    st.markdown("**🔒 セキュリティ**")
    st.markdown("音声：PC内で処理（外部送信なし）")
    st.markdown("テキスト：要約のみ暗号化通信")
    st.markdown("---")
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Raleway:ital,wght@1,800&display=swap" rel="stylesheet">
    <p style="font-family:'Raleway',sans-serif;font-style:italic;font-weight:800;font-size:1.2rem;letter-spacing:1px;color:#888;">MeetLog</p>
    """, unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])
with col1:
    meeting_title = st.text_input("会議名（任意）", placeholder="例：週次定例会議、営業報告")
with col2:
    meeting_date = st.date_input("会議日", value=datetime.today())

# 固有名詞入力（商品名・人名の誤認識防止）
known_terms = st.text_input(
    "固有名詞（商品名・人名など）",
    placeholder="例：商品名、ヤマダタロウ",
    help="会議に登場する商品名や人名をカンマ区切りで入力すると認識精度が上がります"
)

audio_file = st.file_uploader(
    "音声ファイルをアップロード",
    type=["mp3", "mp4", "wav", "m4a", "flac", "ogg", "mov"],
)

if audio_file:
    st.audio(audio_file)
    st.caption(f"ファイルサイズ: {audio_file.size / (1024*1024):.1f} MB")

st.markdown("---")

if "result_text" not in st.session_state:
    st.session_state.result_text = None
if "summary_text" not in st.session_state:
    st.session_state.summary_text = None
if "filename_base" not in st.session_state:
    st.session_state.filename_base = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if st.button("🚀 議事録を作成する", type="primary", use_container_width=True):
    if not audio_file:
        st.error("音声ファイルをアップロードしてください")
    else:
        try:
            title_text = meeting_title if meeting_title else "会議"
            date_text = meeting_date.strftime("%Y年%m月%d日")
            terms_note = f"\n【この会議に登場する固有名詞】{known_terms}\nこれらの固有名詞は必ず正確に表記してください。" if known_terms else ""

            ext = audio_file.name.split(".")[-1].lower()
            suffix = ".mp4" if ext == "mov" else f".{ext}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_file.read())
                tmp_path = tmp.name

            with st.spinner("🔒 音声をPC内で文字起こし中...（初回は少し時間がかかります）"):
                model = load_whisper_model()
                audio = load_audio_with_ffmpeg(tmp_path)
                result = model.transcribe(audio, language="ja")
                transcript_text = result["text"]
            os.unlink(tmp_path)

            client = Groq(api_key=api_key)

            with st.spinner("議事録を作成中..."):
                detail_res = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"""
あなたはプロの議事録作成者です。
以下は「{date_text}」の「{title_text}」の文字起こしです。
{terms_note}

【絶対ルール①】人名は苗字・名前ともに100%カタカナで表記。山田太郎→ヤマダタロウ、田中花子→タナカハナコ。漢字・ひらがなの人名は議事録のどこにも一切書かない。
【絶対ルール②】商品名・サービス名・固有名詞は文字起こしに出てきた通り正確に記載。勝手に変えない。
【絶対ルール③】担当者・商品名・期限は必ずTODOテーブルに記載する。
【絶対ルール④】ルール①を最優先。人名が出てくる全箇所（概要・決定事項・TODO・議論・どこでも）でカタカナを徹底する。

以下の形式で議事録を作成してください：

# 📋 議事録
**会議名：** {title_text}

**日付：** {date_text}

---

## 1. 会議の概要

## 2. 決定事項

## 3. TODO・アクションアイテム
| 担当者（カタカナ） | 商品名・内容 | 期限 |
|--------|------|------|

## 4. 重要な議論・ポイント

## 5. 次回会議

---
【文字起こし】
{transcript_text}
"""}],
                    temperature=0.2,
                )
                detail_text = detail_res.choices[0].message.content

            with st.spinner("PDF用サマリーを作成中..."):
                summary_res = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"""
以下の議事録をPDF印刷用に整理してください。

【出力フォーマットの絶対ルール】
- マークダウン記号（#・*・|・-）は一切使わない
- セクション名は [セクション名] の形式で書く
- 箇条書きは「・」で始める
- 表は使わない。「・担当者：XXX　内容：XXX　期限：XXX」の形式で書く
- 人名は全てカタカナのみ（漢字・ひらがな禁止）
- 商品名・固有名詞は正確にそのまま記載。絶対に省略・変更しない
- 行数制限なし。内容を一切省略しない。元の議事録に書かれていることは全て漏れなく記載する
- 該当する情報がない項目は「・該当なし」と記載する

以下の9項目を必ず全て出力すること：

[参加者]
・（出席者を全員列挙）

[会議の概要]
・（何について話し合ったか）

[数値・実績報告]
・（訪問件数・成約数・売上など具体的な数字）

[重要な議論・ポイント]
・（話し合いの要点・背景・経緯）

[決定事項]
・（会議で決まったこと）

[課題・問題点]
・（出た懸念・未解決の問題）

[保留・確認事項]
・（結論が出なかった事項・要確認項目）

[共有事項]
・（情報共有のみで決定事項にならなかったこと）

[TODO]
・担当者：XXX　内容：XXX　期限：XXX
（アクションアイテムを一つも省略せず全て記載）

[次回会議]
・（日時・場所・議題）

---
【元の議事録】
{detail_text}
"""}],
                    temperature=0.2,
                )
                summary_text = summary_res.choices[0].message.content

            st.session_state.result_text = detail_text
            st.session_state.summary_text = summary_text
            st.session_state.filename_base = f"議事録_{date_text}_{title_text}".replace(" ", "_")
            st.session_state.title_text = title_text
            st.session_state.date_text = date_text

        except Exception as e:
            err = str(e)
            if "rate_limit" in err.lower() or "quota" in err.lower():
                st.error("一時的な上限です。1〜2分待ってから再試行してください。")
            else:
                st.error(f"エラー: {err}")

# 結果表示
if st.session_state.result_text:
    st.success("議事録の作成が完了しました！")
    st.markdown("---")
    st.markdown(st.session_state.result_text)
    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            label="📄 テキストでダウンロード",
            data=st.session_state.result_text,
            file_name=f"{st.session_state.filename_base}.txt",
            mime="text/plain",
            use_container_width=True
        )
    with col_b:
        if st.button("📥 PDFを作成・表示する", use_container_width=True):
            try:
                pdf_bytes = generate_pdf(
                    st.session_state.summary_text,
                    st.session_state.title_text,
                    st.session_state.date_text
                )
                st.session_state.pdf_bytes = pdf_bytes
            except Exception as e:
                st.error(f"PDFエラー: {e}")

if "pdf_bytes" in st.session_state and st.session_state.pdf_bytes:
    st.markdown("---")
    st.subheader("📄 PDF プレビュー")
    show_pdf(st.session_state.pdf_bytes)
    st.download_button(
        label="⬇️ PDFをダウンロード",
        data=st.session_state.pdf_bytes,
        file_name=f"{st.session_state.filename_base}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("✏️ 手直しする")
    st.caption("名前・商品名など間違いがあればここで修正してください。修正後に「PDFを更新する」を押してください。")

    edited_text = st.text_area(
        "内容を編集",
        value=st.session_state.summary_text,
        height=400,
        label_visibility="collapsed"
    )

    col_edit1, col_edit2 = st.columns(2)
    with col_edit1:
        if st.button("🔄 PDFを更新する", type="primary", use_container_width=True):
            try:
                new_pdf = generate_pdf(
                    edited_text,
                    st.session_state.title_text,
                    st.session_state.date_text
                )
                st.session_state.pdf_bytes = new_pdf
                st.session_state.summary_text = edited_text
                st.success("PDFを更新しました！")
                st.rerun()
            except Exception as e:
                st.error(f"PDFエラー: {e}")


st.markdown("---")
st.caption("Powered by Whisper（ローカル処理）+ Groq AI | AI議事録メーカー")
