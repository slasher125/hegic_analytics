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

    # there are some weird options (probably test cases) with very low/high strike prices
    # e.g. 1usd strike for 10 df_ put option (ID == WBTC-9). there breakeven price will be
    # negative based on the above calculation so I set the min value to 0
    df["breakeven"] = np.where(df["breakeven"] < 0, 0, df["breakeven"])

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

    # NOTE(!)have to think about this, but I think overall its better the way it is not using this!
    # in some isolated cases (usually with large options) small differences in the calculated
    # break even price and the actual break even might be large enough to lead to some illogical
    # values for the projected profit.
    # I apply a filter on top, to make sure we don't see anything weird.
    # A profit can never be smaller than -premium (no matter what scenario)
    df["profit"] = np.where(df["profit"] < -df["premium"], -df["premium"], df["profit"])

    # OTM is if the profit is simply the same as the negative premium
    # e.g. premium was 10eth -> if the profit equals -10 then the option is OTM
    # else ITM
    df["group"] = np.where(df["profit"] == -df["premium"], "OTM", "ITM")

    ################################### this section is for calculating offsets on the current price
    # to get an overview of how the pools P&L ranges with changes pct-changes (+/- 0-20 pct) in the spot price
    # the below values will be bonkers for no longer active options, so set them to Nan later on
    # we only need this for active stuff
    for i in np.arange(0, 0.26, 0.01):
        i = round(i, 2)

        # if price increases (this will be good for the calls and bad for the puts)
        df[f"current_price_plus_{i}pct"] = df["current_price"] + df["current_price"] * i
        # if price decreases (will be bad for calls and good for puts)
        df[f"current_price_minus_{i}pct"] = (
            df["current_price"] - df["current_price"] * i
        )

        # OTM
        df[f"projected_profit_plus_{i}pct"] = np.where(
            (df["type"] == "CALL") & (df[f"current_price_plus_{i}pct"] < df["strike"]),
            -df["premium"],
            np.nan,
        )

        df[f"projected_profit_plus_{i}pct"] = np.where(
            (df["type"] == "PUT") & (df[f"current_price_plus_{i}pct"] > df["strike"]),
            -df["premium"],
            df[f"projected_profit_plus_{i}pct"],
        )

        df[f"projected_profit_minus_{i}pct"] = np.where(
            (df["type"] == "CALL") & (df[f"current_price_minus_{i}pct"] < df["strike"]),
            -df["premium"],
            np.nan,
        )

        df[f"projected_profit_minus_{i}pct"] = np.where(
            (df["type"] == "PUT") & (df[f"current_price_minus_{i}pct"] > df["strike"]),
            -df["premium"],
            df[f"projected_profit_minus_{i}pct"],
        )

        # II) ITM
        df[f"projected_profit_plus_{i}pct"] = np.where(
            (df["type"] == "CALL") & (df[f"current_price_plus_{i}pct"] >= df["strike"]),
            ((df[f"current_price_plus_{i}pct"] - df["breakeven"]) * df["amount"])
            / df[f"current_price_plus_{i}pct"],
            df[f"projected_profit_plus_{i}pct"],
        )

        df[f"projected_profit_plus_{i}pct"] = np.where(
            (df["type"] == "PUT") & (df[f"current_price_plus_{i}pct"] <= df["strike"]),
            ((df["breakeven"] - df[f"current_price_plus_{i}pct"]) * df["amount"])
            / df[f"current_price_plus_{i}pct"],
            df[f"projected_profit_plus_{i}pct"],
        )

        df[f"projected_profit_minus_{i}pct"] = np.where(
            (df["type"] == "CALL")
            & (df[f"current_price_minus_{i}pct"] >= df["strike"]),
            ((df[f"current_price_minus_{i}pct"] - df["breakeven"]) * df["amount"])
            / df[f"current_price_minus_{i}pct"],
            df[f"projected_profit_minus_{i}pct"],
        )

        df[f"projected_profit_minus_{i}pct"] = np.where(
            (df["type"] == "PUT") & (df[f"current_price_minus_{i}pct"] <= df["strike"]),
            ((df["breakeven"] - df[f"current_price_minus_{i}pct"]) * df["amount"])
            / df[f"current_price_minus_{i}pct"],
            df[f"projected_profit_minus_{i}pct"],
        )

    # set the values to Nan if status no ACTIVE
    cols = df.columns[df.columns.str.contains("projected_profit")]
    for i in cols:
        df[i] = np.where(df["status"] != "ACTIVE", np.nan, df[i])

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
    id_: str,
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

    if id_ is not None and len(id_) > 0:
        # first check if this ID is even in the select symbol set
        if len(id_) >= 40:
            # filter to unique account address (can have [0, inf) rows)
            X = X[X["account"].str.lower() == id_.lower()]
        else:
            # fitler to unique option ID (results in 1 row!)
            X["id"] = X["id"].str.split("-").apply(lambda x: x[1])
            X = X[X["id"] == id_]

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

    # get total for plots
    z = agg.groupby("type")[["profit"]].sum().reset_index()
    z["group"] = ["P&L"] * len(z)
    z = z[agg.columns.tolist()]
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


