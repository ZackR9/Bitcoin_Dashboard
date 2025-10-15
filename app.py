import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Config
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=cad,usd"

st.set_page_config(page_title="BTC Tax Tracker", page_icon="🪙")
st.title("🪙 Bitcoin Tax & Profit Tracker")
st.sidebar.title("Shakepay Analytics")

# Get current BTC price
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_btc_price():
    response = requests.get(COINGECKO_API)
    return response.json()['bitcoin']

current_prices = get_btc_price()
current_price_cad = current_prices['cad']
current_price_usd = current_prices['usd']

# Display current price in sidebar
st.sidebar.metric("Current BTC Price (CAD)", f"${current_price_cad:,.2f}")
st.sidebar.metric("Current BTC Price (USD)", f"${current_price_usd:,.2f}")

# 1. Upload & Parse Shakepay CSV
st.subheader("📊 Upload Shakepay Transaction History")
st.info("Export your **crypto transactions** from Shakepay: Settings → Export Transaction History → Crypto Transactions")

uploaded_file = st.file_uploader("Upload Shakepay Crypto Transactions CSV", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # Show raw data preview
    with st.expander("View Raw Data"):
        st.dataframe(df.head(10))
    
    # Parse dates (Shakepay uses "Date" column)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Filter for Bitcoin purchases only (Type = "Buy" and Asset Credited = "BTC")
    btc_buys = df[(df['Type'] == 'Buy') & (df['Asset Credited'] == 'BTC')].copy()
    
    if len(btc_buys) == 0:
        st.warning("No Bitcoin purchases found in this CSV file. Make sure you uploaded the **Crypto Transactions** CSV.")
    else:
        # Calculate metrics using the actual column names
        total_btc_purchased = btc_buys['Amount Credited'].sum()
        total_cad_spent = btc_buys['Book Cost'].sum()
        average_buy_price = total_cad_spent / total_btc_purchased
        total_sats = total_btc_purchased * 1e8
        
        # Current value and profit/loss
        current_value_cad = total_btc_purchased * current_price_cad
        unrealized_gain_cad = current_value_cad - total_cad_spent
        unrealized_gain_pct = (unrealized_gain_cad / total_cad_spent) * 100
        
        # Display Summary Metrics
        st.subheader("💰 Portfolio Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Invested (CAD)", f"${total_cad_spent:,.2f}")
            st.metric("Total BTC Purchased", f"{total_btc_purchased:.8f}")
            st.metric("Total Sats", f"{total_sats:,.0f}")
        
        with col2:
            st.metric("Average Buy Price (CAD)", f"${average_buy_price:,.2f}")
            st.metric("Current Value (CAD)", f"${current_value_cad:,.2f}")
            st.metric("Number of Purchases", len(btc_buys))
        
        with col3:
            st.metric(
                "Unrealized Gain/Loss (CAD)", 
                f"${unrealized_gain_cad:,.2f}",
                delta=f"{unrealized_gain_pct:.2f}%"
            )
            break_even_price = average_buy_price
            st.metric("Break-even Price (CAD)", f"${break_even_price:,.2f}")
        
        # Tax Information
        st.subheader("📋 Tax Information (Canada)")
        st.write(f"**Tax Year:** {datetime.now().year}")
        st.write(f"**Cost Basis (ACB):** ${total_cad_spent:,.2f} CAD")
        st.write(f"**Current Fair Market Value:** ${current_value_cad:,.2f} CAD")
        
        if unrealized_gain_cad > 0:
            capital_gain_50pct = unrealized_gain_cad * 0.5
            st.write(f"**Unrealized Capital Gain (50% taxable):** ${capital_gain_50pct:,.2f} CAD")
            st.info("💡 This is unrealized gain. Capital gains tax only applies when you sell or dispose of your Bitcoin.")
        else:
            st.write(f"**Unrealized Capital Loss:** ${abs(unrealized_gain_cad):,.2f} CAD")
        
        # Transaction History Table
        st.subheader("📜 Transaction History")
        
        # Prepare display dataframe
        display_df = btc_buys[['Date', 'Amount Credited', 'Book Cost', 'Buy / Sell Rate']].copy()
        display_df.columns = ['Date', 'BTC Purchased', 'CAD Spent', 'Price per BTC']
        display_df['Sats'] = display_df['BTC Purchased'] * 1e8
        display_df = display_df.sort_values('Date', ascending=False)
        
        st.dataframe(
            display_df.style.format({
                'BTC Purchased': '{:.8f}',
                'CAD Spent': '${:,.2f}',
                'Price per BTC': '${:,.2f}',
                'Sats': '{:,.0f}'
            }),
            use_container_width=True
        )
        
        # Charts
        st.subheader("📈 Visualizations")
        
        # Cumulative BTC stacked over time
        col1, col2 = st.columns(2)
        
        with col1:
            buys_sorted = btc_buys.sort_values('Date').copy()
            buys_sorted['Cumulative BTC'] = buys_sorted['Amount Credited'].cumsum()
            
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.lineplot(data=buys_sorted, x='Date', y='Cumulative BTC', ax=ax, marker='o')
            ax.set_title("Cumulative BTC Accumulated Over Time")
            ax.set_ylabel("Total BTC")
            ax.set_xlabel("Date")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
        
        with col2:
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.barplot(data=buys_sorted, x='Date', y='Amount Credited', ax=ax)
            ax.set_title("BTC Purchase Amounts")
            ax.set_ylabel("BTC Purchased")
            ax.set_xlabel("Date")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
        
        # Download tax summary
        st.subheader("💾 Export Tax Summary")
        tax_summary = f"""
Bitcoin Tax Summary - {datetime.now().year}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

PORTFOLIO SUMMARY:
Total BTC Purchased: {total_btc_purchased:.8f} BTC
Total CAD Invested: ${total_cad_spent:,.2f} CAD
Average Cost Basis: ${average_buy_price:,.2f} CAD per BTC
Number of Transactions: {len(btc_buys)}

CURRENT POSITION:
Current BTC Price: ${current_price_cad:,.2f} CAD
Current Portfolio Value: ${current_value_cad:,.2f} CAD
Unrealized Gain/Loss: ${unrealized_gain_cad:,.2f} CAD ({unrealized_gain_pct:.2f}%)

TAX INFORMATION (Canada):
Adjusted Cost Base (ACB): ${total_cad_spent:,.2f} CAD
Fair Market Value: ${current_value_cad:,.2f} CAD
Unrealized Capital Gain (50% taxable): ${unrealized_gain_cad * 0.5:,.2f} CAD

Note: Consult with a tax professional for accurate tax reporting.
"""
        st.download_button(
            label="Download Tax Summary (TXT)",
            data=tax_summary,
            file_name=f"btc_tax_summary_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )

else:
    st.warning("👆 Please upload your Shakepay **Crypto Transactions** CSV file to begin analysis")
    st.markdown("""
    ### How to Export:
    1. Open Shakepay app
    2. Go to **Settings**
    3. Select **Export Transaction History**
    4. Choose **Crypto Transactions Summary**
    5. Upload the `crypto_transactions_summary.csv` file here
    
    ### Required Columns:
    - Date
    - Type (should include 'Buy')
    - Asset Credited (BTC)
    - Amount Credited
    - Book Cost (CAD spent)
    """)

# Footer
st.markdown("---")
st.caption("⚠️ This tool is for informational purposes only. Consult a tax professional for official tax advice.")

# Run: streamlit run app.py