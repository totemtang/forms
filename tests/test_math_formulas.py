#  Copyright 2022-2023 The FormS Authors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import pytest
import pandas as pd
import numpy as np

import forms

df = None


@pytest.fixture(autouse=True)
def execute_before_and_after_one_test():
    global df
    df = pd.DataFrame(
        {
            "col1": ["A", "B", "C", "D"] * 10,
            "col2": [1] * 40,
            "col3": ["A", "B", "C", "D"] * 10,
            "col4": [1, 2, 3, 4] * 10,
        }
    )
    forms.config(cores=4, function_executor="df_pandas_executor")
    yield


def test_compute_is_odd():
    global df
    computed_df = forms.compute_formula(df, "=ISODD(D1)")
    expected_df = pd.DataFrame(np.array([True, False] * 20))
    assert np.array_equal(computed_df.values, expected_df.values)


def test_compute_sin():
    global df
    computed_df = forms.compute_formula(df, "=SIN(B1)")
    expected_df = pd.DataFrame(np.full(40, 0.841))
    assert np.allclose(computed_df.values, expected_df.values, rtol=1e-03)
