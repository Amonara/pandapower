# -*- coding: utf-8 -*-

# Copyright (c) 2016-2018 by University of Kassel and Fraunhofer Institute for Energy Economics
# and Energy System Technology (IEE), Kassel. All rights reserved.


import pandas as pd
from pandapower import create_empty_network
from numpy import int64

try:
    import pplog as logging
except ImportError:
    import logging

logger = logging.getLogger(__name__)


def dicts_to_pandas(json_dict):
    pd_dict = dict()
    for k in sorted(json_dict.keys()):
        if isinstance(json_dict[k], dict):
            pd_dict[k] = pd.DataFrame.from_dict(json_dict[k], orient="columns")
            if pd_dict[k].shape[0] == 0:  # skip empty dataframes
                continue
            if pd_dict[k].index[0].isdigit():
                pd_dict[k].set_index(pd_dict[k].index.astype(int64), inplace=True)
        else:
            raise UserWarning("The json network is an old version or corrupt. "
                              "Trying to use the old load function")
    return pd_dict


def to_dict_of_dfs(net, include_results=False, create_dtype_df=True):
    dodfs = dict()
    dodfs["parameters"] = pd.DataFrame(columns=["parameter"])
    for item, table in net.items():
        # dont save internal variables and results (if not explicitely specified)
        if item.startswith("_") or (item.startswith("res") and not include_results):
            continue
        # attributes of "primitive" types are just stored in a DataFrame "parameters"
        elif isinstance(table, (int, float, bool, str)):
            dodfs["parameters"].loc[item] = net[item]
        elif item == "std_types":
            for t in net.std_types.keys():  # which are ["line", "trafo", "trafo3w"]
                dodfs["%s_std_types" % t] = pd.DataFrame(net.std_types[t]).T
        elif item == "user_pf_options":
            if len(table) > 0:
                dodfs["user_pf_options"] = pd.DataFrame(table, index=[0])
            else:
                continue
        elif type(table) != pd.DataFrame:
            # just skip empty things without warning
            if table:
                logger.warning("Attribute net.%s could not be saved !" % item)
            continue
        elif item == "bus_geodata":
            dodfs[item] = pd.DataFrame(table[["x", "y"]])
        elif item == "line_geodata":
            geo = pd.DataFrame()
            for i, coord in table.iterrows():
                for nr, (x, y) in enumerate(coord.coords):
                    geo.loc[i, "x%u" % nr] = x
                    geo.loc[i, "y%u" % nr] = y
            dodfs[item] = geo
        else:
            dodfs[item] = table
    return dodfs


def from_dict_of_dfs(dodfs):
    net = create_empty_network()
    for p, v in dodfs["parameters"].iterrows():
        net[p] = v.parameter
    for item, table in dodfs.items():
        if item in ("parameters", "dtypes"):
            continue
        elif item == "line_geodata":
            points = len(table.columns) // 2
            for i, coords in table.iterrows():
                coord = [(coords["x%u" % nr], coords["y%u" % nr]) for nr in range(points)
                         if pd.notnull(coords["x%u" % nr])]
                net.line_geodata.loc[i, "coords"] = coord
        elif item.endswith("_std_types"):
            net["std_types"][item[:-10]] = table.T.to_dict()
        elif item == "user_pf_options":
            net['user_pf_options'] = {c: v for c, v in zip(table.columns, table.values[0])}
        else:
            net[item] = table
    return net


def collect_all_dtypes_df(net):
    dtypes = []
    for element, table in net.items():
        if not hasattr(table, "dtypes"):
            continue
        for item, dtype in table.dtypes.iteritems():
            dtypes.append((element, item, str(dtype)))
    return pd.DataFrame(dtypes, columns=["element", "column", "dtype"])


def restore_all_dtypes(net, dtdf):
    for _, v in dtdf.iterrows():
        try:
            net[v.element][v.column] = net[v.element][v.column].astype(v["dtype"])
        except KeyError:
            logger.warning('Error while setting dtype of %s[%s]' % (v.element, v.column))
