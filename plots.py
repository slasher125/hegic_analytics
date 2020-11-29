import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def plot_bubble(
    X: pd.DataFrame,
    bubble_size: int,
    current_price: float,
    current_iv: float,
    symbol: str,
):

    # hegic colors, first one is for calls (green), second for puts (red)
    colors = ["#45fff4", "#f76eb2"]

    # have to handle the color thing in case the ID search is used (will result in one unique sample)
    if len(X) == 1:
        if X["Option Type"].values[0] == "CALL":
            colors = [colors[0]]
        elif X["Option Type"].values[0] == "PUT":
            colors = [colors[1]]

    option_size = X["Option Size"].max()
    nb_put_call = X["Option Type"].value_counts()
    nb_unique_acc = X["Account"].nunique()
    volume = X["Option Size"].sum()

    title = f"""Puts: {nb_put_call['PUT'] if 'PUT' in nb_put_call else 0} Calls: {nb_put_call['CALL'] if 'CALL' in nb_put_call else 0} | Volume: {volume:.2f} {symbol} | Max Option-Size: {option_size} {symbol} | Unique Accounts: {nb_unique_acc} | Current IV: {current_iv}"""

    fig = px.scatter(
        X,
        x="Expires On",
        y="Strike Price",
        size="Option Size",
        size_max=bubble_size,
        color="Click to select",
        title=title,
        hover_name="Account",
        hover_data={
            "Break-even price": ":s",
            "Option Type": True,
            "Option ID": True,
            "Placed At": "|%b %d, %Y, %H:%M",  # same format as `Expires On` e.g. Dec 7, 2020, 12:02
            "Period of Holding": True,
            "Premium": True,
            "Settlement Fee": True,
            "Total Fee": True,
            "Profit": True,
            "Click to select": False,
            "Group": True,
        },
        color_discrete_sequence=colors,
        template="plotly_dark",
    )

    fig.update_layout(
        {
            "plot_bgcolor": "rgba(0, 0, 0, 0)",
            "paper_bgcolor": "rgba(0, 0, 0, 0)",
        },  # this removes the native plotly background
        font_family="Exo 2",
        font_color="#defefe",
        font_size=13,
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
            font_size=13,
            font_family="Exo 2",
            text=f"Current Price: {current_price}",
            font_color="#ffd24c",
        ),
        annotation_position="top left",
    )

    return fig


def plot_pnl(agg: pd.DataFrame, balances: pd.DataFrame, symbol: str):

    # hegic colors, first one is for calls (green), second for puts (red)
    colors = ["#45fff4", "#f76eb2"]
    agg = agg.sort_values("type")  # to make sure color order is always the same
    # have to handle the color thing in case the ID search is used (will result in one unique sample)

    if agg["type"].nunique() == 1:
        typ = agg["type"].unique()[0]
        if typ == "CALL":
            colors = [colors[0]]
        elif typ == "PUT":
            colors = [colors[1]]

    agg = agg.rename(columns={"type": "Option Type"})
    agg["Click to select"] = agg["Option Type"]
    agg = agg.round(2)

    pl_pct = round(
        (
            agg[agg["group"] == "P&L"]["profit"].sum()
            / balances.loc[symbol]["totalBalance"]
        )
        * 100,
        3,
    )

    fig = px.bar(
        agg,
        x="group",
        y="profit",
        color="Click to select",
        title=f"POOL P&L for selected range: {pl_pct}%",
        labels={
            "profit": f"Profit in {symbol}",
            "group": "Group",
        },
        template="plotly_dark",
        color_discrete_sequence=colors,
        hover_data={
            "Option Type": True,
            "Click to select": False,
        },
        text="profit",
        category_orders={"group": ["ITM", "OTM", "P&L"]},
        height=550,
    )

    fig.update_layout(
        {
            "plot_bgcolor": "rgba(0, 0, 0, 0)",
            "paper_bgcolor": "rgba(0, 0, 0, 0)",
        },  # this removes the native plotly background
        font_family="Exo 2",
        font_color="#defefe",
        font_size=13,
        showlegend=False,
        xaxis_title="",
        title_x=0.5,
    )

    # move xaxis name closer to plot
    fig.update_yaxes(title_standoff=0)

    return fig


def plot_pool_balance(balances: pd.DataFrame, symbol: str):

    agg = balances.loc[symbol].to_frame().T[["availableBalance", "totalBalance"]]
    util_rate = round(balances.loc[symbol]["util_ratio"] * 100, 2)
    agg = agg.round(2)
    fig = px.bar(
        agg,
        barmode="overlay",
        color_discrete_sequence=["#45fff4", "#45fff4"],
        height=400,
    )

    fig.update_layout(
        {
            "plot_bgcolor": "rgba(0, 0, 0, 0)",
            "paper_bgcolor": "rgba(0, 0, 0, 0)",
        },  # this removes the native plotly background
        title=f"LP Pool Balance - UR: {util_rate}%",
        font_family="Exo 2",
        font_color="#defefe",
        font_size=13,
        yaxis_title=f"Nb of {symbol}",
        showlegend=False,
        template="plotly_dark",
        title_x=0.5,
    )

    # move xaxis name closer to plot
    fig.update_yaxes(title_standoff=0)
    fig.update_xaxes(showticklabels=False, title="")

    return fig


def plot_put_call_ratio(df: pd.DataFrame, symbol: str):

    X = df[(df["status"] == "ACTIVE") & (df["symbol"] == symbol)]
    X = X.groupby("type")["amount"].sum().to_frame("Volume")
    X["pct"] = X["Volume"] / X["Volume"].sum()
    X = X.reset_index().rename(columns={"type": "Option Type"})

    fig = px.pie(
        X,
        values="Volume",
        names="Option Type",
        color_discrete_sequence=["#45fff4", "#f76eb2"],
        hover_data={
            "Volume": ":.2f",
        },
    )

    fig.update_layout(
        {
            "plot_bgcolor": "rgba(0, 0, 0, 0)",
            "paper_bgcolor": "rgba(0, 0, 0, 0)",
        },  # this removes the native plotly background
        title="Put-Call Ratio",
        font_family="Exo 2",
        font_color="#defefe",
        font_size=13,
        showlegend=False,
        template="plotly_dark",
        title_x=0.5,
    )

    return fig
