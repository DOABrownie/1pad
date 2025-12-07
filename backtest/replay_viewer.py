from typing import Optional, List, Dict, Any

import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import math

from strategy.pivots import detect_pivots
from app_logging.event_logger import get_logger

logger = get_logger(__name__)

# We will store df and trades in module-level variables for this simple local viewer.
_DF: Optional[pd.DataFrame] = None
_TRADES: Optional[List[Dict[str, Any]]] = None
_STRATEGY: str = "1pad"
_START_BALANCE: float = 0.0
_MS_SERIES: Optional[pd.Series] = None

# Number of bars to keep visible in the replay window
WINDOW_SIZE = 200

def _compute_ms_series(df: pd.DataFrame) -> pd.Series:
    """
    Compute a simple market-structure series for 1pad.

    A structure point is defined as a candle whose CLOSE is higher than
    the CLOSE of the previous 4 candles and the next 4 candles.

    The returned series has the same index as df and at each bar holds
    the value of the most recent confirmed structure high (forward-fill).
    """
    closes = df["close"]
    n = len(closes)
    if n == 0:
        return pd.Series(index=df.index, dtype="float64")

    structure_points = pd.Series(index=df.index, dtype="float64")

    # Need 4 candles on the left and 4 on the right
    for i in range(4, n - 4):
        c = closes.iloc[i]
        left = closes.iloc[i - 4 : i]       # 4 closes on the left
        right = closes.iloc[i + 1 : i + 5]  # 4 closes on the right
        if (c > left).all() and (c > right).all():
            structure_points.iloc[i] = c

    # Forward-fill to create a running structure level
    structure_series = structure_points.ffill()

    return structure_series


def _compute_equity_at_index(index: int) -> Dict[str, float]:
    """Compute equity and PnL values for the 'Strat Data' overlay.

    Returns a dict with:
      - start_balance
      - current_balance
      - realized_pnl
      - unrealized_pnl
    """
    global _DF, _TRADES, _START_BALANCE

    df = _DF
    trades = _TRADES or []

    if df is None or df.empty:
        start_balance = float(_START_BALANCE)
        return {
            "start_balance": start_balance,
            "current_balance": start_balance,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }

    # Clamp index into valid range
    index = max(0, min(int(index), len(df) - 1))
    price = float(df["close"].iloc[index])

    realized_pnl = 0.0
    unrealized_pnl = 0.0

    for t in trades:
        # We expect viewer trades to contain sizing info for this calculation.
        size = float(t.get("size", 0.0))
        if size <= 0:
            continue

        try:
            entry_idx = int(t["entry_index"])
            exit_idx = int(t["exit_index"])
            entry_price = float(t["entry_price"])
            exit_price = float(t.get("exit_price", entry_price))
            direction = str(t.get("direction", "long")).lower()
        except Exception:
            # If any field is missing, skip this trade for safety.
            continue

        if index < entry_idx:
            # Trade has not opened yet at this index.
            continue

        if index >= exit_idx:
            # Trade is closed by this index: count full realized PnL.
            if direction == "long":
                realized_pnl += (exit_price - entry_price) * size
            else:
                realized_pnl += (entry_price - exit_price) * size
        else:
            # Trade is currently open: use current close as mark price.
            if direction == "long":
                unrealized_pnl += (price - entry_price) * size
            else:
                unrealized_pnl += (entry_price - price) * size

    start_balance = float(_START_BALANCE)
    current_balance = start_balance + realized_pnl + unrealized_pnl

    return {
        "start_balance": start_balance,
        "current_balance": current_balance,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
    }

