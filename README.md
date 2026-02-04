# SPY Options Scanner 🕵️‍♂️📈

A Python-based tool designed to scan **SPY (S&P 500 ETF)** options chain to identify potential "bargains" and value opportunities using logical and mathematical filters.

Current focus: **Deep Value ITM LEAPS (Long-Term Equity Anticipation Securities)**.

## 🚀 Key Features

*   **Real-time Data Fetching**: Uses `yfinance` to grab the latest options chain data.
*   **Smart Filtering**:
    *   **Low Implied Volatility (IV)**: Finds options with historically low volatility premiums.
    *   **Black-Scholes Validation**: Calculates the "Theoretical Price" based on ATM (At-The-Money) volatility and compares it to the Market Price.
    *   **ITM LEAPS Focus**: Specifically tuned to find long-term In-The-Money Call options (e.g., 2028 Expiry).
    *   **Greeks Calculation**: Automatically calculates **Delta** to help assess leverage and exposure.

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/gittheworld/spy-option.git
    cd spy-option
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 💻 Usage

Run the main script to start the scanner:

```bash
python main.py
```

### Output Explained

The script generates two main tables:

1.  **TOP 10 CHEAPEST ITM LEAPS (Absolute IV)**
    *   Lists options with the lowest absolute Implied Volatility.
    *   Useful for finding "cheap" premium.

2.  **TOP 10 BARGAINS (Price < Theoretical)**
    *   **Discount %**: Shows how much cheaper the Market Price is compared to the Theoretical Black-Scholes price (calculated using the "average" ATM IV).
    *   **Delta**: The rate of change of the option price with respect to the underlying. High delta (>0.70) ITM LEAPS act as stock replacements.

## ⚙️ Configuration

You can customize the scan settings in `main.py`:

```python
# Example: Modifying the scanner call in main.py
options_df = scanner.scan_options(
    min_volume=5,           # Lower volume filter for illiquid LEAPS
    money_range_pct=0.50,   # 50% range to catch Deep ITM
    expiry_filter="2028-01" # Filter specifically for Jan 2028 options
)
```

## ⚠️ Disclaimer

This tool is for **informational and educational purposes only**. Using functionality like `yfinance` relies on delayed public data which may not be accurate enough for high-frequency trading. Always verify prices with your broker before trading.
