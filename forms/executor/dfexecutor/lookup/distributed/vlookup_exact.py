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
import pandas as pd
from dask.distributed import Client
from forms.executor.dfexecutor.lookup.algorithm.vlookup_exact import vlookup_exact_hash_vector


# Locally hashes a dataframe with 1 column and groups it by hash.
def hash_partition_df(df: pd.DataFrame, num_cores: int):
    hashed_df = pd.util.hash_array(df.iloc[:, 0].to_numpy()) % num_cores
    df['hash_DO_NOT_USE'] = hashed_df
    return df.groupby('hash_DO_NOT_USE')


# Chunks and hashes dataframes in df_list with a Dask client.
def hash_chunk_k_tables_distributed(client: Client, df_list: list[pd.DataFrame]):
    workers = list(client.scheduler_info()['workers'].keys())
    num_cores = len(workers)
    chunk_partitions = {}
    for df_idx in range(len(df_list)):
        chunk_partitions[df_idx] = []
        df = df_list[df_idx]
        for i in range(num_cores):
            worker_id = workers[i]
            start_idx = (i * df.shape[0]) // num_cores
            end_idx = ((i + 1) * df.shape[0]) // num_cores
            data = df[start_idx: end_idx]
            scattered_data = client.scatter(data, workers=worker_id)
            chunk_partitions[df_idx].append(client.submit(hash_partition_df, scattered_data, num_cores))
    for df_idx in range(len(df_list)):
        chunk_partitions[df_idx] = client.gather(chunk_partitions[df_idx])
    return chunk_partitions


# Local hash join to get the result.
def vlookup_exact_hash_local(values_partitions, df_partitions):
    values = pd.concat(values_partitions)
    if len(values) == 0:
        return pd.DataFrame(dtype=object)
    df = pd.concat(df_partitions)
    values, col_idxes = values.iloc[:, 0], values.loc[:, 'col_idxes_DO_NOT_USE']
    res = vlookup_exact_hash_vector(values, df, col_idxes)
    return res.set_index(values.index)


# Performs a distributed VLOOKUP on the given values with a Dask client.
def vlookup_exact_hash_distributed(client: Client,
                                   values: pd.Series,
                                   df: pd.DataFrame,
                                   col_idxes: pd.Series) -> pd.DataFrame:
    values = values.to_frame()
    values['col_idxes_DO_NOT_USE'] = col_idxes
    chunk_partitions = hash_chunk_k_tables_distributed(client, [values, df])
    workers = list(client.scheduler_info()['workers'].keys())
    num_cores = len(workers)
    result_futures = []
    for i in range(num_cores):
        worker_id = workers[i]
        values_partitions, df_partitions = [], []
        for j in range(num_cores):
            if i in chunk_partitions[0][j].groups:
                group = chunk_partitions[0][j].get_group(i)
                values_partitions.append(group)
            if i in chunk_partitions[1][j].groups:
                group = chunk_partitions[1][j].get_group(i)
                df_partitions.append(group)

        if len(values_partitions) > 0:
            scattered_values = client.scatter(values_partitions, workers=worker_id)
        else:
            scattered_values = pd.DataFrame(dtype=object)

        if len(df_partitions) > 0:
            scattered_df = client.scatter(df_partitions, workers=worker_id)
        else:
            scattered_df = pd.DataFrame(dtype=object)

        result_futures.append(client.submit(vlookup_exact_hash_local, scattered_values, scattered_df))

    results = client.gather(result_futures)
    return pd.concat(results).sort_index()
