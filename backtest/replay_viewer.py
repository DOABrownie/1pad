from typing import Optional

import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

from app_logging.event_logger import get_logger

logger = get_logger(__name__)

# We will store df in a module-level variable for this simple local viewer.
_DF: Optional[pd.DataFrame] = None

# Number of bars to keep visible in the replay window
WINDOW_SIZE = 100


def _build_figure(end_index: int) -> go.Figure:
    """
    Build a candlestick figure using data up to end_index (inclusive).

    Uses:
      - Dark mode styling
      - Crosshair-like spikelines
      - A sliding window (last WINDOW_SIZE bars) so candles do not shrink
        to tiny size as replay progresses.
    """
    global _DF
    df = _DF
    if df is None or df.empty:
        return go.Figure()

    # Clamp index
    end_index = max(0, min(end_index, len(df) - 1))

    # Sliding window: last WINDOW_SIZE bars
    start_index = max(0, end_index - WINDOW_SIZE + 1)
    df_slice = df.iloc[start_index : end_index + 1]

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

    fig = go.Figure(data=[candle])

    fig.update_layout(
        template="plotly_dark",
        title="Backtest replay",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        hovermode="x",
        paper_bgcolor="#111111",
        plot_bgcolor="#111111",
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

    return fig


def run_replay_viewer(df: pd.DataFrame, symbol: str, timeframe: str):
    """
    Start a Dash app that replays candles bar-by-bar.

    Controls:
      - Play / Pause buttons
      - Speed selector (Slow / Normal / Fast)
      - Skip to End button (instantly plot all candles)
    """
    global _DF
    _DF = df.copy()

    if _DF.empty:
        logger.warning("Replay viewer started with empty dataframe.")
        return

    # Start a little bit into the data so you see some history immediately
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
                                "End",
                                id="btn-end",
                                n_clicks=0,
                                style={"marginRight": "10px"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Speed:",
                                style={"marginRight": "5px"},
                            ),
                            dcc.Dropdown(
                                id="speed-dropdown",
                                options=[
                                    {"label": "Slow", "value": "slow"},
                                    {"label": "Normal", "value": "normal"},
                                    {"label": "Fast", "value": "fast"},
                                ],
                                value="normal",
                                clearable=False,
                                style={
                                    "width": "150px",
                                    # Dark-mode dropdown styling
                                    "backgroundColor": "#222222",
                                    "color": "#FFFFFF",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
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
                interval=400,  # ms, will be updated by speed
                n_intervals=0,
                disabled=True,  # start paused
            ),
            dcc.Store(id="current-index", data=start_index),
        ],
    )

    # --------- Callbacks ---------

    @app.callback(
        [Output("replay-interval", "disabled"), Output("replay-interval", "interval")],
        [
            Input("btn-play", "n_clicks"),
            Input("btn-pause", "n_clicks"),
            Input("speed-dropdown", "value"),
        ],
        prevent_initial_call=True,
    )
    def control_interval(play_clicks, pause_clicks, speed_value):
        """
        Control whether the interval is running and at what speed.
        """
        import dash as _dash

        ctx = _dash.callback_context
        if not ctx.triggered:
            raise _dash.exceptions.PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Map speed labels to interval in ms
        speed_map = {
            "slow": 1000,
            "normal": 400,
            "fast": 150,
        }
        interval = speed_map.get(speed_value, 400)

        if trigger_id == "btn-play":
            disabled = False
        elif trigger_id == "btn-pause":
            disabled = True
        else:
            # speed change only; keep current disabled state
            disabled = _dash.no_update

        return disabled, interval

    @app.callback(
        [Output("replay-chart", "figure"), Output("current-index", "data")],
        [
            Input("replay-interval", "n_intervals"),
            Input("btn-end", "n_clicks"),
        ],
        State("current-index", "data"),
    )
    def update_chart(n_intervals, end_clicks, current_index):
        """
        Advance the current index by one bar on each interval tick,
        OR jump straight to the final bar when the End button is clicked.
        """
        import dash as _dash

        if _DF is None or _DF.empty:
            return go.Figure(), current_index

        if current_index is None:
            current_index = start_index

        ctx = _dash.callback_context
        if not ctx.triggered:
            raise _dash.exceptions.PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "btn-end":
            # Jump straight to final bar
            end_index = len(_DF) - 1
            fig = _build_figure(end_index)
            return fig, end_index

        # Otherwise, this is a replay-interval tick
        if current_index >= len(_DF) - 1:
            # Already at the end, nothing more to do
            return _build_figure(current_index), current_index

        next_index = current_index + 1
        fig = _build_figure(next_index)
        return fig, next_index

    logger.info("Starting Dash replay server at http://127.0.0.1:8050")
    app.run(debug=False)
