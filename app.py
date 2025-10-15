import streamlit as st
import pandas as pd
import requests
import qrcode
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns

# Config
MEMPOOL_API = "https://mempool.space/api/v1"
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"

st.title("🪙 BTC Stacker Dashboard")
st.sidebar.title("Quick Actions")

# 1. Upload & Parse Shakepay CSV
uploaded_file = st.file_uploader("Upload Shakepay CSV", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    # Assume columns: 'Date', 'Type', 'Currency', 'Amount', 'Price', etc. (adjust based on export)
    df['Date'] = pd.to_datetime(df['Date'])
    buys = df[df['Type'] == 'Buy'].copy()
    total_invested = buys['Amount'].sum() * buys['Price'].mean()  # CAD invested
    total_sats = buys['Crypto Amount'].sum() * 1e8  # Convert to sats
    dca_price = total_invested / (total_sats / 1e8)
    current_price = requests.get(COINGECKO_API).json()['bitcoin']['usd']
    unrealized = (current_price - dca_price) / dca_price * 100

    st.subheader("📊 Stacking Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Invested (CAD)", f"${total_invested:,.2f}")
    col2.metric("Sats Stacked", f"{total_sats:,.0f}")
    col3.metric("DCA Price (USD)", f"${dca_price:.2f}")
    col4.metric("Unrealized Gains", f"{unrealized:.1f}%")

    # Chart: Cumulative sats over time
    buys_cum = buys.sort_values('Date').cumsum()['Crypto Amount']
    fig, ax = plt.subplots()
    sns.lineplot(data=buys_cum, ax=ax)
    ax.set_title("Cumulative Sats Stacked")
    st.pyplot(fig)

# 2. Withdrawal Optimizer
st.subheader("💸 Withdrawal to Ledger")
ledger_address = st.text_input("Ledger BTC Address")
sats_to_send = st.number_input("Sats to Send", min_value=1000, value=10000)
if st.button("Optimize & Generate QR") and ledger_address:
    # Fetch mempool data
    fees = requests.get(f"{MEMPOOL_API}/fees/recommended").json()
    mempool_size = requests.get(f"{MEMPOOL_API}/mempool/info").json()['size']
    
    tx_size_est = 250  # vBytes for simple P2PKH tx
    fee_sat_vb = fees['economyFee']  # Low priority
    total_fee = tx_size_est * fee_sat_vb
    net_sats = sats_to_send - total_fee
    eta_blocks = 6 if fee_sat_vb >= fees['hourFee'] else "1-2 hours"

    st.metric("Estimated Fee", f"{total_fee} sats (~${total_fee * current_price / 1e8:.4f})")
    st.metric("Net Sats Received", f"{net_sats}")
    st.metric("ETA", eta_blocks)
    st.warning("Mempool Size: {:.1f} MB – " + ("Good to send!" if mempool_size < 20 else "Wait for lower congestion") .format(mempool_size))

    # QR Code for address
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(ledger_address)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    st.image(img, caption="Scan to Verify Ledger Address")

# 3. Stacking Simulator
st.subheader("🔮 Future Stacker")
weekly_buy_cad = st.number_input("Weekly Buy (CAD)", value=50)
weeks = st.slider("Over Weeks", 1, 52, 12)
projected_sats = (weekly_buy_cad * weeks) / current_price * 1e8
st.success(f"Projected Sats: {projected_sats:,.0f}")

# Run: streamlit run app.py