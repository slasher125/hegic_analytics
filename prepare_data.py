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
) -> typing.Tuple[pd.DataFrame, int, float]:
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
    X = X[X["period_days"].isin(period)]
    X = X[X["status"].isin(status)]

    # the status from the subgraph data will only change if
    # unlock and unlockAll API is called. this is currently done manually!
    # in order to get around this I keep only samples whoes
    # expiration date is in the future
    if "ACTIVE" in status:
        X = X[X["expiration"] > pd.Timestamp.utcnow().tz_localize(None)]

    lb, ub = X["amount"].quantile(amounts[0]), X["amount"].quantile(amounts[1])
    X = X[X["amount"].between(lb, ub)]

    # get ID
    X["id_nb"] = X["id"].str.split("-").apply(lambda x: x[1])

    # in case of no realised profit, set to nan
    X["profit"] = X["profit"].fillna("NaN")

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

    return X, bubble_size, current_price


def prepare_pnl(
    X: pd.DataFrame, symbol: str, period: str, amounts: typing.List[int]
) -> pd.DataFrame:
    """
    main function to prepare data for P%L chart
    """

    # scale the decile amounts to proper deciles e.g. from 5 -> 0.5
    # so that it can be used with the quantile func
    amounts = [i / 10 for i in amounts]

    X = X[X["symbol"] == symbol]
    X = X[X["period_days"].isin(period)]

    lb, ub = X["amount"].quantile(amounts[0]), X["amount"].quantile(amounts[1])
    X = X[X["amount"].between(lb, ub)]

    # NOTE(!) currently do this only for active
    X = X[X["status"] == "ACTIVE"]

    if symbol == "WBTC":
        symbol_cg = "bitcoin"
    elif symbol == "ETH":
        symbol_cg = "ethereum"

    # for those I need to find a price (use coingecko)
    cg = CoinGeckoAPI()

    price_history = cg.get_coin_market_chart_range_by_id(
        id=symbol_cg,
        vs_currency="usd",
        from_timestamp=X["timestamp_unix"].min(),
        to_timestamp=X["timestamp_unix"].max(),
    )["prices"]

    df_prices = pd.DataFrame(price_history, columns=["timestamp_unix_gc", "price"])

    # correct to secods
    df_prices["timestamp_unix_gc"] = df_prices["timestamp_unix_gc"] // 1000

    X = pd.merge_asof(
        X.sort_values("timestamp_unix"),
        df_prices.sort_values("timestamp_unix_gc"),
        left_on="timestamp_unix",
        right_on="timestamp_unix_gc",
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
    current_price = cg.get_price(ids=symbol_cg, vs_currencies="usd")[symbol_cg]["usd"]
    X["current_price"] = current_price

    # first separate into calls and puts
    call = X[X["type"] == "CALL"]
    put = X[X["type"] == "PUT"]

    cols_to_agg = ["premium", "premium_usd"]
    # I) OTM
    call_otm = call[call["current_price"] < call["strike"]]
    put_otm = put[put["current_price"] > put["strike"]]

    col_mapping = {"premium": "profit", "premium_usd": "profit_usd"}
    profit_call_otm = (
        call_otm.groupby("type")[cols_to_agg].sum().rename(columns=col_mapping)
    )
    profit_put_otm = (
        put_otm.groupby("type")[cols_to_agg].sum().rename(columns=col_mapping)
    )
    profit_call_otm["pos"] = "OTM"
    profit_put_otm["pos"] = "OTM"

    # II) ITM
    call_itm = call[call["current_price"] >= call["strike"]]
    put_itm = put[put["current_price"] <= put["strike"]]

    call_itm = call_itm.assign(
        profit=call_itm["premium_usd"]
        + (call_itm["current_price"] - call_itm["breakeven"]) * call_itm["amount"],
    )
    put_itm = put_itm.assign(
        profit=put_itm["premium_usd"]
        + (put_itm["breakeven"] - put_itm["current_price"]) * put_itm["amount"],
    )

    # also get the profit in btc/eth units not just USD
    profit_call_itm = call_itm.groupby("type")["profit"].sum().to_frame("profit_usd")
    profit_call_itm["profit"] = profit_call_itm["profit_usd"] / current_price

    profit_put_itm = put_itm.groupby("type")["profit"].sum().to_frame("profit_usd")
    profit_put_itm["profit"] = profit_put_itm["profit_usd"] / current_price

    profit_call_itm["pos"] = "ITM"
    profit_put_itm["pos"] = "ITM"

    col_order = ["pos", "profit", "profit_usd"]

    agg = (
        pd.concat(
            [
                profit_put_otm[col_order],
                profit_call_otm[col_order],
                profit_put_itm[col_order],
                profit_call_itm[col_order],
            ]
        )
        .reset_index()
        .sort_values(["type", "pos"])
        .reset_index(drop=True)
    )

    for col in ["profit", "profit_usd"]:
        agg[col] = np.where(agg["pos"] == "ITM", -agg[col], agg[col])

    # get total for plots
    z = agg.groupby("type")[["profit", "profit_usd"]].sum().reset_index()
    z["pos"] = ["TOTAL", "TOTAL"]
    z[agg.columns.tolist()]
    agg = pd.concat([agg, z])

    return agg
