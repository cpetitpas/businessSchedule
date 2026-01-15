import pytest
import pandas as pd
from lib.gui_handlers import tree_to_df


@pytest.fixture
def mock_tree():
    class MockTree:
        def __init__(self):
            self.columns = ["Employee/Input", "Anthony F", "Carol L"]
            self._data = {
                "0": ["Work Area", "Bar", "Kitchen"],
                "1": ["Preferred Shift", "Evening", "Morning"]
            }
            self.get_children = lambda: ["0", "1"]

        def item(self, iid, option=None):
            values = self._data.get(iid, [""] * len(self.columns))
            if option == "values":
                return tuple(values)  # ← Must return tuple (what real Treeview does)
            return {"values": values}  # Keep for compatibility

        def __getitem__(self, key):
            if key == "columns":
                return self.columns
            raise KeyError(f"MockTree does not support key: {key}")

    return MockTree()


def test_tree_to_df_correct_structure(mock_tree):
    df = tree_to_df(mock_tree, has_index=False)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["Employee/Input", "Anthony F", "Carol L"]
    assert len(df) == 2
    assert df.iloc[0, 0] == "Work Area"  # Should now pass
    assert df.iloc[0, 1] == "Bar"


def test_tree_to_df_roundtrip(mock_tree, tmp_path):
    df = tree_to_df(mock_tree, has_index=False)
    temp_file = tmp_path / "test_roundtrip.csv"
    df.to_csv(temp_file, index=False)

    # Read back with dtype=str to avoid float/NaN conversion
    df_reloaded = pd.read_csv(temp_file, dtype=str)
    pd.testing.assert_frame_equal(df.astype(str), df_reloaded)