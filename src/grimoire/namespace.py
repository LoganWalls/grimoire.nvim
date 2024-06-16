from dataclasses import dataclass
from typing import Optional
import typing
from pynvim import Nvim


@dataclass
class Namespace:
    name: str
    _id: Optional[int] = None

    def get(self, vim: Nvim) -> int:
        if self._id is None:
            self._id = typing.cast(int, vim.api.create_namespace(self.name))
        return self._id

    def clear(self, vim: Nvim, buffer: int = 0, start: int = 0, end: int = -1):
        vim.api.buf_clear_namespace(buffer, self.get(vim), start, end)


completion = Namespace("grimoire-preview")
