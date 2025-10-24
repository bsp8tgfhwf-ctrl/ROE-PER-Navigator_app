# app.py

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

# -----------------------------
# 関数①：MarketScreenerからROE・PER取得
# -----------------------------
def get_roe_per_marketscreener(ticker_name, ticker_id):
    url = f"https://www.marketscreener.com/quote/stock/{ticker_name}-{ticker_id}/financials/"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    roe = None
    per = None

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].text.strip()
            value = cells[1].text.strip()
            if "Return on equity" in label:
                roe = value.replace("%", "").strip()
            elif "P/E ratio" in label:
                per = value.strip()

    try:
        roe = float(roe)
        per = float(per)
    except:
        roe, per = None, None

    return roe, per

# -----------------------------
# 関数②：スコアリング
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
    return df

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="初期購入モデル", layout="wide")
st.title("📈 初期購入モデル：生成AI＋半導体株")

# ユーザー入力
initial_yen = st.number_input("初期投資額（円）", value=300000)
roe_weight = st.slider("ROEの重み", 0.0, 1.0, 0.6)
usd_to_jpy = 152.80
initial_usd = initial_yen / usd_to_jpy

# 銘柄情報
tickers_info = {
    "NVDA": ("NVIDIA-CORPORATION", "57355629"),
    "AMD": ("ADVANCED-MICRO-DEVICES", "19475876"),
    "AVGO": ("BROADCOM-INC", "36232673"),
    "ASML": ("ASML-HOLDING-N-V", "16951911"),
    "SMCI": ("SUPER-MICRO-COMPUTER-INC", "27560194")
}

prices = {
    "NVDA": 185.30,
    "AMD": 250.15,
    "AVGO": 356.66,
    "ASML": 940.00,
    "SMCI": 48.66
}

# ROE・PER取得（None対策付き）
roe_data = {}
per_data = {}
for ticker, (name, id_) in tickers_info.items():
    roe, per = get_roe_per_marketscreener(name, id_)
    roe_data[ticker] = roe if roe is not None else 0
    per_data[ticker] = per if per is not None else 100

# スコア計算
df = calculate_scores(roe_data, per_data, roe_weight)
df["Price"] = df["Ticker"].map(prices)
df["Allocated_USD"] = df["Weight"] * initial_usd

# NaN除外して株数計算
df_valid = df.dropna(subset=["Allocated_USD", "Price"]).copy()
df_valid["Shares"] = (df_valid["Allocated_USD"] / df_valid["Price"]).astype(int)
df_valid["Used_USD"] = df_valid["Shares"] * df_valid["Price"]
df_valid["Used_JPY"] = df_valid["Used_USD"] * usd_to_jpy
df_valid["Rank"] = df_valid["Score"].rank(ascending=False).astype(int)

# -----------------------------
# 表示①：スコアランキング（購入対象を強調）
# -----------------------------
def highlight_purchases(row):
    return ['background-color: #dff0d8' if row['Shares'] >= 1 else '' for _ in row]

styled_df = df_valid.sort_values(by="Score", ascending=False).reset_index(drop=True).style.apply(highlight_purchases, axis=1)
st.subheader("📊 スコアランキング（購入対象を強調）")
st.dataframe(styled_df)

# -----------------------------
# 表示②：購入株数と円換算
# -----------------------------
df_purchased = df_valid[df_valid["Shares"] >= 1]
total_invested_yen = df_purchased["Used_JPY"].sum()

st.subheader("💰 初期購入対象銘柄（株数と円換算）")
st.dataframe(df_purchased[["Ticker", "Shares", "Price", "Used_USD", "Used_JPY"]])
st.write(f"🧾 合計投資額（円）: {total_invested_yen:,.0f} 円")

# -----------------------------
# 表示③：CSV保存
# -----------------------------
st.subheader("📥 初期購入結果の保存")
csv = df_purchased.to_csv(index=False).encode("utf-8")
st.download_button("📄 CSVでダウンロード", data=csv, file_name="initial_purchase.csv", mime="text/csv")

# -----------------------------
# 表示④：グラフ表示
# -----------------------------
st.subheader("📊 資金配分グラフ（円換算）")
labels = df_purchased["Ticker"]
sizes = df_purchased["Used_JPY"]
fig, ax = plt.subplots()
ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
ax.axis("equal")
st.pyplot(fig)
