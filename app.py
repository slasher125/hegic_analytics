import time
import typing
from concurrent.futures import ThreadPoolExecutor

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import numpy as np
import pandas as pd
from pycoingecko import CoinGeckoAPI

import api
import prepare_data
import plots


# I deliberatitly use integers here instead of float to the get the
# correct axis labels for the decile slider
deciles = {int(i): str(i) for i in np.arange(0, 11, 1)}


def get_new_data():
    """Updates the global variable 'df' with new data"""
    global df
    df = api.get_data("options")

    # the status from the subgraph data will only change if
    # unlock and unlockAll API is called. this is currently done manually!
    # to address this I check for it and set samples with active status
    # but expiration in the past (smaller than timestamp utc now) to EXPIRED
    df = df.assign(
        status=np.where(
            (df["status"] == "ACTIVE")
            & (df["expiration"] < pd.Timestamp.utcnow().tz_localize(None)),
            "EXPIRED",
            df["status"],
        )
    )


def get_new_data_every(period=300):
    """Update the data every 300 seconds"""
    while True:
        get_new_data()
        print(df["timestamp"].max())
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
                                Interactive charts for ETH/WBTC option amount (bubble size) updated every 5min from [*subgraph*](https://thegraph.com/explorer/subgraph/ppunky/hegic-v888).
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
                            html.Div(html.H2("STATUS")),
                            html.Div(
                                className="div-for-dropdown",
                                children=[
                                    dcc.Dropdown(
                                        id="status",
                                        options=[
                                            {"label": "ACTIVE", "value": "ACTIVE"},
                                            {"label": "EXPIRED", "value": "EXPIRED"},
                                            {
                                                "label": "EXERCISED",
                                                "value": "EXERCISED",
                                            },
                                        ],
                                        value=["ACTIVE"],  # default
                                        multi=True,
                                        placeholder="Select status",
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
                                        placeholder="Select periods",
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
                                        marks=deciles,
                                        value=[0, 10],
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
                            html.Div(html.H2("GENERAL INFO")),
                            html.Div(
                                className="div-for-dropdown",  # to shortedn the distance btw header and text
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
                                    > *If you'd like to support the dev with some coffee* 0xeb3020BEf4A33DaE09E62DDD4308A99FF4312650 (eth)
                                    """
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="eight columns div-for-charts bg-grey",
                        children=[
                            dcc.Graph(
                                id="chart2d_bubble",
                                config={"displayModeBar": False},
                            ),
                            # add two emtpy H1's to get some space between the plots
                            html.Div(html.H1("")),
                            dcc.Graph(
                                id="chart2d_pnl",
                                config={"displayModeBar": False},
                            ),
                        ],
                    ),
                ],
            )
        ]
    )


# Initialise the app
app = dash.Dash(__name__)

# for gunicorn
server = app.server

# get initial data
get_new_data()

# # we need to set layout to be a function so that for each new page load
# # the layout is re-created with the current data, otherwise they will see
# # data that was generated when the Dash app was first initialised
app.layout = make_layout


@app.callback(
    Output("chart2d_bubble", "figure"),
    [
        Input("symbol", "value"),
        Input("period", "value"),
        Input("status", "value"),
        Input("amounts", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_bubble(
    symbol: str,
    period: str,
    status: str,
    amounts: typing.List[int],
    _,
):

    global df
    X = df.copy()

    X, bubble_size, current_price = prepare_data.prepare_bubble(
        X, symbol, period, status, amounts
    )
    fig = plots.plot_bubble(
        X=X, title=symbol, bubble_size=bubble_size, current_price=current_price
    )

    return fig


@app.callback(
    Output("chart2d_pnl", "figure"),
    [
        Input("symbol", "value"),
        Input("period", "value"),
        Input("amounts", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_pnl(symbol: str, period: str, amounts: typing.List[int], _):

    global df
    X = df.copy()

    agg = prepare_data.prepare_pnl(X, symbol, period, amounts)

    fig = plots.plot_pnl(agg=agg, symbol=symbol)

    return fig


# for the data refresh
executor = ThreadPoolExecutor(max_workers=1)
executor.submit(get_new_data_every)

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