def _add_onepad_overlays(
    fig: go.Figure,
    df: pd.DataFrame,
    trades: List[Dict[str, Any]],
    start_index: int,
    end_index: int,
) -> None:
    """
    Add 1pad-specific visual elements to the replay chart:

      - Market structure line used for BOS.
      - BOS vertical marker (if visible).
      - Net window (shaded box) for the current active 1pad trade.
      - Individual limit entry levels inside the net window.
      - Recent pivot highs/lows (last 4 of each) as markers.
    """
    if df is None or df.empty:
        return

    # Clamp indices into the dataframe range
    n = len(df)
    if n == 0:
        return

    start_index = max(0, min(int(start_index), n - 1))
    end_index = max(0, min(int(end_index), n - 1))
    if end_index < start_index:
        return

    df_slice = df.iloc[start_index : end_index + 1]
    if df_slice.empty:
        return

    x_start = df.index[start_index]
    x_end = df.index[end_index]

    # ------- Market structure series (4L/4R close-based) -------
    global _MS_SERIES
    ms_series = _MS_SERIES
    if ms_series is not None:
        try:
            ms_slice = ms_series.iloc[start_index : end_index + 1]

            if not ms_slice.empty:
                ms_visible = ms_slice.copy()

                # Number of right-hand candles required for confirmation
                rh = 4

                if len(ms_visible) > rh:
                    # We want to show only structure levels that are fully confirmed
                    # (i <= end_index - rh), but extend the last confirmed level
                    # horizontally all the way to the current bar.
                    last_confirm_idx = ms_visible.index[-rh - 1]
                    last_confirm_val = ms_visible.loc[last_confirm_idx]

                    # If we have at least one confirmed structure value, freeze
                    # the last `rh` bars at that confirmed level so the line
                    # extends to the right without introducing future-informed pivots.
                    if pd.notna(last_confirm_val):
                        ms_visible.iloc[-rh:] = last_confirm_val
                    else:
                        # No confirmed structure yet, keep as-is (likely all NaN).
                        pass

                # Drop any leading NaNs before plotting
                ms_visible = ms_visible.dropna()
                if not ms_visible.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=ms_visible.index,
                            y=ms_visible.values,
                            mode="lines",
                            name="Market Structure",
                            line=dict(width=1, dash="dot"),
                            hoverinfo="skip",
                        )
                    )
        except Exception as e:
            logger.debug(f"Error drawing market structure series: {e}")

    # ------- Recent pivot highs and lows (last 4 of each) -------
    try:
        _, pivot_highs, pivot_lows = detect_pivots(df_slice, left=1, right=1)

        ph_points = [
            (ts, price)
            for ts, price in pivot_highs.dropna().items()
        ]
        pl_points = [
            (ts, price)
            for ts, price in pivot_lows.dropna().items()
        ]

        ph_points = ph_points[-4:]
        pl_points = pl_points[-4:]

        if ph_points:
            fig.add_trace(
                go.Scatter(
                    x=[p[0] for p in ph_points],
                    y=[p[1] for p in ph_points],
                    mode="markers",
                    name="Pivot High",
                    marker=dict(size=8, symbol="triangle-up"),
                    hovertemplate="PH<br>Time: %{x}<br>Price: %{y}<extra></extra>",
                )
            )

        if pl_points:
            fig.add_trace(
                go.Scatter(
                    x=[p[0] for p in pl_points],
                    y=[p[1] for p in pl_points],
                    mode="markers",
                    name="Pivot Low",
                    marker=dict(size=8, symbol="triangle-down"),
                    hovertemplate="PL<br>Time: %{x}<br>Price: %{y}<extra></extra>",
                )
            )
    except Exception as e:
        logger.debug(f"Error computing pivots for 1pad overlay: {e}")

    # ------- Active 1pad trade (for net window, limit orders, BOS/structure) -------
    active_trades: List[Dict[str, Any]] = []
    for tr in trades:
        meta = tr.get("meta") or tr.get("onepad_meta")
        if not isinstance(meta, dict):
            continue

        entry_idx = tr.get("entry_index")
        exit_idx = tr.get("exit_index")
        if entry_idx is None or exit_idx is None:
            continue

        # Only consider trades that have started by this bar
        if entry_idx <= end_index:
            active_trades.append({"trade": tr, "meta": meta})

    if not active_trades:
        return

    # Use the most recent such trade
    context = active_trades[-1]
    tr = context["trade"]
    meta = context["meta"]

    entry_idx = int(tr["entry_index"])
    exit_idx = int(tr["exit_index"])

    # Restrict the x-extent of the net window to the visible region
    idx0 = max(start_index, entry_idx)
    idx1 = min(end_index, exit_idx)
    if idx0 >= n or idx1 < idx0:
        idx0 = start_index
        idx1 = end_index

    x0 = df.index[idx0]
    x1 = df.index[idx1]

    # Structure line used for BOS (if available)
    structure_level = None
    if isinstance(meta, dict):
        structure_level = meta.get("structure_level")
    try:
        if structure_level is not None and not (
            isinstance(structure_level, float) and math.isnan(structure_level)
        ):
            fig.add_trace(
                go.Scatter(
                    x=[x_start, x_end],
                    y=[structure_level, structure_level],
                    mode="lines",
                    name="Structure",
                    line=dict(width=1, dash="dot"),
                    hoverinfo="skip",
                )
            )
    except Exception as e:
        logger.debug(f"Error drawing structure line for 1pad overlay: {e}")

    # BOS vertical marker (if BOS candle is inside the visible window)
    bos_index = meta.get("bos_index") if isinstance(meta, dict) else None
    try:
        if bos_index is not None and bos_index in df.index:
            bos_time = bos_index
            if x_start <= bos_time <= x_end:
                fig.add_shape(
                    type="line",
                    xref="x",
                    yref="paper",
                    x0=bos_time,
                    x1=bos_time,
                    y0=0.0,
                    y1=1.0,
                    line=dict(width=1, dash="dash", color="#888888"),
                )
                fig.add_annotation(
                    xref="x",
                    yref="paper",
                    x=bos_time,
                    y=1.0,
                    xanchor="left",
                    yanchor="bottom",
                    showarrow=False,
                    text="BOS",
                    font=dict(size=10),
                )
    except Exception as e:
        logger.debug(f"Error drawing BOS marker for 1pad overlay: {e}")

    # Net window (shaded box)
    net = meta.get("net") if isinstance(meta, dict) else None
    if isinstance(net, dict):
        top = net.get("top")
        bottom = net.get("bottom")
        try:
            if top is not None and bottom is not None and bottom < top:
                fig.add_shape(
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=x0,
                    x1=x1,
                    y0=bottom,
                    y1=top,
                    line=dict(width=1, color="#666666"),
                    fillcolor="rgba(80, 80, 80, 0.25)",
                )
        except Exception as e:
            logger.debug(f"Error drawing net window for 1pad overlay: {e}")

    # Individual limit entry levels inside the net window
    entry_levels = tr.get("entry_levels")
    if entry_levels:
        order_x: List = []
        order_y: List = []
        try:
            for price in entry_levels:
                order_x.extend([x0, x1, None])
                order_y.extend([price, price, None])

            fig.add_trace(
                go.Scatter(
                    x=order_x,
                    y=order_y,
                    mode="lines",
                    name="Limit Orders",
                    line=dict(width=1),
                    hoverinfo="skip",
                )
            )
        except Exception as e:
            logger.debug(f"Error drawing limit order levels for 1pad overlay: {e}")

