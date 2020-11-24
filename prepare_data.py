import typing

import pandas as pd
import numpy as np
from pycoingecko import CoinGeckoAPI


# launch cg api
cg = CoinGeckoAPI()


def prepare_bubble(
    X: pd.DataFrame,
    symbol: str,
    period: typing.List[str],
    status: typing.List[str],
    amounts: typing.List[float],
) -> typing.Tuple[pd.DataFrame, int, float, int]:
    """
    main function to prepare data for bubble chart
    """

    if symbol == "WBTC":
        symbol_cg = "bitcoin"
    elif symbol == "ETH":
        symbol_cg = "ethereum"

    current_price = cg.get_price(ids=symbol_cg, vs_currencies="usd")[symbol_cg]["usd"]

    # scale the decile amounts to proper deciles e.g. from 5 -> 0.5
    # so that it can be used with the quantile func
    amounts = [i / 10 for i in amounts]

    X = X.sort_values("type")
    X = X[X["symbol"] == symbol]
    # price will stay the same for the below sections! (but must be after the symbol selector)
    current_iv = int(X.loc[X["timestamp_unix"].idxmax()]["impliedVolatility"])
    X = X[X["period_days"].isin(period)]
    X = X[X["status"].isin(status)]
    lb, ub = X["amount"].quantile(amounts[0]), X["amount"].quantile(amounts[1])
    X = X[X["amount"].between(lb, ub)]

    # get ID
    X["id_nb"] = X["id"].str.split("-").apply(lambda x: x[1])

    # rename columms for plotting
    col_mapping = {
        "account": "Account",
        "id_nb": "Option ID",
        "amount": "Option Size",
        "exercise_timestamp": "Exercise Timestamp",
        "exercise_tx": "Exercise tx",
        "expiration": "Expires On",
        "period_days": "Period of Holding",
        "settlementFee": "Settlement Fee",
        "status": "Status",
        "strike": "Strike Price",
        "breakeven": "Break-even price",
        "symbol": "Symbol",
        "timestamp": "Placed At",
        "totalFee": "Total Fee",
        "type": "Option Type",
        "premium": "Premium",
        "profit": "Profit",
    }
    X = X.rename(columns=col_mapping)

    # create duplicated colum for hover color (legend) arg
    # `Option Type` is used for hover info only
    X["Click to select"] = X["Option Type"]

    # we scale the bubble size based on to selected decile amount (currently hardoced)
    # min 10 (for min option size value), max 100 (for max option size value)
    bubble_size_min = 10
    bubble_size_max = 100
    f = lambda q: bubble_size_min + q * 40 if q <= 0.9 else bubble_size_max

    bubble_size = f(amounts[1])

    return X, bubble_size, current_price, current_iv


def prepare_pnl(
    X: pd.DataFrame,
    symbol: str,
    period: str,
    status: typing.List[str],
    amounts: typing.List[int],
) -> pd.DataFrame:
    """
    main function to prepare data for P%L chart
    """

    # scale the decile amounts to proper deciles e.g. from 5 -> 0.5
    # so that it can be used with the quantile func
    amounts = [i / 10 for i in amounts]

    X = X[X["symbol"] == symbol]
    X = X[X["period_days"].isin(period)]
    X = X[X["status"].isin(status)]
    lb, ub = X["amount"].quantile(amounts[0]), X["amount"].quantile(amounts[1])
    X = X[X["amount"].between(lb, ub)]

    # now apply the specific stuff to obtain the P&L
    agg = (
        X.groupby(["type", "pos"])["profit"]
        .sum()
        .reset_index()
        .sort_values(["type", "pos"])
        .reset_index(drop=True)
    )

    # get total for plots
    z = agg.groupby("type")[["profit"]].sum().reset_index()
    z["pos"] = ["P&L", "P&L"]
    z[agg.columns.tolist()]
    agg = pd.concat([agg, z])

    agg["profit"] = np.where(agg["pos"] == "P&L", -agg["profit"], agg["profit"])

    return agg


