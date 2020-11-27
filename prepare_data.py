import typing

import pandas as pd
import numpy as np
from pycoingecko import CoinGeckoAPI

from api import _run_query, queries


# launch cg api
cg = CoinGeckoAPI()


def get_projected_profit(df: pd.DataFrame) -> pd.DataFrame:
    """
    calculate project profit for status==ACTIVE
    """

    # for those I need to find a price (use coingecko)
    cg = CoinGeckoAPI()

    time_col = "timestamp_unix"
    currency = "usd"

    prices_btc = cg.get_coin_market_chart_range_by_id(
        id="bitcoin",
        vs_currency=currency,
        from_timestamp=df[df["symbol"] == "WBTC"][time_col].min(),
        to_timestamp=df[df["symbol"] == "WBTC"][time_col].max(),
    )["prices"]

    prices_eth = cg.get_coin_market_chart_range_by_id(
        id="ethereum",
        vs_currency=currency,
        from_timestamp=df[df["symbol"] == "ETH"][time_col].min(),
        to_timestamp=df[df["symbol"] == "ETH"][time_col].max(),
    )["prices"]

    time_col_cg = "timestamp_unix_gc"
    prices_btc = pd.DataFrame(prices_btc, columns=[time_col_cg, "price"])
    prices_btc["symbol"] = "WBTC"

    prices_eth = pd.DataFrame(prices_eth, columns=[time_col_cg, "price"])
    prices_eth["symbol"] = "ETH"

    df_prices = pd.concat([prices_btc, prices_eth]).reset_index(drop=True)

    # from millisecond timestamp to seconds
    df_prices[time_col_cg] //= 1000

    # merge nearest historical prices to option creation timestamp
    df = pd.merge_asof(
        df.sort_values(time_col),
        df_prices.sort_values(time_col_cg),
        left_on=time_col,
        right_on=time_col_cg,
        by="symbol",
        allow_exact_matches=True,
        direction="nearest",
    )

    # to calculate the break even price, I need the totalFee in USD
    # (the total usd costs which where paid)
    df["totalFeeUSD"] = df["totalFee"] * df["price"]
    df["premium_usd"] = df["premium"] * df["price"]

    df["breakeven"] = np.where(
        df["type"] == "CALL",
        df["strike"]
        + (df["totalFeeUSD"] / df["amount"]),  # has to be scaled by amount size
        df["strike"] - (df["totalFeeUSD"] / df["amount"]),
    )

    # get latest prices
    current_price_wbtc = cg.get_price(ids="bitcoin", vs_currencies=currency)["bitcoin"][
        currency
    ]
    current_price_eth = cg.get_price(ids="ethereum", vs_currencies=currency)[
        "ethereum"
    ][currency]
    df["current_price"] = np.where(
        df["symbol"] == "WBTC", current_price_wbtc, current_price_eth
    )

    # The projected profit is only relevant for options with status ACTIVE cause
    # the calculation of it is based on the current price which means that the projected
    # profit for exercised and expired options won't match the actual profit! (but thats ok,
    # as we only need it for ACTIVE anyways)
    # I) OTM: projected_profit is simply -premium
    df["projected_profit"] = np.where(
        (df["type"] == "CALL") & (df["current_price"] < df["strike"]),
        -df["premium"],
        np.nan,
    )

    df["projected_profit"] = np.where(
        (df["type"] == "PUT") & (df["current_price"] > df["strike"]),
        -df["premium"],
        df["projected_profit"],
    )

    # II) ITM
    df["projected_profit"] = np.where(
        (df["type"] == "CALL") & (df["current_price"] >= df["strike"]),
        ((df["current_price"] - df["breakeven"]) * df["amount"]) / df["current_price"],
        df["projected_profit"],
    )

    df["projected_profit"] = np.where(
        (df["type"] == "PUT") & (df["current_price"] <= df["strike"]),
        ((df["breakeven"] - df["current_price"]) * df["amount"]) / df["current_price"],
        df["projected_profit"],
    )

    df["profit"] = np.where(
        df["status"] == "ACTIVE", df["projected_profit"], df["profit"]
    )

    df = df.drop(columns=["projected_profit"])

    # OTM is if the profit is simply the same as the negative premium
    # e.g. premium was 10eth -> if the profit equals -10 then the option is OTM
    # else ITM
    df["group"] = np.where(df["profit"] == -df["premium"], "OTM", "ITM")

    # there are some weird options (probably test cases) with very low/high strike prices
    # e.g. 1usd strike for 10 wbtc put option (ID == WBTC-9). there breakeven price will be
    # negative based on the above calculation so I set the min value to 0
    df["breakeven"] = np.where(df["breakeven"] < 0, 0, df["breakeven"])

    # round for plots
    col_round = ["strike", "breakeven", "totalFee", "premium", "profit"]
    df[col_round] = df[col_round].round(2)

    return df


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
        "group": "Group",
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
    relayoutData: dict,
    id_: int,
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

    if id_ is not None:
        # get ID
        X["id"] = X["id"].str.split("-").apply(lambda x: x[1])
        X = X[X["id"] == str(id_)]

    # this block is for the interactive charting capability
    try:
        expiration_right = relayoutData["xaxis.range[0]"]
        expiration_left = relayoutData["xaxis.range[1]"]
        strike_top = relayoutData["yaxis.range[0]"]
        strike_btm = relayoutData["yaxis.range[1]"]
        X = X[X["expiration"].between(expiration_right, expiration_left)]
        X = X[X["strike"].between(strike_top, strike_btm)]
    except:
        pass

    # now apply the specific stuff to obtain the P&L
    agg = (
        X.groupby(["type", "group"])["profit"]
        .sum()
        .reset_index()
        .sort_values(["type", "group"])
        .reset_index(drop=True)
    )

    if id_ is not None or len(X) == 1 or agg["type"].nunique() == 1:
        agg = pd.concat([agg, agg]).reset_index(drop=True)
        agg.loc[1, "group"] = "P&L"
    else:
        # get total for plots
        z = agg.groupby("type")[["profit"]].sum().reset_index()
        z["group"] = ["P&L", "P&L"]
        z[agg.columns.tolist()]
        agg = pd.concat([agg, z])

    agg["profit"] = np.where(agg["group"] == "P&L", -agg["profit"], agg["profit"])

    return agg


def get_pool_balances() -> pd.DataFrame:
    pool_balance_wbtc = _run_query(queries["poolBalances_latest_WBTC"])
    pool_balance_eth = _run_query(queries["poolBalances_latest_ETH"])

    f = lambda x: pd.DataFrame(x["data"]["poolBalances"]).set_index("symbol")
    balances_eth = f(pool_balance_eth)
    balances_wbtc = f(pool_balance_wbtc)
    balances = pd.concat([balances_eth, balances_wbtc]).astype("float64")
    balances["util_ratio"] = 1 - (
        balances["availableBalance"] / balances["totalBalance"]
    )

    return balances
