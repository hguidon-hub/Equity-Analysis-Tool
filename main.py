PROGRAM_NAME = "EquityAnalysisTool"
VERSION = "1.0"

print(
    f"{PROGRAM_NAME} v{VERSION}"
)

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# STOCK INFORMATION
# ============================================================

def get_stock_info(ticker):

    info = ticker.info

    return {
        "price": info.get("currentPrice"),
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "dividend_yield": info.get("dividendYield"),
        "high_52w": info.get("fiftyTwoWeekHigh"),
        "low_52w": info.get("fiftyTwoWeekLow")
    }


# ============================================================
# HISTORICAL VOLATILITY
# ============================================================

def get_historical_volatility(ticker):

    history = ticker.history(period="1y")

    if history.empty:
        return None

    returns = np.log(
        history["Close"] /
        history["Close"].shift(1)
    ).dropna()

    volatility = returns.std() * np.sqrt(252)

    return volatility * 100

# ============================================================
# SHARPE RATIO
# ============================================================

def get_sharpe_ratio(ticker, risk_free_rate=0.02):

    history = ticker.history(period="1y")

    if history.empty:
        return None

    returns = history["Close"].pct_change().dropna()

    annual_return = returns.mean() * 252

    annual_volatility = returns.std() * np.sqrt(252)

    if annual_volatility == 0:
        return None

    sharpe = (
        annual_return - risk_free_rate
    ) / annual_volatility

    return sharpe

# ============================================================
# FINANCIAL STATEMENTS
# ============================================================

def get_financial_data(ticker):

    try:

        income = ticker.quarterly_income_stmt

        if income is None or income.empty:
            return None

        return income

    except Exception as e:

        print(f"Error retrieving financial data: {e}")
        return None


# ============================================================
# BUILD REVENUE / NET INCOME DATAFRAME
# ============================================================

def build_financial_dataframe(income):

    revenues = []
    net_incomes = []
    dates = []

    for date in income.columns:

        revenue = (
            income.loc["Total Revenue", date]
            if "Total Revenue" in income.index
            else np.nan
        )

        net_income = (
            income.loc["Net Income", date]
            if "Net Income" in income.index
            else np.nan
        )

        dates.append(date)

        revenues.append(revenue)
        net_incomes.append(net_income)

    df = pd.DataFrame({
        "Date": dates,
        "Revenue": revenues,
        "Net Income": net_incomes
    })

    df.sort_values(
        by="Date",
        inplace=True
    )

    df["Revenue Growth %"] = (
        df["Revenue"].pct_change() * 100
    )

    df["Net Income Change"] = (
            df["Net Income"]
            - df["Net Income"].shift(1)
    )

    return df


# ============================================================
# PRINT SUMMARY
# ============================================================

def print_summary(symbol, stock_info, volatility, sharpe_ratio, df):

    latest = df.iloc[-1]

    previous = df.iloc[-2] if len(df) >= 2 else None

    print("\n" + "=" * 60)
    print(f"{symbol} EQUITY INSIGHT")
    print("=" * 60)

    print(f"Current Price: ${stock_info['price']:.2f}")

    market_cap = stock_info["market_cap"]

    if market_cap:
        print(f"Market Cap: ${market_cap:,.0f}")

    print(f"P/E Ratio: {stock_info['pe']}")
    print(f"Forward P/E: {stock_info['forward_pe']}")

    dividend = stock_info["dividend_yield"]

    if dividend is None:
        dividend_pct = 0.0
    else:
        dividend_pct = dividend

    print(f"Dividend Yield: {dividend_pct:.2f}%")

    print(f"52W High: ${stock_info['high_52w']}")
    print(f"52W Low: ${stock_info['low_52w']}")

    if volatility:
        print(
            f"Historical Volatility: "
            f"{volatility:.2f}%"
        )

    if sharpe_ratio is not None:
        print(
            f"Sharpe Ratio: "
            f"{sharpe_ratio:.2f}"
        )

    print("\nLATEST QUARTER")

    if latest["Revenue"] >= 1e9:
        revenue_text = f"${latest['Revenue'] / 1e9:.2f}B"
    elif latest["Revenue"] >= 1e6:
        revenue_text = f"${latest['Revenue'] / 1e6:.2f}M"
    else:
        revenue_text = f"${latest['Revenue']:,.0f}"

    print(f"Revenue: {revenue_text}")

    if abs(latest["Net Income"]) >= 1e9:
        income_text = f"${latest['Net Income'] / 1e9:.2f}B"
    elif abs(latest["Net Income"]) >= 1e6:
        income_text = f"${latest['Net Income'] / 1e6:.2f}M"
    else:
        income_text = f"${latest['Net Income']:,.0f}"

    print(f"Net Income: {income_text}")

    if previous is not None:

        print(
            f"Revenue Growth: "
            f"{latest['Revenue Growth %']:.2f}%"
        )

        print(
            f"Net Income Change: "
            f"${latest['Net Income Change'] / 1e6:.2f}M"
        )

    print("=" * 60)


# ============================================================
# CHARTS
# ============================================================

def plot_revenue(df, symbol):

    plt.figure(figsize=(10, 5))

    plt.plot(
        df["Date"],
        df["Revenue"] / 1e9,
        marker="o"
    )

    plt.title(
        f"{symbol} Revenue History"
    )

    plt.ylabel("Revenue ($ Billions)")
    plt.grid(True)

    plt.tight_layout()
    plt.show()


def plot_net_income(df, symbol):

    plt.figure(figsize=(10, 5))

    plt.plot(
        df["Date"],
        df["Net Income"] / 1e9,
        marker="o",
        color="green"
    )

    plt.title(
        f"{symbol} Net Income History"
    )

    plt.ylabel("Net Income ($ Billions)")
    plt.grid(True)

    plt.tight_layout()
    plt.show()


def plot_revenue_vs_income(df, symbol):

    plt.figure(figsize=(10, 5))

    plt.plot(
        df["Date"],
        df["Revenue"] / 1e9,
        marker="o",
        label="Revenue"
    )

    plt.plot(
        df["Date"],
        df["Net Income"] / 1e9,
        marker="o",
        label="Net Income"
    )

    plt.title(
        f"{symbol} Revenue vs Net Income"
    )

    plt.ylabel("$ Billions")

    plt.legend()

    plt.grid(True)

    plt.tight_layout()
    plt.show()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("EQUITY INSIGHT")
    print("=" * 60)

    symbol = input(
        "Enter ticker: "
    ).upper()

    ticker = yf.Ticker(symbol)

    stock_info = get_stock_info(ticker)

    volatility = get_historical_volatility(
        ticker
    )

    sharpe_ratio = get_sharpe_ratio(
        ticker
    )

    income = get_financial_data(
        ticker
    )

    if income is None:

        print(
            "Financial data not available."
        )

        return

    df = build_financial_dataframe(
        income
    )

    print_summary(
        symbol,
        stock_info,
        volatility,
        sharpe_ratio,
        df
    )

    print(df)

    plot_revenue(
        df,
        symbol
    )

    plot_net_income(
        df,
        symbol
    )

    plot_revenue_vs_income(
        df,
        symbol
    )


if __name__ == "__main__":
    main()