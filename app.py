import dash
import dash_html_components as html
import plotly.express as px
import dash_core_components as dcc
from dash.dependencies import Input, Output

import api


df = api.get_data("options")
df["day"] = df["expiration"].dt.strftime("%Y-%m-%d")
df["month"] = df["expiration"].dt.month_name()

options_months = []
for m in df["month"].unique():
    options_months.append({"label": m, "value": m})

options_days = []
for d in df["day"].unique():
    options_days.append({"label": d, "value": d})

unique_amounts = list(df["amount"].sort_values(ascending=False).unique())
unique_amounts = [str(i) for i in unique_amounts]
options_amounts = []
for a in unique_amounts:
    options_amounts.append({"label": str(a), "value": str(a)})


# Initialise the app
app = dash.Dash(__name__)

app.layout = html.Div(
    children=[
        html.Div(
            className="row",
            children=[
                html.Div(
                    className="four columns div-user-controls",
                    children=[
                        html.H1("Hegic Options Analytics Tool"),
                        html.P(
                            "Visualising ETH or WBTC options per strike price, expiration date and options amount."
                        ),
                        html.P("The bubble size corresponds to the options amount."),
                        html.P("Pick what you need from the dropdowns below."),
                        html.Div(html.P("Select the symbol")),
                        html.Div(
                            className="div-for-dropdown",
                            children=[
                                dcc.Dropdown(
                                    id="symbol",
                                    options=[
                                        {"label": "ETH", "value": "ETH"},
                                        {"label": "WBTC", "value": "WBTC"},
                                    ],
                                    multi=False,
                                    value=["ETH"],  # default
                                    placeholder="Select btw ETH or WBTC",
                                    style={"backgroundColor": "#1E1E1E"},
                                    className="stockselector",
                                ),
                            ],
                            style={"color": "#1E1E1E"},
                        ),
                        html.Div(html.P("Select the period(s)")),
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
                                    style={"backgroundColor": "#1E1E1E"},
                                    className="stockselector",
                                ),
                            ],
                            style={"color": "#1E1E1E"},
                        ),
                        html.Div(html.P("Select status")),
                        html.Div(
                            className="div-for-dropdown",
                            children=[
                                dcc.Dropdown(
                                    id="status",
                                    options=[
                                        {"label": "ACTIVE", "value": "ACTIVE"},
                                        {"label": "EXPIRED", "value": "EXPIRED"},
                                        {"label": "EXERCISED", "value": "EXERCISED"},
                                    ],
                                    value=["ACTIVE"],  # default
                                    multi=False,
                                    placeholder="Select status",
                                    style={"backgroundColor": "#1E1E1E"},
                                    className="stockselector",
                                ),
                            ],
                            style={"color": "#1E1E1E"},
                        ),
                        html.Div(html.P("Select amounts")),
                        html.Div(
                            className="div-for-dropdown",
                            children=[
                                dcc.Dropdown(
                                    id="amounts",
                                    options=options_amounts,
                                    value=unique_amounts,  # default
                                    multi=True,
                                    placeholder="Select amounts",
                                    style={"backgroundColor": "#1E1E1E"},
                                    className="stockselector",
                                ),
                            ],
                            style={"color": "#1E1E1E"},
                        ),
                        html.Div(html.P("Select month(s)")),
                        html.Div(
                            className="div-for-dropdown",
                            children=[
                                dcc.Dropdown(
                                    id="months",
                                    options=options_months,
                                    value=df["month"].unique(),  # default
                                    multi=True,
                                    placeholder="Select months",
                                    style={"backgroundColor": "#1E1E1E"},
                                    className="stockselector",
                                ),
                            ],
                            style={"color": "#1E1E1E"},
                        ),
                        html.Div(html.P("Select days(s)")),
                        html.Div(
                            className="div-for-dropdown",
                            children=[
                                dcc.Dropdown(
                                    id="days",
                                    options=options_days,
                                    value=sorted(df["day"].unique()),  # default
                                    multi=True,
                                    placeholder="Select days",
                                    style={"backgroundColor": "#1E1E1E"},
                                    className="stockselector",
                                ),
                            ],
                            style={"color": "#1E1E1E"},
                        ),
                    ],
                ),
                html.Div(
                    className="eight columns div-for-charts bg-grey",
                    children=[
                        dcc.Graph(
                            id="chart_2d",
                            config={"displayModeBar": False},
                        ),
                        dcc.Graph(
                            id="chart_3d",
                            config={"displayModeBar": False},
                        ),
                    ],
                ),
            ],
        )
    ]
)


title = (
    "Nb of options (bubble size) compared to strike, expiration date and option type"
)


@app.callback(
    Output("chart_2d", "figure"),
    [
        Input("symbol", "value"),
        Input("period", "value"),
        Input("status", "value"),
        Input("amounts", "value"),
        Input("months", "value"),
        Input("days", "value"),
    ],
)
def chart2d(
    symbol: str,
    period: str,
    status: str,
    amounts: str,
    months: str,
    days: str,
):

    X = df.copy()
    X = X[X["symbol"] == symbol]
    X = X[X["period_days"].isin(period)]
    X = X[X["status"] == status]
    X = X[X["month"].isin(months)]
    X = X[X["day"].isin(days)]
    X = X[X["amount"].astype(str).isin(amounts)]

    fig = px.scatter(
        X,
        x="expiration",
        y="strike",
        size="amount",
        size_max=70,
        color="type",
        title=title,
        template="plotly_dark",
    ).update_layout(
        {"plot_bgcolor": "rgba(0, 0, 0, 0)", "paper_bgcolor": "rgba(0, 0, 0, 0)"}
    )

    return fig


@app.callback(
    Output("chart_3d", "figure"),
    [
        Input("symbol", "value"),
        Input("period", "value"),
        Input("status", "value"),
        Input("amounts", "value"),
        Input("months", "value"),
        Input("days", "value"),
    ],
)
def chart3d(
    symbol: str,
    period: str,
    status: str,
    amounts: str,
    months: str,
    days: str,
):

    X = df.copy()
    X = X[X["symbol"] == symbol]
    X = X[X["period_days"].isin(period)]
    X = X[X["status"] == status]
    X = X[X["month"].isin(months)]
    X = X[X["day"].isin(days)]
    X = X[X["amount"].astype(str).isin(amounts)]

    fig = px.scatter_3d(
        X,
        x="expiration",
        y="strike",
        z="amount",
        size="amount",
        size_max=70,
        color="type",
        title=title,
        template="plotly_dark",
    ).update_layout(
        {"plot_bgcolor": "rgba(0, 0, 0, 0)", "paper_bgcolor": "rgba(0, 0, 0, 0)"}
    )

    return fig


# Run the app
if __name__ == "__main__":
    app.run_server()
