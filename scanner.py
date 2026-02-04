import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from utils import calculate_time_to_expiry, black_scholes_call, black_scholes_put, calculate_delta

RISK_FREE_RATE = 0.045  # Approx 4.5%

class SPYScanner:
    def __init__(self, ticker="SPY"):
        self.ticker_symbol = ticker
        self.stock = yf.Ticker(ticker)
        self.current_price = None

    def fetch_current_price(self):
        """Fetch the latest underlying price."""
        # fast_info is usually faster and more reliable than history() for latest price
        try:
            self.current_price = self.stock.fast_info['last_price']
        except:
            # Fallback
            hist = self.stock.history(period="1d")
            if not hist.empty:
                self.current_price = hist['Close'].iloc[-1]
        return self.current_price

    def get_expirations(self):
        return self.stock.options

    def scan_options(self, expirations_to_scan=3, min_volume=100, money_range_pct=0.05, expiry_filter=None):
        """
        Scan options for the next few expirations.
        
        Args:
            expirations_to_scan (int): Number of expiration dates to check.
            min_volume (int): Filter out illiquid options.
            money_range_pct (float): Only look at strikes within +/- X% of spot price.
            expiry_filter (str): Optional string to filter expirations (e.g., "2028-01").
        """
        if self.current_price is None:
            self.fetch_current_price()

        all_options = []
        available_expirations = self.get_expirations()
        
        # Filter Expirations if requested
        if expiry_filter:
            target_expirations = [e for e in available_expirations if expiry_filter in e]
            if not target_expirations:
                print(f"No expirations found matching '{expiry_filter}'. Available: {available_expirations}")
                return pd.DataFrame()
        else:
            # Limit to the requested number of expirations
            target_expirations = available_expirations[:expirations_to_scan]
        
        print(f"Scanning expirations: {target_expirations}")
        print(f"Current {self.ticker_symbol} Price: ${self.current_price:.2f}")

        for exp in target_expirations:
            try:
                opt_chain = self.stock.option_chain(exp)
                T = calculate_time_to_expiry(exp)
                
                # Process Calls
                calls = opt_chain.calls
                calls['type'] = 'call'
                calls['T'] = T
                calls['expiry'] = exp
                
                # Process Puts
                puts = opt_chain.puts
                puts['type'] = 'put'
                puts['T'] = T
                puts['expiry'] = exp
                
                # Combine
                chain = pd.concat([calls, puts])
                
                # Filter by Volume
                chain = chain[chain['volume'] >= min_volume]
                
                # Filter by Strike (Money Range)
                lower_bound = self.current_price * (1 - money_range_pct)
                upper_bound = self.current_price * (1 + money_range_pct)
                chain = chain[(chain['strike'] >= lower_bound) & (chain['strike'] <= upper_bound)]
                
                # --- Cheapness Logic ---
                
                # 1. Calculate ATM Volatility for this expiry (approximate)
                # Find strike closest to current price
                atm_strike = chain.iloc[(chain['strike'] - self.current_price).abs().argsort()[:1]]
                if not atm_strike.empty:
                    atm_iv = atm_strike['impliedVolatility'].values[0]
                else:
                    atm_iv = 0.20 # Fallback default
                
                chain['atm_iv_ref'] = atm_iv
                
                # 2. Check for "High Value" (Low IV relative to ATM)
                # We calculate what the price WOULD be if it had ATM IV
                # Then Compare Market Price vs ATM-IV Price.
                # If Market Price < ATM-IV Price, it implies the option's specific IV is lower than ATM.
                
                bs_prices = []
                deltas = []
                for index, row in chain.iterrows():
                    sigma = row['atm_iv_ref'] # Use the "Benchmark" IV
                    
                    # Calculate Theoretical Price & Delta
                    # For Delta, we generally use the option's OWN implied volatility to get the "Market Delta",
                    # but using ATM IV gives a "Theoretical Delta". 
                    # Users usually want "Market Delta" (what brokers show). 
                    # Let's use the option's own IV for Delta if available, otherwise ATM.
                    delta_sigma = row['impliedVolatility'] if row['impliedVolatility'] > 0 else sigma
                    
                    delta = calculate_delta(self.current_price, row['strike'], T, RISK_FREE_RATE, delta_sigma, row['type'])
                    deltas.append(delta)

                    if row['type'] == 'call':
                        theo = black_scholes_call(self.current_price, row['strike'], T, RISK_FREE_RATE, sigma)
                    else:
                        theo = black_scholes_put(self.current_price, row['strike'], T, RISK_FREE_RATE, sigma)
                    bs_prices.append(theo)
                
                chain['theo_price_at_atm_iv'] = bs_prices
                chain['delta'] = deltas
                
                # Discount: How much cheaper is the market price compared to the theoretical price at ATM IV?
                # Positive number means Market is CHEAPER than Theoretical (Good for buying)
                chain['discount_amt'] = chain['theo_price_at_atm_iv'] - chain['lastPrice']
                chain['discount_pct'] = (chain['discount_amt'] / chain['lastPrice']) * 100
                
                all_options.append(chain)
                
            except Exception as e:
                print(f"Error processing expiry {exp}: {e}")

        if not all_options:
            return pd.DataFrame()

        full_df = pd.concat(all_options)
        return full_df

    def find_bargains(self, df, top_n=10):
        """
        Filter and sort for the best bargains.
        Criteria:
        1. Lowest Implied Volatility (Absolute)
        2. Best 'Discount' vs ATM IV
        """
        if df.empty:
            return df
        
        # Sort by lowest IV
        lowest_iv = df.sort_values(by='impliedVolatility').head(top_n)
        
        # Sort by biggest discount % (Market Price is lower than Theoretical ATM price)
        # We filter where discount is positive (Market < Model)
        discounted = df[df['discount_pct'] > 0].sort_values(by='discount_pct', ascending=False).head(top_n)
        
        return lowest_iv, discounted
