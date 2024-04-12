# -*- coding: utf-8 -*-
from typing import Iterable

import pandas as pd
import numpy as np
import brightway2 as bw
from bw2data.backends.peewee import ActivityDataset
from PySide2.QtCore import QModelIndex, Slot, Qt

from activity_browser import log, signals, activity_controller, cs_controller
from activity_browser.bwutils import commontasks as bc
from .base import EditablePandasModel, PandasModel


class CSGenericModel(EditablePandasModel):
    """ Intermediate class to enable internal move functionality for the
    reference flows and impact categories tables. The below flags and relocate functions
    are required to enable internal move.

    Technically, CSMethodsModel is not editable, but as no editing delegates are set in the
    tables, no editing is possible.
    """

    def flags(self, index):
        """ Returns flags
        """
        if not index.isValid():
            return super().flags(index) | Qt.ItemIsDropEnabled
        if index.row() < len(self._dataframe):
            return super().flags(index) | Qt.ItemIsDragEnabled
        return super().flags(index)

    def relocateRow(self, row_source, row_target) -> None:
        """ Relocate a row.
        Move a row in the table to another position and store the new dataframe
        """
        row_a, row_b = max(row_source, row_target), min(row_source, row_target)
        self.beginMoveRows(QModelIndex(), row_a, row_a, QModelIndex(), row_b)
        # copy data
        data_source = self._dataframe.iloc[row_source].copy()
        if row_source > row_target:  # the row needs to be moved up
            pass
            # delete old row
            self._dataframe = self._dataframe.drop(row_source, axis=0).reset_index(drop=True)
            # insert data
            self._dataframe = pd.DataFrame(np.insert(self._dataframe.values,
                                                     row_target,
                                                     values=data_source,
                                                     axis=0),
                                           columns=self.HEADERS)
        elif row_source < row_target:  # the row needs to be moved down
            pass
            # insert data
            self._dataframe = pd.DataFrame(np.insert(self._dataframe.values,
                                                     row_target,
                                                     values=data_source,
                                                     axis=0),
                                           columns=self.HEADERS)
            # delete old row
            self._dataframe = self._dataframe.drop(row_source, axis=0).reset_index(drop=True)

        self.updated.emit()
        signals.calculation_setup_changed.emit()
        self.endMoveRows()


class CSActivityModel(CSGenericModel):
    HEADERS = [
        "Amount", "Unit", "Product", "Activity", "Location", "Database"
    ]

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.current_cs = None
        self.key_col = 0
        self._activities = []

        self.HEADERS = self.HEADERS + ["key"]

        signals.calculation_setup_selected.connect(self.load)
        self.dataChanged.connect(lambda: signals.calculation_setup_changed.emit())

    @property
    def activities(self) -> list:
        # if no dataframe is present return empty list
        if not isinstance(self._dataframe, pd.DataFrame): return []
        # else return the selected activities
        selection = self._dataframe.loc[:, ["Amount", "key"]].to_dict(orient="records")
        return [{x["key"]: x["Amount"]} for x in selection]

    def get_key(self, proxy: QModelIndex) -> tuple:
        idx = self.proxy_to_source(proxy)
        return self._dataframe.iat[idx.row(), self.key_col]

    def load(self, name: str):
        assert name in cs_controller, "Given calculation setup does not exist."

        for act in self._activities:
            act.changed.disconnect(self.sync)
        self._activities.clear()

        self.current_cs = name
        self.sync()

    def sync(self):
        assert self.current_cs, "CS Model not yet loaded"
        fus = cs_controller.get(self.current_cs, {}).get('inv', [])
        df = pd.DataFrame([
            self.build_row(key, amount) for func_unit in fus
            for key, amount in func_unit.items()
        ], columns=self.HEADERS)
        # Drop rows where the fu key was invalid in some way.
        self._dataframe = df.dropna().reset_index(drop=True)
        self.key_col = self._dataframe.columns.get_loc("key")
        self.updated.emit()

    def build_row(self, key: tuple, amount: float = 1.0) -> dict:
        try:
            act = activity_controller.get(key)
            if act.get("type", "process") != "process":
                raise TypeError("Activity is not of type 'process'")
            row = {
                key: act.get(bc.AB_names_to_bw_keys[key], "")
                for key in self.HEADERS[:-1]
            }
            row.update({"Amount": amount, "key": key})

            act.changed.connect(self.sync)
            self._activities.append(act)

            return row
        except (TypeError, ActivityDataset.DoesNotExist):
            log.error("Could not load key '{}' in Calculation Setup '{}'".format(str(key), self.current_cs))
            return {}

    @Slot(name="deleteRows")
    def delete_rows(self, proxies: list) -> None:
        indices = (self.proxy_to_source(p) for p in proxies)
        rows = {i.row() for i in indices}

        for key in [self._dataframe.at[row, "key"] for row in rows]:
            activity = activity_controller.get(key)
            activity.changed.disconnect(self.sync)

        self._dataframe = self._dataframe.drop(rows).reset_index(drop=True)
        self.updated.emit()
        signals.calculation_setup_changed.emit()  # Trigger update of CS in brightway

    def include_activities(self, new_activities: Iterable) -> None:
        existing = set(self._dataframe.loc[:, "key"])
        data = []
        for fu in (f for f in new_activities if existing.isdisjoint(f)):
            k, v = zip(*fu.items())
            data.append(self.build_row(k[0], v[0]))
        if data:
            self._dataframe = pd.concat([self._dataframe, pd.DataFrame(data)], ignore_index=True)
            self.updated.emit()
            signals.calculation_setup_changed.emit()


