import streamlit as st
import yfinance as yf
import pandas as pd
import re
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Global variables
data_dic = {}
current_values = []

def get_token_info(symbol):
    """Get basic token information from Yahoo Finance"""
    try:
        token = yf.Ticker(symbol)
        # Direct access to info dictionary
        print("Token Info:", token.info)  # This will print all available info
        return {
            'info': token.info,
            'symbol': symbol,
            'name': symbol
        }
    except Exception as e:
        print(f"Error getting token info: {e}")
        return None
    

def get_crypto_patterns(crypto_symbol, btc_reference, interval):
    global data_dic, current_values
    
    # Get crypto data
    crypto = yf.Ticker(crypto_symbol)
    crypto_data = crypto.history(period="1y", interval=interval)
    print(f"Crypto {crypto_symbol} data range: {crypto_data.index[0]} to {crypto_data.index[-1]}")
    print(f"Total crypto data points: {len(crypto_data)}")
    
    # Get most recent month of crypto data
    crypto_recent = crypto_data.tail(30 if interval == "1d" else 720)  # 30 days or 720 hours
    
    # Get BTC historical data
    btc = yf.Ticker(btc_reference)
    btc_data = btc.history(period="10y", interval=interval)
    print(f"BTC data range: {btc_data.index[0]} to {btc_data.index[-1]}")
    print(f"Total BTC data points: {len(btc_data)}")
    
    # Create U/D pattern for current crypto (using recent data)
    crypto_pattern = ''.join(['U' if crypto_recent.iloc[i]['Close'] >= crypto_recent.iloc[i-1]['Close'] else 'D'
                            for i in range(1, len(crypto_recent))])
    
    # Get latest pattern (last 8 periods)
    current_pattern = crypto_pattern[-8:]
    print(f"Current pattern being searched: {current_pattern}")
    
    # Create U/D pattern for BTC historical data
    btc_pattern = ''.join(['U' if btc_data.iloc[i]['Close'] >= btc_data.iloc[i-1]['Close'] else 'D'
                          for i in range(1, len(btc_data))])
    
    # Exclude recent BTC data to avoid correlation
    exclude_periods = 720 if interval == "1h" else 30  # Last month in hours or days
    btc_pattern = btc_pattern[:-exclude_periods]
    btc_data = btc_data.iloc[:-exclude_periods]
    
    # Find matches in BTC history
    index_dict = {}
    pattern_length = len(current_pattern)
    print(f"Searching for pattern of length: {pattern_length}")
    
    indices = [index.start() for index in re.finditer(current_pattern, btc_pattern)]
    print(f"Found {len(indices)} matching patterns in BTC history")
    
    if len(indices) > 2:
        for matched_index in indices[1:]:
            if matched_index not in index_dict:
                index_dict[matched_index] = pattern_length
    
    # Process matches
    for key, value in index_dict.items():
        indices, matched, future_average = print_difference_data(
            btc_data, key, value, 13)
        index_dict[key] = (value, indices, matched, future_average)
    
    # Get current crypto values (last 8 periods)
    current_values = [{
        'date': crypto_recent.iloc[count].name.strftime('%d-%b-%Y %H:%M' if interval == "1h" else '%d-%b-%Y'),
        'close': crypto_recent.iloc[count]['Close'],
        'percentage_difference': ((crypto_recent.iloc[count]['Close'] - crypto_recent.iloc[count+1]['Close']) /
                                crypto_recent.iloc[count+1]['Close']) * 100
    } for count in range(min(8, len(crypto_recent)-1))]
    
    print(f"Processed {len(current_values)} current values")
    print(f"Found {len(index_dict)} unique pattern matches")
    
    return index_dict, current_values

    
