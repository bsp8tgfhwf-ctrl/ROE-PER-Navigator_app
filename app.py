import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
import time
import requests

# -----------------------------
# 関数①：為替レート取得（USD→JPY）
# -----------------------------
def get_usd_to_jpy():
    url = "https://api.exchangerate.host/latest?base=USD&symbols=JPY"
    try:
        response = requests.get(url)
        data = response.json()
        return data["rates"]["JPY"]
    except:
        return 152.80  # fallback

# -----------------------------
# 関数②：Yahoo FinanceからROE・PER取得
# -----------------------------
def get_roe_per_yahoo(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    roe = info.get("returnOnEquity")
    per = info.get("trailingPE")
    if roe is not None:
        roe = roe * 100
    return roe, per

# -----------------------------
# 関数③：スコアリング
# -----------------------------
def calculate_scores(roe_dict, per_dict, roe_weight=0.6):
    per_weight = 1.0 - roe_weight
    df = pd.DataFrame({
        "Ticker": list(roe_dict.keys()),
        "ROE": list(roe_dict.values()),
        "PER": list(per_dict.values())
    })
    scaler = MinMaxScaler()
    df[["ROE_norm", "PER_norm"]] = scaler.fit_transform(df[["ROE", "PER"]])
    df["Score"] = df["ROE_norm"] * roe_weight - df["PER_norm"] * per_weight
    df["Weight"] = df["Score"] / df["Score"].sum()
    df = df.dropna(subset=["Score", "Weight"])
    return df

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="初期購入モデル", layout="wide")
st.title("📈 初期購入モデル：生成AI＋半導体株（最大5銘柄）")

initial_yen = st.number_input("初期投資額（円）", value=300000)
roe_weight = st.slider("ROEの重み", 0.0, 1.0, 0.6)

usd_to_jpy = get_usd_to_jpy()
st.write(f"📈 現在の為替レート（USD→JPY）: {usd_to_jpy:.2f} 円")
initial_usd = initial_yen / usd_to_jpy

# -----------------------------
# 銘柄リストと事業内容
# -----------------------------
tickers_info = {
    "NVDA": "GPU・AI半導体の設計・開発",
    "AMD": "CPU・GPUの設計とデータセンター向け製品",
    "AVGO": "通信・データセンター向け半導体",
    "ASML": "EUV露光装置の世界最大手",
    "SMCI": "AIサーバー・データセンター向けハードウェア",
    "INTC": "CPU・半導体製造（IDM）",
    "QCOM": "スマホ向けSoC・5Gチップ",
    "TXN": "アナログ半導体・産業用IC",
    "MU": "メモリ（DRAM/NAND）製造",
    "MRVL": "データセンター・ストレージ向け半導体",
    "TSM": "世界最大の半導体受託製造（ファウンドリ）",
    "AMAT": "半導体製造装置（成膜・エッチング）",
    "LRCX": "半導体製造装置（洗浄・エッチング）",
    "KLAC": "半導体検査装置",
    "NXPI": "車載・IoT向け半導体",
    "ADI": "アナログ・ミックスドシグナルIC",
    "ON": "パワー半導体・車載向けIC",
    "GFS": "先端ファウンドリ（米国拠点）",
    "AEHR": "シリコンカーバイド向けテスト装置",
    "UCTT": "半導体製造装置の部材・組立"
}

tickers = list(tickers_info.keys())

# -----------------------------
# データ取得（1秒待機でレート制限回避）
# -----------------------------
roe_data = {}
per_data = {}
prices = {}
progress_bar = st.progress(0)

for i, ticker in enumerate(tickers):
    stock = yf.Ticker(ticker)
    time.sleep(1)
    try:
        prices[ticker] = stock.history(period="1d")["Close"].iloc[-1]
    except:
        prices[ticker] = None
    roe, per = get_roe_per_yahoo(ticker)
    roe_data[ticker] = roe if roe is not None else 0
    per_data[ticker] = per if per is not None else 100
    progress_bar.progress((i + 1) / len(tickers))

# -----------------------------
# スコア計算と株数計算
# -----------------------------
df = calculate_scores(roe_data, per_data, roe_weight)
df["Price"] = df["Ticker"].map(prices)
df["Business"] = df["Ticker"].map(tickers_info)
df = df.dropna(subset=["Price"])

df_sorted = df.sort_values(by="Score", ascending=False).copy()

# -----------------------------
# 優先順位に基づく購入ロジック（予算内・最大5銘柄）
# -----------------------------
selected = []
remaining_usd = initial_usd

for _, row in df_sorted.iterrows():
    if len(selected) >= 5:
        break
    max_shares = int(remaining_usd // row["Price"])
    if max_shares >= 1:
        used_usd = max_shares * row["Price"]
        remaining_usd -= used_usd
        selected.append({
            "Ticker": row["Ticker"],
            "Business": row["Business"],
            "Price": row["Price"],
            "Shares": max_shares,
            "Used_USD": used_usd,
            "Used_JPY": used_usd * usd_to_jpy,
            "Score": row["Score"],
            "ROE": row["ROE"],
            "PER": row["PER"]
        })

df_top = pd.DataFrame(selected)

# -----------------------------
# 表示
# -----------------------------
st.subheader("📊 スコアランキング（全銘柄）")
st.dataframe(df_sorted[["Ticker", "Business", "ROE", "PER", "Score"]])

st.subheader("💰 初期購入対象（最大5銘柄）")
st.dataframe(df_top[["Ticker", "Business", "Shares", "Price", "Used_USD", "Used_JPY"]])
st.write(f"🧾 合計投資額（円）: {df_top['Used_JPY'].sum():,.0f} 円")

st.subheader("📥 初期購入結果の保存")
csv = df_top.to_csv(index=False).encode("utf-8")
st.download_button("📄 CSVでダウンロード", data=csv, file_name="initial_purchase_top5.csv", mime="text/csv")

st.subheader("📊 資金配分グラフ（円換算）")
labels = df_top["Ticker"]
sizes = df_top["Used_JPY"]
fig, ax = plt.subplots()
ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
ax.axis("equal")
st.pyplot(fig)
