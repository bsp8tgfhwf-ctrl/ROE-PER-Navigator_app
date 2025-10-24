# app.py

import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

# -----------------------------
# 関数①：Yahoo FinanceからROE・PER取得
# -----------------------------
def get_roe_per_yahoo(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info

    roe = info.get("returnOnEquity")
    per = info.get("trailingPE")

    # ROEは小数（例：0.25）なので100倍して％に変換
    if roe is not None:
        roe = roe * 100

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
    df = df.dropna(subset=["Score", "Weight"])
    return df

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="初期購入モデル", layout="wide")
st.title("📈 初期購入モデル：生成AI＋半導体株")

initial_yen = st.number_input("初期投資額（円）", value=300000)
roe_weight = st.slider("ROEの重み", 0.0, 1.0, 0.6)
usd_to_jpy = 152.80
initial_usd = initial_yen / usd_to_jpy

# 銘柄情報（Yahoo Financeのティッカー）
tickers = ["NVDA", "AMD", "AVGO", "ASML", "SMCI"]

# 株価取得（yfinanceから）
prices = {}
roe_data = {}
per_data = {}

for ticker in tickers:
    stock = yf.Ticker(ticker)
    prices[ticker] = stock.info.get("currentPrice")
    roe, per = get_roe_per_yahoo(ticker)
    roe_data[ticker] = roe if roe is not None else 0
    per_data[ticker] = per if per is not None else 100

# 🧪 ステップ①：ROE・PER取得結果を表示
st.subheader("🧪 ステップ①：ROE・PER取得結果")
st.write("ROEデータ:", roe_data)
st.write("PERデータ:", per_data)

# スコア計算
df = calculate_scores(roe_data, per_data, roe_weight)
df["Price"] = df["Ticker"].map(prices)
df["Allocated_USD"] = df["Weight"] * initial_usd

# 🧪 ステップ②：スコア計算後のDataFrameを表示
st.subheader("🧪 ステップ②：スコア計算後のDataFrame")
st.write(df)

# 株数計算
df_valid = df.dropna(subset=["Allocated_USD", "Price"]).copy()
df_valid["Shares"] = (df_valid["Allocated_USD"] / df_valid["Price"]).astype(int)
df_valid["Used_USD"] = df_valid["Shares"] * df_valid["Price"]
df_valid["Used_JPY"] = df_valid["Used_USD"] * usd_to_jpy
df_valid["Rank"] = df_valid["Score"].rank(ascending=False).astype(int)

# 🧪 ステップ③：株数計算後のDataFrameを表示
st.subheader("🧪 ステップ③：株数計算後のDataFrame")
st.write(df_valid)

# 強調表示
def highlight_purchases(row):
    return ['background-color: #dff0d8' if row['Shares'] >= 1 else '' for _ in row]

styled_df = df_valid.sort_values(by="Score", ascending=False).reset_index(drop=True).style.apply(highlight_purchases, axis=1)
st.subheader("📊 スコアランキング（購入対象を強調）")
st.dataframe(styled_df)

# 購入対象表示
df_purchased = df_valid[df_valid["Shares"] >= 1]
total_invested_yen = df_purchased["Used_JPY"].sum()

st.subheader("💰 初期購入対象銘柄（株数と円換算）")
st.dataframe(df_purchased[["Ticker", "Shares", "Price", "Used_USD", "Used_JPY"]])
st.write(f"🧾 合計投資額（円）: {total_invested_yen:,.0f} 円")

# CSV保存
st.subheader("📥 初期購入結果の保存")
csv = df_purchased.to_csv(index=False).encode("utf-8")
st.download_button("📄 CSVでダウンロード", data=csv, file_name="initial_purchase.csv", mime="text/csv")

# グラフ表示
st.subheader("📊 資金配分グラフ（円換算）")
labels = df_purchased["Ticker"]
sizes = df_purchased["Used_JPY"]
fig, ax = plt.subplots()
ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
ax.axis("equal")
st.pyplot(fig)
