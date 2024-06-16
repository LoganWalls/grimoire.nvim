from typing import Self
from pydantic import BaseModel
from pynvim import Nvim


class CodePosition(BaseModel):
    """Identifies a position within a file"""

    row: int
    col: int

    @classmethod
    def from_cursor(cls, vim: Nvim) -> Self:
        row, col = vim.api.win_get_cursor(0)
        return cls(row=row, col=col)


class CodeLocation(BaseModel):
    """Identifies a unique location in code"""

    uri: str
    """The URI of the file containing location"""

    position: CodePosition
    """The position inside the file indicated by `uri`"""

    @classmethod
    def from_cursor(cls, vim: Nvim) -> Self:
        uri = vim.funcs.uri_from_bufnr(0)
        return cls(uri=uri, position=CodePosition.from_cursor(vim))


def get_buffer_context(vim: Nvim, position: CodePosition) -> tuple[str, str]:
    lines = vim.api.buf_get_lines(0, 0, -1, False)
    row = position.row - 1  # row position is 1-indexed
    col = position.col
    current_line = lines[row]
    before = "\n".join(lines[:row] + [current_line[:col]])
    after = "\n".join([current_line[col:]] + lines[row + 1 :])
    return before, after
