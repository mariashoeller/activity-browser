# -*- coding: utf-8 -*-
from logging import getLogger

from bw2calc.errors import BW2CalcError
from PySide2.QtWidgets import QApplication

from ..bwutils import (MLCA, Contributions, # MonteCarloLCA,
                       SuperstructureContributions, SuperstructureMLCA)
from .errors import CriticalCalculationError, ScenarioExchangeNotFoundError

from activity_browser.mod import bw2data as bd
from uncertainty_lca import MonteCarloLCA

log = getLogger(__name__)


def do_LCA_calculations(data: dict):
    """Perform the MLCA calculation."""
    cs_name = data.get("cs_name", "new calculation")
    calculation_type = data.get("calculation_type", "simple")

    if calculation_type == "simple":
        try:
            mlca = MLCA(cs_name)
            contributions = Contributions(mlca)
        except KeyError as e:
            raise BW2CalcError("LCA Failed", str(e)).with_traceback(e.__traceback__)
    elif calculation_type == "scenario":
        try:
            df = data.get("data")
            mlca = SuperstructureMLCA(cs_name, df)
            contributions = SuperstructureContributions(mlca)
        except AssertionError as e:
            # This occurs if the superstructure itself detects something is wrong.
            QApplication.restoreOverrideCursor()
            raise BW2CalcError("Scenario LCA failed.", str(e)).with_traceback(
                e.__traceback__
            )
        except ValueError as e:
            # This occurs if the LCA matrix does not contain any of the
            # exchanges mentioned in the superstructure data.
            QApplication.restoreOverrideCursor()
            raise BW2CalcError(
                "Scenario LCA failed.",
                "Constructed LCA matrix does not contain any exchanges from the superstructure",
            ).with_traceback(e.__traceback__)
        except KeyError as e:
            QApplication.restoreOverrideCursor()
            raise BW2CalcError("LCA Failed", str(e)).with_traceback(e.__traceback__)
        except CriticalCalculationError as e:
            QApplication.restoreOverrideCursor()
            raise Exception(e)
        except ScenarioExchangeNotFoundError as e:
            QApplication.restoreOverrideCursor()
            raise CriticalCalculationError
    else:
        log.error(f"Calculation type must be: simple or scenario. Given: {cs_name}")
        raise ValueError

    mlca.calculate()
    
    demand = bd.calculation_setups[cs_name]["inv"][0] # todo: for now, this only works for the first functional unit due to the [0]
    methods = bd.calculation_setups[cs_name]["ia"]
    mc = MonteCarloLCA(demand, lcia_methods=methods)

    return mlca, contributions, mc
