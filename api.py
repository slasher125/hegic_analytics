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


def get_data(content: str) -> pd.DataFrame:
    """
    pulls data from the subgraph and transforms into pandas.DataFrame.
    Applies some datatype changes.
    `content` must be one of the following: 'options', 'poolBalances', 'bondingcurve'
    """

    if content in ["options", "poolBalances"]:
        data = []
        for i in ["eth", "wbtc"]:
            result = _run_query(queries[f"{content}_{i}"])
            proposal = result["data"][content]
            df_ = pd.DataFrame(data=proposal)
            data.append(df_)
        df = pd.concat(data)

        if content == "options":
            cols = [
                "amount",
                "lockedAmount",
                "premium",
                "settlementFee",
                "strike",
                "totalFee",
                "profit",
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

        if content == "poolBalances":
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
        result = _run_query(queries[content])
        proposal = result["data"]["bondingCurveEvents"]
        df = pd.DataFrame(data=proposal)

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        cols = ["bondingCurveSoldAmount", "ethAmount", "tokenAmount"]
        df[cols] = df[cols].astype("float64")

    return df


queries = {
    "options_eth": """{
        options(first: 1000, where: {symbol: "ETH"}) {
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
        }
        }""",
    "options_wbtc": """{ 
        options(first: 1000, where: {symbol: "WBTC"}) {
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
        }
        }""",
    "poolBalances_eth": """{ 
        poolBalances(first: 1000, where: {symbol: "ETH"}) {
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
    "poolBalances_wbtc": """{ 
        poolBalances(first: 1000, where: {symbol: "WBTC"}) {
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
    "bondingcurve": """{ 
        bondingCurveEvents(first: 1000) {
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
