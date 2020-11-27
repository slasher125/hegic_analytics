import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def plot_bubble(
    X: pd.DataFrame, bubble_size: int, current_price: float, current_iv: int
):

    # hegic colors, first one is for calls (green), second for puts (red)
    colors = ["#45fff4", "#f76eb2"]

    # have to handle the color thing in case the ID search is used (will result in one unique sample)
    if len(X) == 1:
        if X["Option Type"].values[0] == "CALL":
            colors = [colors[0]]
        elif X["Option Type"].values[0] == "PUT":
            colors = [colors[1]]

    fig = px.scatter(
        X,
        x="Expires On",
        y="Strike Price",
        size="Option Size",
        size_max=bubble_size,
        color="Click to select",
        title=f"Max Option-Size Value: {X['Option Size'].max()} - Current IV: {current_iv}",
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


def plot_pnl(agg: pd.DataFrame, symbol: str):

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

    fig = px.bar(
        agg,
        x="group",
        y="profit",
        color="Click to select",
        title="P&L for POOL LPs",
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
        # height=500,
        # width=500,
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
    fig.update_yaxes(title_standoff=0)

    return fig


def plot_pool_balance(balances: dict, symbol: str):

    totalBalance = balances[symbol]["totalBalance"]
    availableBalance = balances[symbol]["availableBalance"]
    util_rate = round(balances[symbol]["util_ratio"] * 100, 2)

    fig = go.Figure(
        data=[
            go.Bar(
                name="Total Balance",
                x=["Balance"],
                y=[totalBalance],
                text=[totalBalance],
                textposition="auto",
                marker_color=["#45fff4"],
                opacity=0.5,
            ),
            go.Bar(
                name="Available Balance",
                x=["Balance"],
                y=[availableBalance],
                text=[availableBalance],
                textposition="auto",
                marker_color=["#45fff4"],
            ),
        ]
    )
    # Change the bar mode
    fig.update_traces(texttemplate="%{text:.0f}")

    fig.update_layout(
        {
            "plot_bgcolor": "rgba(0, 0, 0, 0)",
            "paper_bgcolor": "rgba(0, 0, 0, 0)",
        },  # this removes the native plotly background
        barmode="overlay",
        title=f"Pool utilization rate: {util_rate}%",
        font_family="Exo 2",
        font_color="#defefe",
        font_size=15,
        # width=500,
        yaxis_title=f"Nb of {symbol}",
        showlegend=False,
        template="plotly_dark",
    )

    # move xaxis name closer to plot
    fig.update_yaxes(title_standoff=0)

    return fig