def print_difference_data(arg_array, index, matched_length, forward_length):
    matched = [{
        'date': arg_array.iloc[count].name.strftime('%d-%b-%Y %H:%M'),
        'close': arg_array.iloc[count]['Close'],
        'percentage_difference': ((arg_array.iloc[count]['Close'] - arg_array.iloc[count+1]['Close']) /
                                arg_array.iloc[count+1]['Close']) * 100
    } for count in range(index, index + matched_length)]

    indices = [{
        'date': arg_array.iloc[count].name.strftime('%d-%b-%Y %H:%M'),
        'close': arg_array.iloc[count]['Close'],
        'percentage_difference': ((arg_array.iloc[count-1]['Close'] - arg_array.iloc[count]['Close']) /
                                arg_array.iloc[count]['Close']) * 100
    } for count in range(index, index - forward_length, -1)]

    future_average = sum(index['percentage_difference']
                        for index in indices) / len(indices)
    return indices, matched, future_average

def main():
    st.title("Crypto Pattern Analysis App")

    # User input for crypto symbol
    crypto_symbol = st.text_input("Enter Crypto Symbol (e.g., ETH-USD, SOL-USD)", "ETH-USD")
    selected_interval = st.selectbox("Select an interval", ["1d", "1h"])

    if st.button("Analyze"):
        # Get token info
        token_info = get_token_info(crypto_symbol)
        if token_info:
            st.subheader(f"Analyzing {token_info['info']} ({token_info['symbol']})")
            st.write(f"Info : {token_info['info']}")
            
            # Get patterns
            data_dic, current_values = get_crypto_patterns(
                crypto_symbol, "BTC-USD", selected_interval)

            # Split display into two columns
            col1, col2 = st.columns(2)

            # Current crypto prices (left column)
            with col1:
                st.subheader(f"Current {token_info['name']} Prices")
                
                dates = [datetime.strptime(data['date'], '%d-%b-%Y %H:%M' if selected_interval == "1h" else '%d-%b-%Y')
                        for data in current_values]
                current_prices = [data['close'] for data in current_values]
                current_trace = go.Scatter(x=dates, y=current_prices, mode='lines+markers',
                                        name='Current Prices', marker=dict(color='blue'))

                fig_current = go.Figure(data=[current_trace])
                fig_current.update_layout(
                    title=f"Current {token_info['name']} Prices",
                    xaxis_title="Date & Time" if selected_interval == "1h" else "Date",
                    yaxis_title="Price",
                    showlegend=False
                )
                st.plotly_chart(fig_current)
                
                current_df = pd.DataFrame(current_values)
                st.dataframe(current_df)

            # Bitcoin historical patterns (right column)
            with col2:
                st.subheader("Similar Bitcoin Patterns")
                
                future_traces = []
                colors = ['green', 'red', 'purple', 'orange', 'brown']
                last_close = current_prices[-1]
                last_date = dates[-1]

                for i, (_, data) in enumerate(list(data_dic.items())[:5]):
                    pattern, indices, _, _ = data
                    future_returns = [index['percentage_difference'] / 100 for index in indices[:10]]
                    future_prices = [last_close]
                    for j in range(10):
                        future_prices.append(future_prices[-1] * (1 + future_returns[j]))
                    
                    future_dates = [last_date + timedelta(hours=j+1) if selected_interval == "1h" else last_date + timedelta(days=j+1) 
                                  for j in range(10)]
                    
                    future_trace = go.Scatter(
                        x=future_dates, 
                        y=future_prices[1:], 
                        mode='lines', 
                        name=f'BTC Pattern {i+1} ({pattern})', 
                        marker=dict(color=colors[i]))
                    future_traces.append(future_trace)

                fig_future = go.Figure(data=future_traces)
                fig_future.update_layout(
                    title="Historical Bitcoin Patterns",
                    xaxis_title="Date & Time" if selected_interval == "1h" else "Date",
                    yaxis_title="Projected Price",
                    showlegend=True
                )
                st.plotly_chart(fig_future)

                # Display pattern matches table
                matched_data = []
                for i, (_, data) in enumerate(list(data_dic.items())[:5]):
                    pattern, indices, _, _ = data
                    for index in indices[:10]:
                        matched_data.append({
                            'date': index['date'],
                            'percentage_difference': index['percentage_difference']
                        })

                future_df = pd.DataFrame(matched_data)
                st.dataframe(future_df)
        else:
            st.error("Invalid crypto symbol or unable to fetch token information")

if __name__ == "__main__":
    main()