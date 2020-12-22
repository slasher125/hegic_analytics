import time
import typing
from concurrent.futures import ThreadPoolExecutor

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from dash_table import DataTable
import numpy as np
import pandas as pd

import api
import prepare_data
import plots


def get_new_data():
    """Updates the global variable 'df' with new data"""
    global df, balances
    df = api.get_data("options_active")

    # the status from the subgraph data will only change if
    # unlock and unlockAll API is called. this is currently done manually!
    # to address this I check for it and set samples with active status
    # but expiration in the past (smaller than timestamp utc now) to EXPIRED
    df = df[df["expiration"] >= pd.Timestamp.utcnow().tz_localize(None)]
    df = prepare_data.get_projected_profit(df)
    balances = prepare_data.get_pool_balances()


def get_historical_oi():
    df_full = pd.read_parquet("df_full.parquet")
    df_oi_hist = prepare_data.prepare_historical_open_interest(df_full)

    return df_oi_hist


def update_expanding_oi():
    global df_oi

    today = pd.to_datetime("today").normalize()
    df["amount_usd"] = df["amount"] * df["current_price"]
    df["date"] = today
    X = df.groupby(["date", "symbol"])[["amount", "amount_usd"]].sum().reset_index()

    dict_oi_expanding[today] = X

    df_oi_expanding = pd.concat(dict_oi_expanding).reset_index(drop=True)
    df_oi = pd.concat([df_oi_hist, df_oi_expanding]).reset_index(drop=True)


def get_new_data_every(period=300):
    """Update the data every 300 seconds"""
    while True:
        get_new_data()
        update_expanding_oi()
        print("data updated")
        time.sleep(period)


def make_layout():
    return html.Div(
        children=[
            html.Div(
                className="row",
                children=[
                    html.Div(
                        className="four columns div-user-controls",
                        children=[
                            html.Div(
                                id="invisible-div-callback-trigger"
                            ),  # needed for the plots in combi with the auto update
                            html.H1("HEGIC OPTIONS ANALYTICS TOOL"),
                            dcc.Markdown(
                                """
                                Interactive charts displaying active ETH/WBTC option amount (bubble size) updated every 5min from [*subgraph*](https://thegraph.com/explorer/subgraph/ppunky/hegic-v888).
                                """
                            ),
                            html.Div(html.H2("SYMBOL")),
                            html.Div(
                                className="div-for-radio",
                                children=[
                                    dcc.RadioItems(
                                        id="symbol",
                                        options=[
                                            {"label": "WBTC", "value": "WBTC"},
                                            {"label": "ETH", "value": "ETH"},
                                        ],
                                        value="WBTC",  # default
                                        labelStyle={"display": "inline-block"},
                                        className="dropdown_selector",
                                    ),
                                ],
                            ),
                            html.Div(html.H2("PERIOD OF HOLDING (IN DAYS)")),
                            html.Div(
                                className="div-for-dropdown",
                                children=[
                                    dcc.Dropdown(
                                        id="period",
                                        options=[
                                            {"label": "1", "value": "1"},
                                            {"label": "7", "value": "7"},
                                            {"label": "14", "value": "14"},
                                            {"label": "21", "value": "21"},
                                            {"label": "28", "value": "28"},
                                        ],
                                        value=["1", "7", "14", "21", "28"],  # default
                                        multi=True,
                                        className="dropdown_selector",
                                    ),
                                ],
                            ),
                            html.Div(html.H2("SELECT OPTION-SIZE BY DECILE")),
                            html.Div(
                                className="div-for-slider",
                                children=[
                                    dcc.RangeSlider(
                                        id="amounts",
                                        min=0,
                                        max=10,
                                        step=None,
                                        marks={
                                            int(i): str(i) for i in np.arange(0, 11, 1)
                                        },
                                        value=[1, 10],
                                        allowCross=False,
                                        className="dropdown_selector",
                                    ),
                                ],
                            ),
                            html.Div(
                                html.P(
                                    "Deciles 0-1 covers the lowest 10% of options, deciles 9-10 the top 10% of options etc."
                                )
                            ),
                            html.Div(html.H2("SEARCH BY OPTION ID or ACCOUNT")),
                            html.Div(
                                className="div-for-input",
                                children=[
                                    dcc.Input(
                                        id="id",
                                        type="text",
                                        placeholder="ID or Account",
                                        className="input_selector",
                                        multiple=False,
                                    )
                                ],
                            ),
                            html.Div(
                                html.P(
                                    "Clear the search box to return to options overview."
                                )
                            ),
                            html.Div(html.H2("GENERAL INFO")),
                            html.Div(
                                className="div-for-dropdown",  # to shorten the distance btw header and text
                                children=[
                                    html.P(
                                        "Click-and-select directly on the plots to filter to a specific date range/cluster of options."
                                    )
                                ],
                            ),
                            html.Div(
                                children=[
                                    dcc.Markdown(
                                        """
                                    > If you'd like to [*support the dev*](https://etherscan.io/address/0xeb3020BEf4A33DaE09E62DDD4308A99FF4312650) with some coffee"""
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="eight columns div-for-charts bg-grey",
                        children=[
                            dbc.Row(
                                dbc.Col(
                                    dcc.Graph(
                                        id="chart2d_bubble",
                                        config={"displayModeBar": False},
                                    ),
                                    xs=12,
                                    xl=12,  # xs is for phones to use the full width of the device, need xl in here as well to make sure the layout for large screens is being kept as defined in the css
                                ),
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="chart2d_pnl_pct_change",
                                            config={"displayModeBar": False},
                                        ),
                                        xs=12,
                                        xl=6,
                                    ),
                                    dbc.Col(
                                        dcc.Graph(
                                            id="chart2d_pnl",
                                            config={"displayModeBar": False},
                                        ),
                                        xs=12,
                                        xl=6,
                                    ),
                                ]
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="chart2d_balance",
                                            config={"displayModeBar": False},
                                        ),
                                        xs=12,
                                        xl=6,
                                    ),
                                    dbc.Col(
                                        dcc.Graph(
                                            id="chart2d_putcall",
                                            config={"displayModeBar": False},
                                        ),
                                        xs=12,
                                        xl=6,
                                    ),
                                ]
                            ),
                            dbc.Row(
                                dbc.Col(
                                    dcc.Graph(
                                        id="chart2d_open_interest",
                                        config={"displayModeBar": False},
                                    )
                                )
                            ),
                        ],
                    ),
                ],
            )
        ]
    )


