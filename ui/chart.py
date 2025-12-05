from typing import Optional

import dash
from dash import dcc, html
import plotly.graph_objects as go

from data.ohlcv_manager import OhlcvManager


def build_figure(ohlcv_manager: OhlcvManager) -> go.Figure:
    df = ohlcv_manager.get_closed_candles()

    fig = go.Figure()

    if not df.empty:
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Closed candles",
            )
        )

    current = ohlcv_manager.get_current_candle()
    if current is not None:
        # Plot forming candle as a separate OHLC (one bar)
        fig.add_trace(
            go.Ohlc(
                x=[current["timestamp"]],
                open=[current["open"]],
                high=[current["high"]],
                low=[current["low"]],
                close=[current["close"]],
                name="Forming candle",
            )
        )

    fig.update_layout(
        title="Price Chart",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
    )

    return fig


def create_dash_app(ohlcv_manager: OhlcvManager, live_mode: bool = True) -> dash.Dash:
    """
    Creates a Dash app for interactive charting.

    In a later step we will add:
      - Live Interval updates (dcc.Interval) to refresh the chart
      - Controls for backtest replay speed
    """
    app = dash.Dash(__name__)

    app.layout = html.Div(
        children=[
            html.H1("Trading Bot Chart"),
            dcc.Graph(
                id="price-chart",
                figure=build_figure(ohlcv_manager),
            ),
            # TODO: We can add controls for replay speed, play/pause buttons here.
        ]
    )

    # TODO: Add callbacks for live updates or BT replay

    return app
