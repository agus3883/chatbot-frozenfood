import os
import streamlit as st
import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

st.title("ChatBot-Ku")

sales_ai_prompt = """
Anda adalah Agen Penjualan dari Rumah Bunda Frozen Food Bogor yang membantu, supel, kasual, ramah, proaktif dan simpel untuk katalog Frozen Food pengguna. Lokasi toko di kota Bogor, kontak WA 081234567890. Rekening transfer BCA 123-456-7890 a.n. Rumah Bunda Frozen Food.

Prinsip interaksi:
1) Pada sapaan awal atau saat informasi belum cukup, SAPA dulu dan ajukan MAKS 2 pertanyaan kunci
   (contoh: kisaran anggaran, kategori/jenis produk, dan use-case).
   Jangan langsung menampilkan daftar produk pada langkah ini.
2) Setelah ada sinyal kebutuhan (budget/kategori/use-case), rekomendasikan 3–5 produk terbaik dari katalog,
   jelaskan alasan singkat & trade-off. Harga gunakan format IDR (contoh: Rp 1.250.000).
3) Selalu gunakan data dari katalog (Excel) untuk nama, kategori, harga, stok, deskripsi, merek/brand, dan kemasan/pack.
   Jangan mengada-ada SKU.
4) Tawarkan upsell/cross-sell bila relevan. Nada profesional, ramah, dan solutif.
5) Jangan lupa tanyakan alamat pengiriman dan metode pembayaran di akhir percakapan.
"""

def get_api_key_input():
    st.write("Masukkan Google API Key")
    if "GOOGLE_API_KEY" not in st.session_state:
        st.session_state["GOOGLE_API_KEY"] = ""
    col1, col2 = st.columns((80, 20))
    with col1:
        api_key = st.text_input("", label_visibility="collapsed", type="password")
    with col2:
        is_submit_pressed = st.button("Submit")
        if is_submit_pressed:
            st.session_state["GOOGLE_API_KEY"] = api_key
    os.environ["GOOGLE_API_KEY"] = st.session_state["GOOGLE_API_KEY"]

def load_llm():
    if "llm" not in st.session_state:
        st.session_state["llm"] = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    return st.session_state["llm"]

def get_chat_history():
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    return st.session_state["chat_history"]

def display_chat_message(message):
    if isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    else:
        role = "assistant"
    with st.chat_message(role):
        st.markdown(message.content)

st.sidebar.subheader("📦 Unggah Katalog Frozen Food (Excel)")
uploaded = st.sidebar.file_uploader("File .xlsx / .xls", type=["xlsx", "xls"])

def _infer_col(cols, candidates):
    cols_l = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in cols_l:
            return cols_l[cand.lower()]
    for c in cols:
        cl = c.lower()
        if any(cand.lower() in cl for cand in candidates):
            return c
    return None

def _rupiah(x):
    try:
        v = float(str(x).replace(".", "").replace(",", "."))
    except Exception:
        try:
            v = float(x)
        except Exception:
            return "-"
    return f"Rp {int(v):,}".replace(",", ".")

def _make_catalog_context(df, limit=60):
    
    name_col = _infer_col(df.columns, ["name", "nama", "product_name", "title"])
    price_col = _infer_col(df.columns, ["price", "harga", "unit_price"])
    cat_col   = _infer_col(df.columns, ["category", "kategori", "type", "jenis"])
    stock_col = _infer_col(df.columns, ["stock", "stok", "qty", "quantity"])
    desc_col  = _infer_col(df.columns, ["description", "deskripsi", "detail", "spec"])
    brand_col = _infer_col(df.columns, ["brand", "merek", "merk", "brand_name"])         
    pack_col  = _infer_col(df.columns, ["kemasan", "packaging", "pack", "ukuran",       
                                        "size", "netto", "berat", "weight", "volume", "isi", "pack size"])

    if name_col is None or price_col is None:
        return "Katalog belum siap: kolom name/nama dan price/harga wajib ada."

    lines = []
    for _, r in df.head(limit).iterrows():
        nm = str(r.get(name_col, "")).strip()
        pr = _rupiah(r.get(price_col, ""))
        ct = str(r.get(cat_col, "")).strip() if cat_col else ""
        stx = str(r.get(stock_col, "")).strip() if stock_col else ""
        ds  = str(r.get(desc_col, "")).strip() if desc_col else ""
        br  = str(r.get(brand_col, "")).strip() if brand_col else ""     
        pk  = str(r.get(pack_col, "")).strip() if pack_col else ""       
        if len(ds) > 120:
            ds = ds[:120] + "…"

        parts = [f"Nama: {nm}", f"Harga: {pr}"]
        if br:  parts.append(f"Merek: {br}")         
        if pk:  parts.append(f"Kemasan: {pk}")       
        if ct:  parts.append(f"Kategori: {ct}")
        if stx: parts.append(f"Stok: {stx}")
        if ds:  parts.append(f"Deskripsi: {ds}")
        lines.append("- " + " | ".join(parts))

    header_schema = "Kolom tersedia: name, price, category, stock, description" \
                    + (", brand" if brand_col else "") \
                    + (", packaging" if pack_col else "") + "."
    return header_schema + "\nKatalog Frozen Food (ringkas):\n" + "\n".join(lines)

get_api_key_input()
if not os.environ["GOOGLE_API_KEY"]:
    st.stop()

llm = load_llm()
chat_history = get_chat_history()

catalog_context = None
if uploaded is not None:
    xls = pd.ExcelFile(uploaded)
    sheet_name = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]
    st.sidebar.success(f"Katalog dimuat dari sheet: {sheet_name}")
    with st.expander("🔎 Pratinjau Data (atas 20 baris)"):
        st.dataframe(df.head(20), use_container_width=True)
    catalog_context = _make_catalog_context(df, limit=60)
else:
    st.info("Unggah file Excel katalog frozen food dulu ya (minimal punya kolom Name/Nama dan Price/Harga).")

system_msgs = [SystemMessage(content=sales_ai_prompt.strip())]
if catalog_context:
    system_msgs.append(SystemMessage(content=catalog_context))

for chat in chat_history:
    display_chat_message(chat)

prompt = st.chat_input("Tanya produk frozen food…")
if prompt:
    chat_history.append(HumanMessage(content=prompt))
    display_chat_message(chat_history[-1])

    messages = system_msgs + chat_history
    response = llm.invoke(messages)

    chat_history.append(response)
    display_chat_message(chat_history[-1])