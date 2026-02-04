import numpy as np
from scipy.stats import norm
from datetime import datetime

def d1(S, K, T, r, sigma):
    """Calculate d1 for Black-Scholes."""
    # Avoid division by zero for very small T or sigma
    if T <= 0 or sigma <= 0:
        return 0
    return (np.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * np.sqrt(T))

def d2(S, K, T, r, sigma):
    """Calculate d2 for Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return 0
    return d1(S, K, T, r, sigma) - sigma * np.sqrt(T)

def calculate_delta(S, K, T, r, sigma, option_type='call'):
    """Calculate Delta for an option."""
    if T <= 0 or sigma <= 0:
        return 0
    d_1 = d1(S, K, T, r, sigma)
    if option_type == 'call':
        return norm.cdf(d_1)
    else:
        return norm.cdf(d_1) - 1

def black_scholes_call(S, K, T, r, sigma):
    """Calculate theoretical price for a Call option."""
    if T <= 0:
        return max(0, S - K)
    d_1 = d1(S, K, T, r, sigma)
    d_2 = d2(S, K, T, r, sigma)
    return S * norm.cdf(d_1) - K * np.exp(-r * T) * norm.cdf(d_2)

def black_scholes_put(S, K, T, r, sigma):
    """Calculate theoretical price for a Put option."""
    if T <= 0:
        return max(0, K - S)
    d_1 = d1(S, K, T, r, sigma)
    d_2 = d2(S, K, T, r, sigma)
    return K * np.exp(-r * T) * norm.cdf(-d_2) - S * norm.cdf(-d_1)

def calculate_time_to_expiry(expiry_date_str):
    """
    Calculate time to expiry in years.
    expiry_date_str: 'YYYY-MM-DD'
    """
    expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d")
    today = datetime.now()
    delta = expiry - today
    return max(delta.days / 365.0, 0.0001) # Avoid 0

def calculate_vega(S, K, T, r, sigma):
    """Calculate Vega for Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return 0
    d_1 = d1(S, K, T, r, sigma)
    return S * np.sqrt(T) * norm.pdf(d_1)

def calculate_implied_volatility(price, S, K, T, r, option_type='call', tol=1e-5, max_iter=100):
    """
    Calculate Implied Volatility using Newton-Raphson method.
    """
    if T <= 0 or price <= 0:
        return 0
        
    sigma = 0.5 # Initial guess (50%)
    
    for i in range(max_iter):
        if option_type == 'call':
            theo_price = black_scholes_call(S, K, T, r, sigma)
        else:
            theo_price = black_scholes_put(S, K, T, r, sigma)
            
        diff = theo_price - price
        
        if abs(diff) < tol:
            return sigma
            
        vega = calculate_vega(S, K, T, r, sigma)
        
        if vega == 0:
            break
            
        sigma = sigma - diff / vega
        
        # Keep sigma within bounds
        if sigma <= 0:
            sigma = 0.001
        if sigma > 5.0: # Cap at 500%
            sigma = 5.0
            break
            
    return sigma
