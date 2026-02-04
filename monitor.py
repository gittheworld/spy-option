import time
from datetime import datetime
from scanner import SPYScanner
from tabulate import tabulate

# Configuration
SCAN_INTERVAL_SECONDS = 60
DISCOUNT_THRESHOLD = 15.0
TICKERS = ["SPY", "QQQ", "SOXX", "NVDA", "AAPL"]

def main():
    print("Initializing Market Options Monitor (Console Mode)...")
    print(f"Monitoring started. Ctrl+C to stop.")
    print(f"Tickers: {TICKERS}")
    print(f"Filters: Expiry > 365 Days, ITM Call, Discount > {DISCOUNT_THRESHOLD}%")
    
    try:
        while True:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{timestamp}] Scanning LEAPS across {len(TICKERS)} tickers...")
            
            all_bargains = []
            
            for ticker in TICKERS:
                try:
                    # print(f"  > Scanning {ticker}...", end="\r")
                    scanner = SPYScanner(ticker)
                    
                    # Scan LEAPS
                    options_df = scanner.scan_options(min_volume=0, money_range_pct=0.50, min_days_to_expiry=365)
                    
                    if not options_df.empty:
                        # Filter ITM Calls
                        current_price = scanner.current_price
                        itm_calls = options_df[ (options_df['type'] == 'call') & (options_df['strike'] < current_price) ]
                        
                        if not itm_calls.empty:
                            # Use internal helper to get bargains, but we want ALL of them to aggregate first
                            # logic from scanner.find_bargains allows getting top_n. Let's get top 20 per ticker to save memory
                            _, bargains = scanner.find_bargains(itm_calls, top_n=20)
                            
                            if not bargains.empty:
                                bargains['Ticker'] = ticker # Add Identifier
                                all_bargains.append(bargains)
                                
                except Exception as e:
                    print(f"  x Error scanning {ticker}: {e}")

            # Process Aggregated Results
            if all_bargains:
                import pandas as pd
                consolidated = pd.concat(all_bargains, ignore_index=True)
                
                # Sort by Discount descending
                consolidated = consolidated.sort_values(by='discount_pct', ascending=False)
                
                # Check Threshold
                alerts = consolidated[consolidated['discount_pct'] > DISCOUNT_THRESHOLD]
                
                if not alerts.empty:
                    print(f"\n🚨 FOUND {len(alerts)} BARGAINS! (Discount > {DISCOUNT_THRESHOLD}%)")
                    cols_to_show = ['Ticker', 'expiry', 'strike', 'bid', 'ask', 'lastPrice', 'delta', 'impliedVolatility', 'theo_price_at_atm_iv', 'discount_pct']
                    print(tabulate(alerts[cols_to_show], headers='keys', tablefmt='pretty', floatfmt=".2f"))
                    print("\a")
                else:
                    print(f"\n   No alerts (> {DISCOUNT_THRESHOLD}%). 🏆 Top 5 Best Bargains across market:")
                    top5 = consolidated.head(5)
                    cols_to_show = ['Ticker', 'expiry', 'strike', 'bid', 'ask', 'lastPrice', 'delta', 'impliedVolatility', 'theo_price_at_atm_iv', 'discount_pct']
                    print(tabulate(top5[cols_to_show], headers='keys', tablefmt='pretty', floatfmt=".2f"))
            else:
                print("\n   No bargains found across any ticker.")

            print(f"   Sleeping for {SCAN_INTERVAL_SECONDS} seconds...", end="\r")
            time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopping Monitor...")

if __name__ == "__main__":
    main()