class CSMethodsModel(CSGenericModel):
    HEADERS = ["Name", "Unit", "# CFs", "method"]

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.current_cs = None
        signals.calculation_setup_selected.connect(self.update_cs)
        signals.method_deleted.connect(
            lambda: self.update_cs(self.current_cs))

    @property
    def methods(self) -> list:
        return [] if self._dataframe is None else self._dataframe.loc[:, "method"].to_list()

    @Slot(name="UpdateBWCalculationSetup")
    def update_cs(self, name: str = None) -> None:
        """Updates and syncs the bw.calculation_setups for the Impact categories. Removes any
        Impact category from a calculation setup if it is not present in the current environment"""
        def filter_methods(cs):
            """Filters any methods out from the calculation setup if they aren't in bw.methods"""
            i = 0
            while i < len(cs):
                if cs[i] not in bw.methods:
                    cs.pop(i)
                else:
                    i += 1

        if self.current_cs is not None or name is not None:
            self.current_cs = name
            filter_methods(cs_controller[self.current_cs].get('ia', []))
            self.sync(self.current_cs)
        else:
            for name, cs in cs_controller.items():
                filter_methods(cs['ia'])
            self.sync()

    @Slot(str, name="syncModel")
    def sync(self, name: str = None) -> None:
        if name:
            assert name in cs_controller, "Given calculation setup does not exist."
            self.current_cs = name
            self._dataframe = pd.DataFrame([
                self.build_row(method)
                for method in cs_controller[self.current_cs].get("ia", [])
            ], columns=self.HEADERS)
        self.updated.emit()

    @staticmethod
    def build_row(method: tuple) -> dict:
        method_metadata = bw.methods[method]
        return {
            "Name": ', '.join(method),
            "Unit": method_metadata.get('unit', "Unknown"),
            "# CFs": method_metadata.get('num_cfs', 0),
            "method": method,
        }

    @Slot(list, name="deleteRows")
    def delete_rows(self, proxies: list) -> None:
        indices = (self.proxy_to_source(p) for p in proxies)
        rows = [i.row() for i in indices]
        self._dataframe = self._dataframe.drop(rows, axis=0).reset_index(drop=True)
        self.updated.emit()
        signals.calculation_setup_changed.emit()  # Trigger update of CS in brightway

    def include_methods(self, new_methods: Iterable) -> None:
        old_methods = set(self.methods)
        data = [self.build_row(m) for m in new_methods if m not in old_methods]
        if data:
            self._dataframe = pd.concat([self._dataframe, pd.DataFrame(data)], ignore_index=True)
            self.updated.emit()
            signals.calculation_setup_changed.emit()


class ScenarioImportModel(PandasModel):
    HEADERS = ["Scenario name"]

    def sync(self, names: list) -> None:
        self._dataframe = pd.DataFrame(names, columns=self.HEADERS)
        self.updated.emit()
