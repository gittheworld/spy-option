from scanner import SPYScanner
from tabulate import tabulate
import pandas as pd

def main():
    print("Initializing SPY Options Scanner...")
    scanner = SPYScanner("SPY")
    
    print("Fetching data (this may take a few seconds)...")
    # User requested 2028 Jan LEAPS, ITM Calls.
    # We widen the range to 50% to catch Deep ITM options.
    # Lowered min_volume to ensure we see available options even if illiquid.
    options_df = scanner.scan_options(min_volume=5, money_range_pct=0.50, expiry_filter="2028-01")
    
    if options_df.empty:
        print("No options found matching criteria.")
        return

    # Filter for ITM Calls (Strike < Current Price)
    print(f"Filtering for ITM Calls (Strike < ${scanner.current_price:.2f})...")
    itm_calls = options_df[ (options_df['type'] == 'call') & (options_df['strike'] < scanner.current_price) ]

    if itm_calls.empty:
        print("No ITM Calls found.")
        return

    lowest_iv, best_discounts = scanner.find_bargains(itm_calls, top_n=10)

    # Clean up output for display
    cols_to_show = ['expiry', 'type', 'strike', 'delta', 'lastPrice', 'impliedVolatility', 'volume', 'openInterest']
    
    if 'discount_pct' in best_discounts.columns:
        cols_dicount = cols_to_show + ['atm_iv_ref', 'theo_price_at_atm_iv', 'discount_pct']
    else:
        cols_dicount = cols_to_show

    print("\n" + "="*50)
    print(" TOP 10 'CHEAPEST' ITM LEAPS CALLS (Absolute IV) ")
    print("="*50)
    print(tabulate(lowest_iv[cols_to_show], headers='keys', tablefmt='pretty', floatfmt=".2f"))

    print("\n" + "="*50)
    print(" TOP 10 'BARGAINS' ITM LEAPS CALLS (Price < Theoretical) ")
    print("="*50)
    print(tabulate(best_discounts[cols_dicount], headers='keys', tablefmt='pretty', floatfmt=".2f"))

if __name__ == "__main__":
    main()