def prepare_pnl_pct_changes(
    df: pd.DataFrame,
    balances: pd.DataFrame,
    relayoutData: dict,
    symbol: str,
    period: str,
    amounts: typing.List[int],
) -> pd.DataFrame:
    """
    code for aggregating data to plot P&L for different pct changes in spot price
    """

    if symbol == "WBTC":
        symbol_cg = "bitcoin"
    elif symbol == "ETH":
        symbol_cg = "ethereum"

    current_price = cg.get_price(ids=symbol_cg, vs_currencies="usd")[symbol_cg]["usd"]

    X = df.copy()

    # scale the decile amounts to proper deciles e.g. from 5 -> 0.5
    # so that it can be used with the quantile func
    amounts = [i / 10 for i in amounts]

    X = X[X["symbol"] == symbol]
    X = X[X["period_days"].isin(period)]
    lb, ub = X["amount"].quantile(amounts[0]), X["amount"].quantile(amounts[1])
    X = X[X["amount"].between(lb, ub)]

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

    # get the p&l's
    cols = X.columns[X.columns.str.contains("projected_profit")]
    x = X[cols].sum(axis=0)

    # need to revert the sign to get the pnl for pool !
    x = -x

    # next need the current balance
    x = (x / balances.loc[symbol]["totalBalance"]) * 100
    x = x.to_frame("pnl").reset_index()
    x["pct"] = (
        x["index"].str.split("_").apply(lambda x: x[-1]).str.strip("pct").astype(float)
    )
    x["sign"] = x["index"].str.split("_").apply(lambda x: x[-2])

    x = x.assign(pct=np.where(x["sign"] == "plus", x["pct"], -x["pct"]))

    z = (
        X[X.columns[X.columns.str.contains("current_price_")]]
        .apply(lambda x: x.unique())
        .T.round(2)
    )
    z = z.rename(columns={0: "projected_price"}).reset_index(drop=True)
    x = pd.concat([x, z], axis=1)

    return x, current_price


def prepare_leaderboard(
    df: pd.DataFrame, symbol: str
) -> typing.Tuple[pd.DataFrame, typing.List[str]]:

    X = df.copy()
    X = X[X["status"] == "ACTIVE"]
    X = X[X["symbol"] == symbol]
    X = X.sort_values(["amount", "profit"], ascending=False).reset_index(drop=True)
    X["id"] = X["id"].str.split("-").apply(lambda x: x[1]).astype(int)
    X = X[["amount", "profit", "id", "account"]]

    X = X.round(2)
    X = X.rename(
        columns={
            "amount": "Option Size",
            "profit": f"Profit in {symbol}",
            "id": "Option ID",
            "account": "Account",
        }
    )

    columns = [{"name": i, "id": i} for i in X.columns]

    return X, columns


def prepare_open_interest(df: pd.DataFrame, symbol: str) -> pd.DataFrame:

    df_ = df[df["symbol"] == symbol]
    df_ = df_.assign(amount_usd=df["amount"] * df["price"])

    days = pd.date_range(
        df_["timestamp"].dt.normalize().min() + pd.offsets.Day(1),
        df_["timestamp"].dt.normalize().max(),
    )

    data = {}
    for d in days:
        # first we keep only samples up to that day
        X = df_[df_["timestamp"] <= d]
        # remove everything which is already expired
        X = X[X["expiration"] >= d]
        # remove exercised
        X = X[(X["exercise_timestamp"].isna()) | (X["exercise_timestamp"] > d)]
        # calculate sum
        data[d] = X[["amount", "amount_usd"]].sum()

    data = pd.DataFrame(data).T
    data = data.reset_index().rename(columns={"index": "date"})

    return data
