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

# UI構成
st.set_page_config(page_title="一体型資産管理アプリ", layout="wide")
st.title("📊 一体型資産管理アプリ")
mode = st.radio("モードを選択してください", ["初期購入", "月次リバランス"])
roe_weight = st.slider("ROEの重み", 0.0, 1.0, 0.6)
usd_to_jpy = get_usd_to_jpy()
st.write(f"📈 現在の為替レート（USD→JPY）: {usd_to_jpy:.2f} 円")

# データ取得
roe_data, per_data, prices = {}, {}, {}
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

df = calculate_scores(roe_data, per_data, roe_weight)
df["Price"] = df["Ticker"].map(prices)
df["Business"] = df["Ticker"].map(tickers_info)
df = df.dropna(subset=["Price"])
df_sorted = df.sort_values(by="Score", ascending=False).copy()

# 初期購入モード
if mode == "初期購入":
    st.header("🛒 初期購入モード")
    initial_yen = st.number_input("💰 初期投資額（円）を入力してください", value=300000, step=10000)
    initial_usd = initial_yen / usd_to_jpy
    
    # スコア上位から順に購入可能か判定
    df_sorted["Allocated_USD"] = initial_usd / 5  # 仮に均等配分
    df_sorted["Shares"] = (df_sorted["Allocated_USD"] / df_sorted["Price"]).astype(int)
    df_sorted["Recommended"] = df_sorted["Shares"].apply(lambda x: "✅" if x > 0 else "❌")
    
    # 📊 全銘柄スコア一覧（購入可否付き）
    st.subheader("📊 スコアランキング（全銘柄）")
    st.dataframe(df_sorted[["Ticker", "Business", "ROE", "PER", "Score", "Price", "Shares", "Recommended"]])
    
    # 🎯 購入推奨銘柄（予算内で1株以上買える）
    st.subheader("🎯 購入推奨銘柄（予算内で購入可能）")
    df_recommended = df_sorted[df_sorted["Recommended"] == "✅"].head(5).copy()
    df_recommended["Used_USD"] = df_recommended["Shares"] * df_recommended["Price"]
    df_recommended["Used_JPY"] = df_recommended["Used_USD"] * usd_to_jpy
    st.dataframe(df_recommended[["Ticker", "Shares", "Price", "Used_USD", "Used_JPY", "Score"]])
    st.write(f"🧾 合計投資額（円）: {df_recommended['Used_JPY'].sum():,.0f} 円")
    
    # ❌ 購入不可銘柄（予算オーバー）
    st.subheader("❌ 購入不可（予算オーバー）")
    df_unbuyable = df_sorted[df_sorted["Recommended"] == "❌"].head(5)
    st.dataframe(df_unbuyable[["Ticker", "Price", "Score", "ROE", "PER"]])
    
    # 📥 CSV出力
    df_recommended["PurchasePriceUSD"] = df_recommended["Price"]
    df_recommended["PurchaseDate"] = pd.Timestamp.today().strftime("%Y-%m-%d")
    df_recommended["ROE"] = df_recommended["Ticker"].map(roe_data)
    df_recommended["PER"] = df_recommended["Ticker"].map(per_data)
    df_recommended["Score"] = df_recommended["Ticker"].map(df.set_index("Ticker")["Score"])
    df_recommended["PurchaseRate"] = usd_to_jpy
    portfolio_df = df_recommended[["Ticker", "Shares", "PurchasePriceUSD", "PurchaseDate", "ROE", "PER", "Score", "PurchaseRate"]]
    csv = portfolio_df.to_csv(index=False).encode("utf-8")
    st.download_button("📄 portfolio.csv をダウンロード", data=csv, file_name="portfolio.csv", mime="text/csv")

# 月次リバランスモード
elif mode == "月次リバランス":
    st.header("🔄 月次リバランスモード")
    uploaded_file = st.file_uploader("📤 portfolio.csv をアップロード", type="csv")
    if uploaded_file is not None:
        portfolio_df = pd.read_csv(uploaded_file)
        owned_tickers = portfolio_df["Ticker"].tolist()
        additional_yen = st.number_input("📥 今月の追加投資額（円）", value=0)
        additional_usd = additional_yen / usd_to_jpy
        
        # 損益計算
        portfolio_df["CurrentPriceUSD"] = portfolio_df["Ticker"].map(prices)
        portfolio_df["CurrentRate"] = usd_to_jpy
        portfolio_df["ProfitJPY"] = (
            (portfolio_df["CurrentPriceUSD"] * portfolio_df["CurrentRate"]) -
            (portfolio_df["PurchasePriceUSD"] * portfolio_df["PurchaseRate"])
        ) * portfolio_df["Shares"]
        
        st.subheader("💰 円ベースの損益（含み益・損）")
        st.dataframe(portfolio_df[["Ticker", "Shares", "PurchasePriceUSD", "CurrentPriceUSD", "PurchaseRate", "CurrentRate", "ProfitJPY"]])
        st.write(f"📈 合計損益（円）: {portfolio_df['ProfitJPY'].sum():,.0f} 円")
        
        # スコア上位から購入可能か判定
        top_candidates = df_sorted.head(10).copy()
        top_candidates["Score"] = top_candidates["Ticker"].map(df.set_index("Ticker")["Score"])
        top_candidates["Weight"] = top_candidates["Score"] / top_candidates["Score"].sum()
        top_candidates["Allocated_USD"] = top_candidates["Weight"] * additional_usd
        top_candidates["Shares"] = (top_candidates["Allocated_USD"] / top_candidates["Price"]).astype(int)
        top_candidates["Recommended"] = top_candidates["Shares"].apply(lambda x: "✅" if x > 0 else "❌")
        
        # 🎯 購入推奨銘柄（予算内で購入可能）
        st.subheader("🎯 購入推奨銘柄（予算内で購入可能）")
        df_recommended = top_candidates[top_candidates["Recommended"] == "✅"].copy()
        st.dataframe(df_recommended[["Ticker", "Price", "Score", "Shares", "Allocated_USD"]])
        
        # ❌ 購入不可銘柄（予算オーバー）
        st.subheader("❌ 購入不可（予算オーバー）")
        df_unbuyable = top_candidates[top_candidates["Recommended"] == "❌"].copy()
        st.dataframe(df_unbuyable[["Ticker", "Price", "Score", "ROE", "PER"]])
        
        # 🔁 売却候補（保有中だが推奨外）
        st.subheader("🔁 売却候補（保有中だが推奨外）")
        sell_candidates = portfolio_df[~portfolio_df["Ticker"].isin(df_recommended["Ticker"])]
        st.dataframe(sell_candidates[["Ticker", "Shares", "ProfitJPY"]])
        
        # 📥 CSV保存
        if st.button("📄 portfolio.csv を更新"):
            df_recommended["PurchasePriceUSD"] = df_recommended["Price"]
            df_recommended["PurchaseDate"] = pd.Timestamp.today().strftime("%Y-%m-%d")
            df_recommended["ROE"] = df_recommended["Ticker"].map(roe_data)
            df_recommended["PER"] = df_recommended["Ticker"].map(per_data)
            df_recommended["PurchaseRate"] = usd_to_jpy
            final_df = df_recommended[["Ticker", "Shares", "PurchasePriceUSD", "PurchaseDate", "ROE", "PER", "Score", "PurchaseRate"]]
            csv = final_df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 portfolio.csv をダウンロード", data=csv, file_name="portfolio.csv", mime="text/csv")
        

