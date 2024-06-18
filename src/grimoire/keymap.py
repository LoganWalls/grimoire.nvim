from dataclasses import dataclass
from typing import Optional
from pynvim import Nvim


@dataclass
class Keymap:
    vim: Nvim
    mode: str
    lhs: str
    rhs: str
    is_set: bool = False

    def register(self, buffer: int = 0, options: Optional[dict] = None):
        if self.is_set:
            return

        opts = dict(silent=True, noremap=True)
        if options:
            opts.update(options)
        self.vim.api.buf_set_keymap(buffer, self.mode, self.lhs, self.rhs, opts)
        self.is_set = True

    def unregister(self, buffer: int = 0):
        if self.is_set:
            self.vim.api.buf_del_keymap(buffer, "i", self.lhs)
            self.is_set = False


class KeymapDict(dict[str, Keymap]):
    def register(self, buffer: int = 0, options: Optional[dict] = None):
        for v in self.values():
            v.register(buffer=buffer, options=options)

    def unregister(self, buffer: int = 0):
        for v in self.values():
            v.unregister(buffer=buffer)
