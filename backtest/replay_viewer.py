from typing import Optional, List, Dict, Any

import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

from app_logging.event_logger import get_logger

logger = get_logger(__name__)

# Module-level state for the simple local viewer
_DF: Optional[pd.DataFrame] = None
_TRADES: Optional[List[Dict[str, Any]]] = None
_STRATEGY: str = "sma"
_METRICS: Optional[Dict[str, Any]] = None

WINDOW_SIZE = 150


def _build_figure(end_index: int) -> go.Figure:
    """
    Build a candlestick figure using data up to end_index (inclusive).

    Includes:
      - Dark theme styling
      - Sliding window (last WINDOW_SIZE bars)
      - SMA 10 / SMA 50 when present and strategy == 'sma'
      - Trade overlays (entries, TP, SL)
      - Strategy summary annotation on the right
    """
    global _DF, _TRADES, _STRATEGY, _METRICS

    if _DF is None or _DF.empty:
        return go.Figure()

    df = _DF
    trades = _TRADES or []

    end_index = max(0, min(end_index, len(df) - 1))
    start_index = max(0, end_index - WINDOW_SIZE + 1)
    df_slice = df.iloc[start_index : end_index + 1]

    fig = go.Figure()

    # Candles
    candle = go.Candlestick(
        x=df_slice.index,
        open=df_slice["open"],
        high=df_slice["high"],
        low=df_slice["low"],
        close=df_slice["close"],
        name="Price",
        hovertemplate=(
            "Time: %{x}<br>"
            "Open: %{open}<br>"
            "High: %{high}<br>"
            "Low: %{low}<br>"
            "Close: %{close}<extra></extra>"
        ),
    )
    fig.add_trace(candle)

    # SMAs if strategy uses them
    if _STRATEGY == "sma":
        if "sma_fast" in df_slice.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_slice.index,
                    y=df_slice["sma_fast"],
                    mode="lines",
                    name="SMA 10",
                    line=dict(width=1),
                    hoverinfo="skip",
                )
            )
        if "sma_slow" in df_slice.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_slice.index,
                    y=df_slice["sma_slow"],
                    mode="lines",
                    name="SMA 50",
                    line=dict(width=1),
                    hoverinfo="skip",
                )
            )

    # Trade overlays
    entries_x: List[Any] = []
    entries_y: List[float] = []

    for tr in trades:
        entry_idx = tr["entry_index"]
        exit_idx = tr["exit_index"]
        entry_price = tr["entry_price"]
        tp = tr.get("take_profit")
        sl = tr.get("stop_loss")

        if entry_idx > end_index:
            continue

        entry_time = df.index[entry_idx]
        entries_x.append(entry_time)
        entries_y.append(entry_price)

        # Draw TP / SL lines for the visible part of the trade
        visible_start = max(entry_idx, start_index)
        visible_end = min(exit_idx, end_index)

        # If the trade is completely left of the current window,
        # or indices are reversed after clipping, skip drawing.
        if exit_idx < start_index or visible_end < visible_start:
            continue

        if tp is not None:
            fig.add_trace(
                go.Scatter(
                    x=[df.index[visible_start], df.index[visible_end]],
                    y=[tp, tp],
                    mode="lines",
                    name="Take Profit",
                    line=dict(width=1, dash="dash"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        if sl is not None:
            fig.add_trace(
                go.Scatter(
                    x=[df.index[visible_start], df.index[visible_end]],
                    y=[sl, sl],
                    mode="lines",
                    name="Stop Loss",
                    line=dict(width=1, dash="dot"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    if entries_x:
        fig.add_trace(
            go.Scatter(
                x=entries_x,
                y=entries_y,
                mode="markers",
                name="Entries",
                marker=dict(size=8, symbol="triangle-up"),
                hovertemplate="Entry<br>Time: %{x}<br>Price: %{y}<extra></extra>",
            )
        )

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(color="#FFFFFF"),
        margin=dict(l=40, r=200, t=50, b=40),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
        ),
        xaxis=dict(
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            gridcolor="#333333",
            zerolinecolor="#333333",
        ),
        yaxis=dict(
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            gridcolor="#333333",
            zerolinecolor="#333333",
        ),
    )

    # Strategy summary annotation
    metrics = _METRICS or {}
    if metrics:
        text_lines = [
            f"Start: {metrics.get('starting_balance', 0):.2f}",
            f"End: {metrics.get('ending_balance', 0):.2f}",
            f"Net: {metrics.get('net_profit', 0):.2f}",
            f"Return: {metrics.get('net_return_pct', 0):.2f} %",
            f"Trades: {metrics.get('num_trades', 0)}",
        ]
        summary_text = "<br>".join(text_lines)

        fig.add_annotation(
            x=1.02,
            y=0.5,
            xref="paper",
            yref="paper",
            text=summary_text,
            showarrow=False,
            align="left",
            font=dict(size=11, color="#FFFFFF"),
            bgcolor="rgba(0, 0, 0, 0.5)",
        )

    return fig


def run_replay_viewer(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    trades: Optional[List[Dict[str, Any]]] = None,
    strategy: str = "sma",
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Start a Dash app that replays candles bar-by-bar.

    Controls:
      - Play / Pause / Step buttons
      - Speed selector (Slow / Normal / Fast)
      - End button (jump to final bar)
    """
    global _DF, _TRADES, _STRATEGY, _METRICS

    _DF = df.copy()
    _TRADES = trades or []
    _STRATEGY = strategy.lower()
    _METRICS = metrics or {}

    if _DF.empty:
        logger.warning("Replay viewer started with empty dataframe.")
        return

    start_index = max(0, min(50, len(_DF) - 1))

    app = dash.Dash(__name__)
    app.title = "Backtest Replay"

    app.layout = html.Div(
        style={"backgroundColor": "#111111", "color": "#FFFFFF", "padding": "10px"},
        children=[
            html.H2(
                f"Backtest Replay — {symbol} {timeframe}",
                style={"textAlign": "center"},
            ),
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "10px",
                },
                children=[
                    html.Div(
                        [
                            html.Button(
                                "Play",
                                id="btn-play",
                                n_clicks=0,
                                style={"marginRight": "10px"},
                            ),
                            html.Button(
                                "Pause",
                                id="btn-pause",
                                n_clicks=0,
                                style={"marginRight": "10px"},
                            ),
                            html.Button(
                                "Step",
                                id="btn-step",
                                n_clicks=0,
                                style={"marginRight": "10px"},
                            ),
                            html.Button(
                                "End",
                                id="btn-end",
                                n_clicks=0,
                                style={"marginRight": "10px"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Span("Speed:", style={"marginRight": "8px"}),
                            dcc.Dropdown(
                                id="speed-dropdown",
                                options=[
                                    {"label": "Slow", "value": "slow"},
                                    {"label": "Normal", "value": "normal"},
                                    {"label": "Fast", "value": "fast"},
                                ],
                                value="normal",
                                clearable=False,
                                style={"width": "140px"},
                            ),
                        ]
                    ),
                ],
            ),
            dcc.Graph(
                id="replay-chart",
                figure=_build_figure(start_index),
                style={"height": "80vh"},
            ),
            dcc.Interval(
                id="replay-interval",
                interval=400,
                n_intervals=0,
                disabled=True,
            ),
            dcc.Store(id="current-index", data=start_index),
        ],
    )

    @app.callback(
        [Output("replay-interval", "disabled"), Output("replay-interval", "interval")],
        [
            Input("btn-play", "n_clicks"),
            Input("btn-pause", "n_clicks"),
            Input("btn-step", "n_clicks"),
            Input("speed-dropdown", "value"),
        ],
        prevent_initial_call=True,
    )
    def control_interval(play_clicks, pause_clicks, step_clicks, speed_value):
        """
        Control whether the interval is running and at what speed.
        """
        import dash as _dash

        ctx = _dash.callback_context
        if not ctx.triggered:
            raise _dash.exceptions.PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        speed_map = {
            "slow": 1000,
            "normal": 400,
            "fast": 150,
        }
        interval = speed_map.get(speed_value, 400)

        if trigger_id == "btn-play":
            disabled = False
        elif trigger_id in ("btn-pause", "btn-step"):
            disabled = True
        else:
            disabled = _dash.no_update

        return disabled, interval

    @app.callback(
        [Output("replay-chart", "figure"), Output("current-index", "data")],
        [
            Input("replay-interval", "n_intervals"),
            Input("btn-end", "n_clicks"),
            Input("btn-step", "n_clicks"),
        ],
        State("current-index", "data"),
    )
    def update_chart(n_intervals, end_clicks, step_clicks, current_index):
        """
        Advance the current index on each interval tick,
        jump to the end when End is pressed,
        or move forward exactly one bar when Step is pressed.
        """
        import dash as _dash

        global _DF

        if _DF is None or _DF.empty:
            return go.Figure(), current_index

        if current_index is None:
            current_index = start_index

        ctx = _dash.callback_context
        if not ctx.triggered:
            raise _dash.exceptions.PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "btn-end":
            end_index = len(_DF) - 1
            fig = _build_figure(end_index)
            return fig, end_index

        if trigger_id == "btn-step":
            if current_index >= len(_DF) - 1:
                return _build_figure(current_index), current_index
            next_index = current_index + 1
            fig = _build_figure(next_index)
            return fig, next_index

        # Interval tick
        if current_index >= len(_DF) - 1:
            return _build_figure(current_index), current_index

        next_index = current_index + 1
        fig = _build_figure(next_index)
        return fig, next_index

    logger.info("Starting Dash replay server at http://127.0.0.1:8050")
    app.run(debug=False)
