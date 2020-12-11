import requests
import typing
import time
import math
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import numpy as np
import scipy
import mibian
from pycoingecko import CoinGeckoAPI

import abi_stuff


query = """{
options(where: {status: "ACTIVE"}, first: 100, skip: page_size) {
symbol
status
strike
amount
expiration
type
account
}
}"""


def _run_query(query):
    request = requests.post(
        "https://api.thegraph.com/subgraphs/name/ppunky/hegic-v888",
        json={"query": query},
    )
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception(
            "Query failed to run by returning code of {}. {}".format(
                request.status_code, query
            )
        )


def loop_over_pages() -> typing.List:
    """
    function for looping over paginated content
    """

    data = []
    page_size = 0
    page = 1

    while True:
        print("page:", page)
        q = query

        q = q.replace("skip: page_size", f"skip: {page_size}")
        try:
            response = _run_query(q)
            try:
                response = response["data"]
            except KeyError as e:
                print(e)
                break
            try:
                sample = response["options"]
                if len(sample) > 0:
                    data.append(pd.DataFrame(sample))
                else:
                    break
            except KeyError as e:
                print(e)
                break
            # increase skip param
            page_size += 100
            page += 1
        except:
            break

    return data


def get_new_data():
    """
    pulls data from subgraph and calculates the BS stuff for all df entries
    """

    global df, underlying_prices, writetoken_totbal

    print("pulling active options...")
    data = loop_over_pages()
    df = pd.concat(data).reset_index(drop=True)
    df["days_to_expiry"] = (df["expiration"] - time.time()) / (60 * 60 * 24)
    cols = ["strike", "amount"]
    df[cols] = df[cols].astype(float)
    df = df[(df["days_to_expiry"] > 0) & (df["strike"] > 0)]

    # compute greeks
    df, underlying_prices, writetoken_totbal = calculate_greeks(df)


def get_new_data_every(period=300):
    """Updates the global variable `df` and the `underlying_prices` dict every 300 seconds"""
    while True:
        get_new_data()
        print("data updated")
        time.sleep(period)


def mibian_bs(row) -> typing.Tuple[float, float, float]:

    formula = mibian.BS(
        [
            row["underlying_price"],
            row["strike"],
            0,
            row["days_to_expiry"],
        ],
        volatility=row["volatility"],
    )

    if row["type"] == "CALL":
        delta = formula.callDelta * row["amount"]
        theta = formula.callTheta * row["amount"]

    elif row["type"] == "PUT":
        delta = formula.putDelta * row["amount"]
        theta = formula.putTheta * row["amount"]

    gamma = formula.gamma * row["amount"]

    s = pd.Series(
        {
            "delta": delta,
            "theta": theta,
            "gamma": gamma,
        }
    )

    return s


def calculate_greeks(
    df: pd.DataFrame,
) -> typing.Tuple[pd.DataFrame, typing.Dict[str, float], typing.Dict[str, float]]:
    """we apply the greeks on each row over the dataframe"""

    # pricing API
    cg = CoinGeckoAPI()

    # lambdas for getting IV and current price of underlying
    f_vol = lambda x: math.sqrt(x.functions.impliedVolRate().call())
    f_pri = lambda x: cg.get_price(ids=x, vs_currencies="usd")[x]["usd"]

    price_wbtc, price_eth = f_pri("bitcoin"), f_pri("ethereum")

    # append constants to df as cols
    df = df.assign(
        underlying_price=np.where(
            df["symbol"] == "WBTC",
            price_wbtc,
            price_eth,
        ),
        volatility=np.where(
            df["symbol"] == "WBTC",
            f_vol(abi_stuff.wbtc_contract),
            f_vol(abi_stuff.eth_contract),
        ),
    )

    df_greeks = df.apply(mibian_bs, axis=1)
    df = pd.concat([df, df_greeks], axis=1)

    underlying_prices = {
        "WBTC": price_wbtc,
        "ETH": price_eth,
    }

    # instead of doing this every time a user interacts with the calculator we do it once
    # and cache until repull of data
    writetoken_totbal = {
        "WBTC": abi_stuff.writewbtc_contract.functions.totalSupply().call(),
        "ETH": abi_stuff.writeeth_contract.functions.totalSupply().call(),
    }

    return df, underlying_prices, writetoken_totbal


def Pnl(price, expiry, delta, gamma, theta) -> float:
    pnl = delta * price + 0.5 * gamma * price ** 2 + theta * expiry
    return pnl


def trigger_calculator(address: str, symbol: str, price: int, day: int) -> pd.DataFrame:
    """
    this is func which will deliver the P&L based on the users inputs
    """

    global df, underlying_prices, writetoken_totbal

    address = abi_stuff.web3.toChecksumAddress(address)

    f = (
        lambda staked_contract, write_contract: staked_contract.functions.balanceOf(
            address
        ).call()
        + write_contract.functions.balanceOf(address).call()
    )

    if symbol == "WBTC":

        writetoken_userbal = f(
            abi_stuff.stakedwbtc_contract, abi_stuff.writewbtc_contract
        )

    elif symbol == "ETH":

        writetoken_userbal = f(
            abi_stuff.stakedeth_contract, abi_stuff.writeeth_contract
        )

    writetoken_usershare = writetoken_userbal / writetoken_totbal[symbol]

    user_greeks = lambda symbol, gr: round(
        df[df["symbol"] == symbol][gr].sum() * -1 * writetoken_usershare, 2
    )
    u_delta, u_gamma, u_theta = (
        user_greeks(symbol, "delta"),
        user_greeks(symbol, "gamma"),
        user_greeks(symbol, "theta"),
    )

    delta = price - underlying_prices[symbol]
    pnl = Pnl(delta, day, u_delta, u_gamma, u_theta)

    data = pd.DataFrame(
        {"coin": [symbol], "price": [price], "day": [day], "pnl": [pnl]}
    )

    return data


################################################
# pull initial data on app start
get_new_data()

# for the data refresh
executor = ThreadPoolExecutor(max_workers=1)
executor.submit(get_new_data_every)

data = pd.read_csv("input.csv")
data = data.to_dict()
address = data.get("address")[0]
symbol = data.get("coin")[0]
price = data.get("price")[0]
day = data.get("day")[0]

# run the calculator
X = trigger_calculator(address, symbol, price, day)