def _build_figure(end_index: int) -> go.Figure:
    """
    Build a candlestick figure using data up to end_index (inclusive).

    Uses:
      - Dark mode styling
      - Crosshair-like spikelines
      - A sliding window (last WINDOW_SIZE bars)
      - SMA 10 and SMA 50 lines (if present)
      - Trade overlays for entries and TP/SL levels
    """
    global _DF, _TRADES
    df = _DF
    trades = _TRADES or []

    if df is None or df.empty:
        return go.Figure()

    # Clamp index
    end_index = max(0, min(end_index, len(df) - 1))

    # Sliding window: last WINDOW_SIZE bars
    start_index = max(0, end_index - WINDOW_SIZE + 1)
    df_slice = df.iloc[start_index : end_index + 1]

    # --------------- Candles ---------------

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

    # --------------- SMAs (if available and strategy == 'sma') ---------------

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

    # --------------- Trade overlays ---------------

    entries_x = []
    entries_y = []

    tp_x = []
    tp_y = []
    sl_x = []
    sl_y = []

    for tr in trades:
        entry_idx = tr["entry_index"]
        exit_idx = tr["exit_index"]
        entry_price = tr["entry_price"]
        tp = tr["take_profit"]
        sl = tr["stop_loss"]

        # Only consider trades that have started by end_index
        if entry_idx > end_index:
            continue

        # Only draw segments that overlap the current window
        seg_start = max(entry_idx, start_index)
        seg_end = min(exit_idx, end_index)
        if seg_start > seg_end:
            continue

        # Entry marker (only once, at entry bar)
        if start_index <= entry_idx <= end_index:
            entries_x.append(df.index[entry_idx])
            entries_y.append(entry_price)

        # TP line segment
        tp_x.extend(
            [
                df.index[seg_start],
                df.index[seg_end],
                None,
            ]
        )
        tp_y.extend(
            [
                tp,
                tp,
                None,
            ]
        )

        # SL line segment
        sl_x.extend(
            [
                df.index[seg_start],
                df.index[seg_end],
                None,
            ]
        )
        sl_y.extend(
            [
                sl,
                sl,
                None,
            ]
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

    if tp_x:
        fig.add_trace(
            go.Scatter(
                x=tp_x,
                y=tp_y,
                mode="lines",
                name="Take Profit",
                line=dict(width=1, dash="dash"),
                hoverinfo="skip",
            )
        )

    if sl_x:
        fig.add_trace(
            go.Scatter(
                x=sl_x,
                y=sl_y,
                mode="lines",
                name="Stop Loss",
                line=dict(width=1, dash="dot"),
                hoverinfo="skip",
            )
        )

    # --------------- 1pad-specific overlays ---------------
    if _STRATEGY == "1pad":
        _add_onepad_overlays(fig, df, trades, start_index, end_index)

    # --------------- Layout ---------------

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

    # --------------- Strategy data overlay ---------------
    try:
        equity = _compute_equity_at_index(end_index)
        start_val = equity.get("start_balance", 0.0)
        current_val = equity.get("current_balance", start_val)
        realized = equity.get("realized_pnl", 0.0)
        unrealized = equity.get("unrealized_pnl", 0.0)

        text_lines = [
            "<b>Strat Data</b>",
            f"Start $ {start_val:,.2f}",
            f"Current $ {current_val:,.2f}",
            f"Realized PnL $ {realized:,.2f}",
            f"Unrealized PnL $ {unrealized:,.2f}",
        ]

        # Place a single annotation box centered at the top of the figure,
        # just above the plotting area (y = 1.0 is the top of the axes).
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.5,
            y=1.0,
            xanchor="center",
            yanchor="bottom",
            showarrow=False,
            align="center",
            text="<br>".join(text_lines),
            font=dict(size=11),
            bgcolor="#00332F",
            bordercolor="#FFFFFF",
            borderwidth=1,
            borderpad=8,
        )
    except Exception as e:
        # If anything goes wrong with the overlay, do not break the replay.
        logger.debug(f"Error computing strat data overlay: {e}")


    return fig