# Initialise the app
# meta tags will only be applied to XS devices (mobile phones)
app = dash.Dash(
    __name__,
    meta_tags=[
        {
            "name": "viewport",
            "content": "width=device-width, initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0",
        }
    ],
)

# for gunicorn
server = app.server

# get initial data
get_new_data()

# calculate historical OI (we do this once, and then append the current day whos values
# get updated every 5min)
df_oi_hist = get_historical_oi()
dict_oi_expanding = {}
update_expanding_oi()


# # we need to set layout to be a function so that for each new page load
# # the layout is re-created with the current data, otherwise they will see
# # data that was generated when the Dash app was first initialised
app.layout = make_layout


@app.callback(
    Output("chart2d_bubble", "figure"),
    [
        Input("symbol", "value"),
        Input("period", "value"),
        Input("amounts", "value"),
        Input("id", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_bubble(
    symbol: str,
    period: str,
    amounts: typing.List[int],
    id_: str,
    _,
):

    global df
    X = df.copy()

    X, bubble_size, current_price, current_iv = prepare_data.prepare_bubble(
        X, symbol, period, amounts
    )

    if id_ is not None and len(id_) > 0:
        if len(id_) >= 40:
            X = X[X["Account"].str.lower() == id_.lower()]
        else:
            X = X[X["Option ID"] == id_]

    fig = plots.plot_bubble(
        X=X,
        bubble_size=bubble_size,
        current_price=current_price,
        current_iv=current_iv,
        symbol=symbol,
    )

    return fig


@app.callback(
    Output("chart2d_pnl", "figure"),
    [
        Input("chart2d_bubble", "relayoutData"),
        Input("symbol", "value"),
        Input("period", "value"),
        Input("amounts", "value"),
        Input("id", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_pnl(
    relayoutData: dict,
    symbol: str,
    period: str,
    amounts: typing.List[int],
    id_: str,
    _,
):

    global df, balances
    X = df.copy()

    agg = prepare_data.prepare_pnl(X, symbol, period, amounts, relayoutData, id_)

    fig = plots.plot_pnl(agg=agg, balances=balances, symbol=symbol)

    return fig


@app.callback(
    Output("chart2d_balance", "figure"),
    [
        Input("symbol", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_balance(
    symbol: str,
    _,
):

    global balances

    fig = plots.plot_pool_balance(balances, symbol)

    return fig


@app.callback(
    Output("chart2d_putcall", "figure"),
    [
        Input("symbol", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_putcall(
    symbol: str,
    _,
):

    global df

    fig = plots.plot_put_call_ratio(df, symbol)

    return fig


@app.callback(
    Output("chart2d_pnl_pct_change", "figure"),
    [
        Input("chart2d_bubble", "relayoutData"),
        Input("symbol", "value"),
        Input("period", "value"),
        Input("amounts", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_pnl_pct_change(
    relayoutData: dict,
    symbol: str,
    period: str,
    amounts: typing.List[int],
    _,
):

    global df, balances

    X, current_price = prepare_data.prepare_pnl_pct_changes(
        df,
        balances,
        relayoutData,
        symbol,
        period,
        amounts,
    )
    fig = plots.plot_pnl_pct_change(X, current_price)

    return fig


@app.callback(
    Output("chart2d_open_interest", "figure"),
    [
        Input("symbol", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_open_interest(
    symbol: str,
    _,
):

    """
    given that this is static its better to calcuate this with every n-th update once
    instead of on every user interaction
    """
    global df_oi

    fig = plots.plot_open_interest(df_oi, symbol)

    return fig


# for the data refresh
executor = ThreadPoolExecutor(max_workers=1)
executor.submit(get_new_data_every)

# Run the app
if __name__ == "__main__":
    app.run_server()
