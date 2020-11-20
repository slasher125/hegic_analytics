import datetime
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

import api


deciles = {round(i, 1): str(round(i, 1)) for i in np.arange(0.0, 1.1, 0.1)}


def get_new_data():
    """Updates the global variable 'df' with new data"""
    global df
    df = api.get_data("options")


def get_new_data_every(period=3600):
    """Update the data every 3600 seconds"""
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
                            html.P(
                                "Inspect individual ETH/WBTC options per strike price, expiration-date and option amount (displayed by the bubble size)."
                            ),
                            html.P("Choose from the dropdown menus below."),
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
                            html.Div(html.H2("PERIOD OF HOLDING")),
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
                            html.Div(html.H2("OPTION-SIZE SLIDER - ETH")),
                            html.Div(
                                className="div-for-slider",
                                children=[
                                    dcc.RangeSlider(
                                        id="amounts_eth",
                                        min=0.0,
                                        max=1.0,
                                        step=None,
                                        marks=deciles,
                                        value=[0.0, 1.0],
                                        allowCross=False,
                                        className="dropdown_selector",
                                    ),
                                ],
                            ),
                            html.Div(html.H2("OPTION-SIZE DECILE SLIDER - WBTC")),
                            html.Div(
                                className="div-for-slider",
                                children=[
                                    dcc.RangeSlider(
                                        id="amounts_wbtc",
                                        min=0.0,
                                        max=1.0,
                                        step=None,
                                        marks=deciles,
                                        value=[0.0, 1.0],
                                        allowCross=False,
                                        className="dropdown_selector",
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
    Output("chart_2d_eth", "figure"),
    [
        Input("period", "value"),
        Input("status", "value"),
        Input("amounts_eth", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d(
    period: str,
    status: str,
    amounts_eth: List[float],
    _,
):

    global df
    X = df.copy()
    symbol = "ETH"

    X = X.sort_values("type")
    X = X[X["symbol"] == symbol]
    X = X[X["period_days"].isin(period)]
    X = X[X["status"].isin(status)]
    lb, ub = X["amount"].quantile(amounts_eth[0]), X["amount"].quantile(amounts_eth[1])
    X = X[X["amount"].between(lb, ub)]

    # in case of no realised profit, set to nan
    X["profit"] = X["profit"].fillna("NaN")

    bubble_size = int(70 * amounts_eth[1])
    fig = plot(X=X, title=symbol, bubble_size=bubble_size)

    return fig


@app.callback(
    Output("chart_2d_wbtc", "figure"),
    [
        Input("period", "value"),
        Input("status", "value"),
        Input("amounts_wbtc", "value"),
        Input("invisible-div-callback-trigger", "children"),
    ],
)
def chart2d(
    period: str,
    status: str,
    amounts_wbtc: List[float],
    _,
):

    global df
    X = df.copy()
    symbol = "WBTC"

    X = X.sort_values("type")
    X = X[X["symbol"] == symbol]
    X = X[X["period_days"].isin(period)]
    X = X[X["status"].isin(status)]
    lb, ub = X["amount"].quantile(amounts_wbtc[0]), X["amount"].quantile(
        amounts_wbtc[1]
    )
    X = X[X["amount"].between(lb, ub)]

    # in case of no realised profit, set to nan
    X["profit"] = X["profit"].fillna("NaN")

    bubble_size = int(70 * amounts_wbtc[1])
    fig = plot(X=X, title=symbol, bubble_size=bubble_size)

    return fig


def plot(X: pd.DataFrame, title: str, bubble_size: int):

    # rename columms for plotting
    col_mapping = {
        "account": "Account",
        "amount": "Option Size",
        "exercise_timestamp": "Exercise Timestamp",
        "exercise_tx": "Exercise tx",
        "expiration": "Expires At",
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

    fig = px.scatter(
        X,
        x="Expires At",
        y="Strike Price",
        size="Option Size",
        size_max=bubble_size,
        color="Option Type",
        title=f"{title} - Max Option-Size Value: {X['Option Size'].max()}",
        hover_name="Account",
        hover_data={
            "Placed At": "|%b %d, %Y, %H:%M",
            "Period of Holding": True,
            "Premium": True,
            "Settlement Fee": True,
            "Total Fee": True,
            "Profit": True,
        },
        color_discrete_sequence=["#45fff4", "#f76eb2"],  # hegic colors
        template="plotly_dark",
    ).update_layout(
        {"plot_bgcolor": "rgba(0, 0, 0, 0)", "paper_bgcolor": "rgba(0, 0, 0, 0)"},
        font_family="Exo 2",
        title_font_family="Exo 2",
        title_font_color="#defefe",
        font={"size": 15},
    )

    return fig


executor = ThreadPoolExecutor(max_workers=1)
executor.submit(get_new_data_every)


# Run the app
if __name__ == "__main__":
    app.run_server()