def get_projected_profit(df: pd.DataFrame) -> pd.DataFrame:
    """
    calculate project profit for status==ACTIVE
    """

    X = df.copy()
    X = X[X["status"] == "ACTIVE"]

    wbtc = X[X["symbol"] == "WBTC"]
    eth = X[X["symbol"] == "ETH"]

    # for those I need to find a price (use coingecko)
    cg = CoinGeckoAPI()

    prices_btc = cg.get_coin_market_chart_range_by_id(
        id="bitcoin",
        vs_currency="usd",
        from_timestamp=wbtc["timestamp_unix"].min(),
        to_timestamp=wbtc["timestamp_unix"].max(),
    )["prices"]

    prices_eth = cg.get_coin_market_chart_range_by_id(
        id="ethereum",
        vs_currency="usd",
        from_timestamp=eth["timestamp_unix"].min(),
        to_timestamp=eth["timestamp_unix"].max(),
    )["prices"]

    prices_btc = pd.DataFrame(prices_btc, columns=["timestamp_unix_gc", "price"])
    prices_btc["symbol"] = "WBTC"

    prices_eth = pd.DataFrame(prices_eth, columns=["timestamp_unix_gc", "price"])
    prices_eth["symbol"] = "ETH"

    df_prices = pd.concat([prices_btc, prices_eth]).reset_index(drop=True)

    # correct to secods
    df_prices["timestamp_unix_gc"] = df_prices["timestamp_unix_gc"] // 1000

    X = pd.merge_asof(
        X.sort_values("timestamp_unix"),
        df_prices.sort_values("timestamp_unix_gc"),
        left_on="timestamp_unix",
        right_on="timestamp_unix_gc",
        by="symbol",
        allow_exact_matches=True,
        direction="nearest",
    )

    # to calculate the break even price, I need the totalFee in USD (the total usd costs which where paid)
    # TODO(!) make sure that this is correct, I acutally might need to use the current_price here instead
    X["totalFeeUSD"] = X["totalFee"] * X["price"]
    X["premium_usd"] = X["premium"] * X["price"]

    # has to be different by put and call (for call its + for put its -)
    X["breakeven"] = np.where(
        X["type"] == "CALL",
        X["strike"]
        + (X["totalFeeUSD"] / X["amount"]),  # has to be scaled by amount size
        X["strike"] - (X["totalFeeUSD"] / X["amount"]),
    )

    # OTM
    current_price_wbtc = cg.get_price(ids="bitcoin", vs_currencies="usd")["bitcoin"][
        "usd"
    ]
    current_price_eth = cg.get_price(ids="ethereum", vs_currencies="usd")["ethereum"][
        "usd"
    ]
    X["current_price"] = np.where(
        X["symbol"] == "WBTC", current_price_wbtc, current_price_eth
    )

    # I) OTM: projected_profit is simply -premium
    X["projected_profit"] = np.where(
        (X["type"] == "CALL") & (X["current_price"] < X["strike"]),
        -X["premium"],
        np.nan,
    )

    X["projected_profit"] = np.where(
        (X["type"] == "PUT") & (X["current_price"] > X["strike"]),
        -X["premium"],
        X["projected_profit"],
    )

    # II) ITM
    X["projected_profit"] = np.where(
        (X["type"] == "CALL") & (X["current_price"] >= X["strike"]),
        ((X["current_price"] - X["breakeven"]) * X["amount"]) / X["current_price"],
        X["projected_profit"],
    )

    X["projected_profit"] = np.where(
        (X["type"] == "PUT") & (X["current_price"] <= X["strike"]),
        ((X["breakeven"] - X["current_price"]) * X["amount"]) / X["current_price"],
        X["projected_profit"],
    )

    # merge this stuff onto df
    df = df.merge(X[["id", "projected_profit", "breakeven"]], how="left", on="id")
    df["profit"] = np.where(
        df["status"] == "ACTIVE", df["projected_profit"], df["profit"]
    )

    df = df.drop(columns=["projected_profit"])

    df["pos"] = np.where(df["profit"] >= 0, "ITM", "OTM")

    col_round = ["strike", "breakeven"]
    df[col_round] = df[col_round].round(2)

    return df
