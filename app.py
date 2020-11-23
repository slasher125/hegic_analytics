import time
from typing import List
from concurrent.futures import ThreadPoolExecutor

import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import numpy as np
from pycoingecko import CoinGeckoAPI

import api


# I deliberatitly use integers here instead of float to the get the
# correct axis labels for the decile slider
deciles = {int(i): str(i) for i in np.arange(0, 11, 1)}


def get_new_data():
    """Updates the global variable 'df' with new data"""
    global df
    df = api.get_data("options")


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
                            html.Div(id="invisible-div-callback-trigger"),
                            html.H1("HEGIC OPTIONS ANALYTICS TOOL"),
                            dcc.Markdown(
                                """
                                Interactive charts for ETH/WBTC option amount (bubble size) updated every 5min from [*subgraph*](https://thegraph.com/explorer/subgraph/ppunky/hegic-v888).
                                """
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
                                    > *If you'd like to support the dev with some coffee* 0xeb3020BEf4A33DaE09E62DDD4308A99FF4312650
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
                                id="chart_2d_eth",
                                config={"displayModeBar": False},
                            ),
                            # add two emtpy H1's to get some space between the plots
                            html.Div(html.H1("")),
                            dcc.Graph(
                                id="chart_2d_wbtc",
                                config={"displayModeBar": False},
                            ),
                        ],
                    ),
                ],
            )
        ]
    )


# launch cg api
cg = CoinGeckoAPI()

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


def slice_for_plotting(
    X: pd.DataFrame,
    symbol: str,
    period: str,
    status: str,
    amounts: List[float],
):

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


def plot(X: pd.DataFrame, title: str, bubble_size: int, current_price: float):

    fig = px.scatter(
        X,
        x="Expires On",
        y="Strike Price",
        size="Option Size",
        size_max=bubble_size,
        color="Click to select",
        title=f"{title} - Max Option-Size Value: {X['Option Size'].max()}",
        hover_name="Account",
        hover_data={
            "Option Type": True,
            "Option ID": True,
            "Placed At": "|%b %d, %Y, %H:%M",  # same format as `Expires On` e.g. Dec 7, 2020, 12:02
            "Period of Holding": True,
            "Premium": True,
            "Settlement Fee": True,
            "Total Fee": True,
            "Profit": True,
            "Click to select": False,
        },
        color_discrete_sequence=["#45fff4", "#f76eb2"],  # hegic colors
        template="plotly_dark",
    )

    fig.update_layout(
        {
            "plot_bgcolor": "rgba(0, 0, 0, 0)",
            "paper_bgcolor": "rgba(0, 0, 0, 0)",
        },  # this removes the native plotly background
        font_family="Exo 2",
        font_color="#defefe",
        font_size=15,
        legend={  # adjust the location of the legend
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )

    # move xaxis name closer to plot
    fig.update_xaxes(title_standoff=0)

    fig.add_hline(
        y=current_price,
        line_color="#ffd24c",
        annotation=dict(
            font_size=15,
            font_family="Exo 2",
            text=f"Current Price: {current_price}",
            font_color="#ffd24c",
        ),
        annotation_position="top left",
    )

    return fig


@app.callback(
    Output("chart_2d_eth", "figure"),
    [
        Input("period", "value"),
        Input("status", "value"),
        Input("amounts", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_eth(
    period: str,
    status: str,
    amounts: List[int],
    _,
):

    global df
    X = df.copy()
    symbol = "ETH"

    X, bubble_size, current_price = slice_for_plotting(
        X, symbol, period, status, amounts
    )
    fig = plot(X=X, title=symbol, bubble_size=bubble_size, current_price=current_price)

    return fig


@app.callback(
    Output("chart_2d_wbtc", "figure"),
    [
        Input("period", "value"),
        Input("status", "value"),
        Input("amounts", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d_wbtc(
    period: str,
    status: str,
    amounts: List[int],
    _,
):

    global df
    X = df.copy()
    symbol = "WBTC"

    X, bubble_size, current_price = slice_for_plotting(
        X, symbol, period, status, amounts
    )
    fig = plot(X=X, title=symbol, bubble_size=bubble_size, current_price=current_price)

    return fig


executor = ThreadPoolExecutor(max_workers=1)
executor.submit(get_new_data_every)


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
