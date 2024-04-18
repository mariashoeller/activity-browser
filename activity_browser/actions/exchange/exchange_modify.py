from typing import Union, Callable, Any

from PySide2 import QtCore

from ..base import ABAction
from ...ui.icons import qicons


class ExchangeModify(ABAction):
    """
    ABAction to modify an exchange with the supplied data.
    """
    icon = qicons.delete
    title = "Delete exchange(s)"
    exchange: Any
    data_: dict

    def __init__(self, exchange: Union[Any, Callable], data: Union[dict, callable], parent: QtCore.QObject):
        super().__init__(parent, exchange=exchange, data_=data)

    def onTrigger(self, toggled):
        for key, value in self.data_.items():
            self.exchange[key] = value

        self.exchange.save()
