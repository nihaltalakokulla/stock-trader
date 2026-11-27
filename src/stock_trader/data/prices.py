from collections.abc import Callable, Sequence

import pandas as pd


def load_price_history(
    fetch: Callable[[str], pd.DataFrame], symbols: Sequence[str]
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = fetch(symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame
    return frames
