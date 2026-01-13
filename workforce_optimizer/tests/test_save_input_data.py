import pytest
import pandas as pd
from lib.gui_handlers import tree_to_df


@pytest.fixture
def mock_tree():
    class MockTree:
        def __init__(self):
            self.columns = ["Employee/Input", "Anthony F", "Carol L"]
            self.get_children = lambda: ["0", "1"]
            self.item = lambda iid, option: {
                "values": ["Work Area", "Bar", "Kitchen"] if iid == "0" else
                          ["Preferred Shift", "Evening", "Morning"]
            } if option == "values" else None

        def __getitem__(self, key):
            if key == "columns":
                return self.columns
            raise KeyError(f"MockTree does not support key: {key}")

        def set(self, iid, col, value=None):
            if value is None:  # reading mode
                values = self.item(iid, "values")
                if values and col in self.columns:
                    idx = self.columns.index(col)
                    return values["values"][idx]
                return ""
            # writing mode (dummy for tests)
            pass

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