def run_replay_viewer(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    trades: Optional[List[Dict[str, Any]]] = None,
    strategy: str = "1pad",
    starting_balance: float = 0.0,
):
    """
    Start a Dash app that replays candles bar-by-bar.

    Controls:
      - Play / Pause buttons
      - Step button (pause if playing, then advance one bar per click)
      - Speed selector (Slow / Normal / Fast)
      - End button (instantly jump to final bar)


    Visuals:
      - Candlesticks
      - SMA 10 and SMA 50 (if present)
      - Entry markers
      - TP and SL horizontal bands
    """
    global _DF, _TRADES, _STRATEGY, _START_BALANCE, _MS_SERIES
    _DF = df.copy()
    _TRADES = trades or []
    _STRATEGY = strategy.lower()
    try:
        _START_BALANCE = float(starting_balance)
    except Exception:
        _START_BALANCE = 0.0

    # Pre-compute market structure series for 1pad
    try:
        if _STRATEGY == "1pad":
            _MS_SERIES = _compute_ms_series(_DF)
        else:
            _MS_SERIES = None
    except Exception as e:
        logger.debug(f"Error computing market structure series: {e}")
        _MS_SERIES = None


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
            # Both Pause and Step should stop the automatic interval
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
        Advance the current index by one bar on each interval tick,
        step forward by one bar when the Step button is clicked,
        or jump straight to the final bar when the End button is clicked.
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
            end_index = len(_DF) - 1
            fig = _build_figure(end_index)
            return fig, end_index

        if trigger_id in ("replay-interval", "btn-step"):
            # Either an automatic interval tick or a manual Step click
            if current_index >= len(_DF) - 1:
                return _build_figure(current_index), current_index

            next_index = current_index + 1
            fig = _build_figure(next_index)
            return fig, next_index

        # Any other trigger is unexpected here
        raise _dash.exceptions.PreventUpdate


    logger.info("Starting Dash replay server at http://127.0.0.1:8050")
    app.run(debug=False)
