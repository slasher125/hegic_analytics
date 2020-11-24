import pandas as pd
import plotly.express as px


def plot_bubble(
    X: pd.DataFrame, bubble_size: int, current_price: float, current_iv: int
):

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


def plot_pnl(agg: pd.DataFrame):

    agg = agg.rename(columns={"type": "Option Type"})
    agg["Click to select"] = agg["Option Type"]

    fig = px.bar(
        agg,
        x="pos",
        y="profit",
        color="Click to select",
        title="P&L for POOL LPs",
        labels={
            "profit": "Profit",
            "pos": "Group",
        },
        template="plotly_dark",
        color_discrete_sequence=["#45fff4", "#f76eb2"],
        hover_data={
            "Option Type": True,
            "Click to select": False,
        },
    )

    fig.update_layout(
        {
            "plot_bgcolor": "rgba(0, 0, 0, 0)",
            "paper_bgcolor": "rgba(0, 0, 0, 0)",
        },  # this removes the native plotly background
        font_family="Exo 2",
        font_color="#defefe",
        font_size=15,
    )

    return fig
