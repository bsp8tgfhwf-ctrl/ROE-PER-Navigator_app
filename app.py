import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
import time
import requests

# 為替レート取得
def get_usd_to_jpy():
    url = "https://api.exchangerate.host/latest?base=USD&symbols=JPY"
    try:
        response = requests.get(url)
        data = response.json()
        return data["rates"]["JPY"]
    except:
        return 152.80

# スコア計算
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

# 銘柄分割
def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

# Streamlit UI
st.set_page_config(page_title="初期購入モデル（CSV対応）", layout="wide")
st.title("📈 初期購入モデル：生成AI＋半導体株（CSV形式で保存）")

initial_yen = st.number_input("初期投資額（円）", value=300000)
roe_weight = st.slider("ROEの重み", 0.0, 1.0, 0.6)

usd_to_jpy = get_usd_to_jpy()
st.write(f"📈 現在の為替レート（USD→JPY）: {usd_to_jpy:.2f} 円")
initial_usd = initial_yen / usd_to_jpy

# 銘柄情報
tickers_info = {
    "NVDA": "GPU・AI半導体の設計・開発", "AMD": "CPU・GPUの設計とデータセンター向け製品",
    "AVGO": "通信・データセンター向け半導体", "ASML": "EUV露光装置の世界最大手",
    "SMCI": "AIサーバー・データセンター向けハードウェア", "INTC": "CPU・半導体製造（IDM）",
    "QCOM": "スマホ向けSoC・5Gチップ", "TXN": "アナログ半導体・産業用IC",
    "MU": "メモリ（DRAM/NAND）製造", "MRVL": "データセンター・ストレージ向け半導体",
    "TSM": "世界最大の半導体受託製造（ファウンドリ）", "AMAT": "半導体製造装置（成膜・エッチング）",
    "LRCX": "半導体製造装置（洗浄・エッチング）", "KLAC": "半導体検査装置",
    "NXPI": "車載・IoT向け半導体", "ADI": "アナログ・ミックスドシグナルIC",
    "ON": "パワー半導体・車載向けIC", "GFS": "先端ファウンドリ（米国拠点）",
    "AEHR": "シリコンカーバイド向けテスト装置", "UCTT": "半導体製造装置の部材・組立"
}
tickers = list(tickers_info.keys())

# データ取得（分割）
roe_data = {}
per_data = {}
prices = {}
progress_bar = st.progress(0)
chunk_size = 5
total_chunks = len(list(chunk_list(tickers, chunk_size)))
chunk_index = 0

for group in chunk_list(tickers, chunk_size):
    for ticker in group:
        stock = yf.Ticker(ticker)
        try:
            prices[ticker] = stock.history(period="1d")["Close"].iloc[-1]
        except:
            prices[ticker] = None
        try:
            info = stock.info
            roe = info.get("returnOnEquity")
            per = info.get("trailingPE")
            roe_data[ticker] = roe * 100 if roe else 0
            per_data[ticker] = per if per else 100
        except:
            roe_data[ticker] = 0
            per_data[ticker] = 100
    chunk_index += 1
    progress_bar.progress(chunk_index / total_chunks)
    time.sleep(10)

# スコア計算
df = calculate_scores(roe_data, per_data, roe_weight)
df["Price"] = df["Ticker"].map(prices)
df["Business"] = df["Ticker"].map(tickers_info)
df = df.dropna(subset=["Price"])
df_sorted = df.sort_values(by="Score", ascending=False).copy()

# 必ず5銘柄購入
df_top5 = df_sorted.head(5).copy()
allocated_usd = initial_usd / 5
df_top5["Shares"] = (allocated_usd / df_top5["Price"]).astype(int)
df_top5["Used_USD"] = df_top5["Shares"] * df_top5["Price"]
df_top5["Used_JPY"] = df_top5["Used_USD"] * usd_to_jpy
total_invested_yen = df_top5["Used_JPY"].sum()

# 選定理由生成
df_top5["Reason"] = df_top5.apply(lambda row: f"{row['Ticker']}は{row['Business']}を手がけており、ROE {row['ROE']:.1f}%、PER {row['PER']:.1f}倍と財務指標も優秀。スコア上位に位置するため、初期購入対象に選定しました。", axis=1)

# 表示
st.subheader("📊 スコアランキング（全銘柄）")
st.dataframe(df_sorted[["Ticker", "Business", "ROE", "PER", "Score"]])

st.subheader("💰 初期購入対象（必ず5銘柄）")
st.dataframe(df_top5[["Ticker", "Business", "Shares", "Price", "Used_USD", "Used_JPY", "Reason"]])
st.write(f"🧾 合計投資額（円）: {total_invested_yen:,.0f} 円")
if total_invested_yen > initial_yen:
    st.warning(f"⚠️ 合計投資額が予算を {total_invested_yen - initial_yen:,.0f} 円オーバーしています")

# CSV保存（月次モデル互換）
st.subheader("📥 月次モデル用CSV保存")
df_top5["PurchasePriceUSD"] = df_top5["Price"]
df_top5["PurchaseDate"] = pd.Timestamp.today().strftime("%Y-%m-%d")
df_top5["ROE"] = df_top5["Ticker"].map(roe_data)
df_top5["PER"] = df_top5["Ticker"].map(per_data)
df_top5["Score"] = df_top5["Ticker"].map(df.set_index("Ticker")["Score"])
df_top5["PurchaseRate"] = usd_to_jpy
portfolio_df = df_top5[["Ticker", "Shares", "PurchasePriceUSD", "PurchaseDate", "ROE", "PER", "Score", "PurchaseRate"]]
csv = portfolio_df.to_csv(index=False).encode("utf-8")
st.download_button("📄 portfolio.csv をダウンロード", data=csv, file_name="portfolio.csv", mime="text/csv")

# グラフ
st.subheader("📊 資金配分グラフ（円換算）")
labels = df_top5["Ticker"]
sizes = df_top5["Used_JPY"]
fig, ax = plt.subplots()
ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
ax.axis("equal")
st.pyplot(fig)
