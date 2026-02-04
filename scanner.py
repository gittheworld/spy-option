import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from utils import calculate_time_to_expiry, black_scholes_call, black_scholes_put, calculate_delta, calculate_implied_volatility

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

    def scan_options(self, expirations_to_scan=3, min_volume=100, money_range_pct=0.05, expiry_filter=None, min_days_to_expiry=None):
        """
        Scan options for the next few expirations.
        
        Args:
            expirations_to_scan (int): Number of expiration dates to check.
            min_volume (int): Filter out illiquid options.
            money_range_pct (float): Only look at strikes within +/- X% of spot price.
            expiry_filter (str): Optional string to filter expirations (e.g., "2028-01").
            min_days_to_expiry (int): Optional, only scan expirations > X days away.
        """
        if self.current_price is None:
            self.fetch_current_price()

        all_options = []
        available_expirations = self.get_expirations()
        
        # Filter Expirations
        target_expirations = []
        
        if expiry_filter:
            target_expirations = [e for e in available_expirations if expiry_filter in e]
        elif min_days_to_expiry:
            # Filter dynamically by days
            for exp in available_expirations:
                days = calculate_time_to_expiry(exp) * 365
                if days >= min_days_to_expiry:
                    target_expirations.append(exp)
        else:
            # Limit to the requested number of expirations
            target_expirations = available_expirations[:expirations_to_scan]
        
        if not target_expirations:
             print(f"No expirations found matching criteria.")
             return pd.DataFrame()
        
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
                
                # 1. Calculate Robust ATM Volatility
                # yfinance often returns 0 or NaN for IV on illiquid LEAPS.
                # We typically want the "Average IV" of strikes near the money.
                
                # Filter for "Near-the-Money" options (within 5%) that have VALID IV (> 1%)
                valid_iv_options = chain[
                    (chain['strike'] >= self.current_price * 0.95) & 
                    (chain['strike'] <= self.current_price * 1.05) & 
                    (chain['impliedVolatility'] > 0.01)
                ]
                
                if not valid_iv_options.empty:
                    atm_iv = valid_iv_options['impliedVolatility'].mean()
                else:
                    # Fallback: Look wider (10%)
                    valid_iv_options_wide = chain[
                        (chain['strike'] >= self.current_price * 0.90) & 
                        (chain['strike'] <= self.current_price * 1.10) & 
                        (chain['impliedVolatility'] > 0.01)
                    ]
                    if not valid_iv_options_wide.empty:
                        atm_iv = valid_iv_options_wide['impliedVolatility'].mean()
                    else:
                         # Last resort fallback (e.g., historical avg for SPY ~15-20%)
                         # This prevents the "Delta 1.0" issue when data is missing.
                        atm_iv = 0.15 
                
                chain['atm_iv_ref'] = atm_iv
                
                bs_prices = []
                deltas = []
                recalc_ivs = []
                
                for index, row in chain.iterrows():
                    # Use ASK Price just for valuation if available (Buyer's perspective)
                    ask_price = row.get('ask', 0)
                    bid_price = row.get('bid', 0)
                    last_price = row['lastPrice']
                    
                    # PRIORITY: Ask > Last
                    if ask_price > 0:
                        market_price = ask_price
                    else:
                        market_price = last_price
                    
                    # Save for display
                    chain.at[index, 'priceUsed'] = market_price
                    
                    strike = row['strike']
                    otype = row['type']
                    
                    # A. Back-solve Implied Volatility from Market Price
                    calc_iv = calculate_implied_volatility(market_price, self.current_price, strike, T, RISK_FREE_RATE, otype)
                    
                    # Sanity check
                    if calc_iv <= 0.001 or calc_iv >= 4.9:
                         iv_to_use = atm_iv
                    else:
                         iv_to_use = calc_iv
                         
                    recalc_ivs.append(iv_to_use)
                    
                    # B. Calculate Greeks with THIS IV
                    delta = calculate_delta(self.current_price, strike, T, RISK_FREE_RATE, iv_to_use, otype)
                    deltas.append(delta)

                    # C. Calculate "Theoretical" Price using ATM Volatility
                    if otype == 'call':
                        theo = black_scholes_call(self.current_price, strike, T, RISK_FREE_RATE, atm_iv)
                    else:
                        theo = black_scholes_put(self.current_price, strike, T, RISK_FREE_RATE, atm_iv)
                    bs_prices.append(theo)
                
                # Update DataFrame with our calculated values
                chain['impliedVolatility'] = recalc_ivs
                chain['theo_price_at_atm_iv'] = bs_prices
                chain['delta'] = deltas
                
                # Discount: (Theo - PriceUsed) / PriceUsed * 100
                chain['discount_pct'] = (chain['theo_price_at_atm_iv'] - chain['priceUsed']) / chain['priceUsed'] * 100
                
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
