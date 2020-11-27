from typing import List

import requests
import pandas as pd


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


def loop_over_pages(content: str) -> List:

    data = []
    page_size = 0
    page = 1

    while True:
        print("page:", page)
        q = queries[content]

        q = q.replace("skip: page_size", f"skip: {page_size}")
        try:
            response = _run_query(q)
            try:
                response = response["data"]
            except KeyError as e:
                print(e)
                break
            try:
                sample = response[content]
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


def get_data(content: str) -> pd.DataFrame:

    print(f"pulling '{content}'-data")
    data = loop_over_pages(content)
    df = pd.concat(data).reset_index(drop=True)

    # keep the unix timestamp
    df["timestamp_unix"] = df["timestamp"]

    if content == "options":
        cols = [
            "amount",
            "lockedAmount",
            "premium",
            "settlementFee",
            "strike",
            "totalFee",
            "profit",
            "impliedVolatility",
        ]
        df[cols] = df[cols].astype("float64")

        for col in ["expiration", "timestamp", "exercise_timestamp"]:
            df[col] = pd.to_datetime(df[col], unit="s")

        # map the period column (in seconds) to integer
        duration_mapping = {
            86400: 1,
            604800: 7,
            1209600: 14,
            1814400: 21,
            2419200: 28,
        }
        df["period_days"] = df["period"].map(duration_mapping)
        df["block"] = df["block"].astype(int)

    elif content == "poolBalances":
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        cols = [
            "amount",
            "availableBalance",
            "currentRatio",
            "tokens",
            "totalBalance",
        ]
        df[cols] = df[cols].astype("float64")

    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        cols = ["bondingCurveSoldAmount", "ethAmount", "tokenAmount"]
        df[cols] = df[cols].astype("float64")

    return df


queries = {
    "options": """{
        options(first: 100, skip: page_size, orderBy: timestamp, orderDirection: asc) {
        id
        account
        symbol
        status
        strike
        amount
        lockedAmount
        timestamp
        period
        expiration
        type
        premium
        settlementFee
        totalFee
        exercise_timestamp
        exercise_tx
        profit
        impliedVolatility
        block
        }
        }""",
    "poolBalances": """{ 
        poolBalances(first: 100, skip: page_size, orderBy: timestamp, orderDirection: asc) {
        id
        timestamp
        account
        symbol
        type
        amount
        tokens
        availableBalance
        totalBalance
        currentRatio
        }
        }""",
    "poolBalances_latest_WBTC": """{ 
        poolBalances(where: {symbol: "WBTC", type: "PROVIDE"}, first: 1, orderBy: timestamp, orderDirection: desc) {
        symbol
        availableBalance
        totalBalance
        }
        }""",
    "poolBalances_latest_ETH": """{ 
        poolBalances(where: {symbol: "ETH", type: "PROVIDE"}, first: 1, orderBy: timestamp, orderDirection: desc) {
        symbol
        availableBalance
        totalBalance
        }
        }""",
    "bondingCurveEvents": """{ 
        bondingCurveEvents(first: 100, skip: page_size, orderBy: timestamp, orderDirection: asc) {
        id
        timestamp
        account
        type
        tokenAmount
        ethAmount
        bondingCurveSoldAmount
        }
        }""",
}
