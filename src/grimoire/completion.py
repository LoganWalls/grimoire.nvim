from typing import Iterable
from pynvim import Nvim

from .context import CodePosition
from . import namespace as ns

ACCEPT_COMMAND = "GrimoireAcceptCompletion"
PENDING_EVENT = "GrimoireCompletionPending"
FINISH_EVENT = "GrimoireCompletionFinish"
ACCEPT_EVENT = "GrimoireCompletionAccept"


class StreamingCompletion:
    start: CodePosition
    stream: Iterable[str]
    tokens: list[str]

    def __init__(
        self,
        vim: Nvim,
        start: CodePosition,
        stream: Iterable[str],
        hl_group: str = "LspInlayHint",
    ):
        self.start = start
        self.stream = stream
        self.tokens = []

        for token in stream:
            self.tokens.append(token)
            ns.completion.clear(vim)
            lines = [((line, hl_group),) for line in self.lines()]
            first_line = lines.pop(0)
            vim.api.buf_set_extmark(
                0,
                ns.completion.get(vim),
                start.row - 1,
                start.col,
                dict(
                    hl_mode="combine",
                    ephemeral=False,
                    virt_text=first_line,
                    virt_lines=lines,
                    virt_text_pos="inline",
                ),
            )
            vim.command("redraw")
        vim.api.exec_autocmds("User", dict(pattern=FINISH_EVENT))

    def lines(self) -> list[str]:
        return "".join(self.tokens).split("\n")

    def accept(self, vim: Nvim):
        row = self.start.row - 1
        lines = self.lines()
        cur_line = vim.api.buf_get_lines(0, row, row + 1, True)[0]
        lines[0] = cur_line + lines[0]

        ns.completion.clear(vim)
        vim.api.buf_set_lines(0, row, row + 1, True, lines)  # 1-indexed lines
        vim.api.win_set_cursor(  # 0-indexed lines, 1-index cols
            0, (row + len(lines), len(lines[-1]))
        )
        vim.command("redraw")
        vim.api.exec_autocmds("User", dict(pattern=ACCEPT_EVENT))
