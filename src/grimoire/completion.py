from enum import Enum
import random
from typing import Iterable

from pynvim import Nvim

from . import namespace as ns
from .context import CodePosition

ACCEPT_COMMAND = "GrimoireAcceptCompletion"
NEXT_VARIANT_COMMAND = "GrimoireNextVariant"
PREV_VARIANT_COMMAND = "GrimoirePrevVariant"

PENDING_EVENT = "GrimoireCompletionPending"
FINISH_EVENT = "GrimoireCompletionFinish"
ACCEPT_EVENT = "GrimoireCompletionAccept"


class CompletionKind(Enum):
    line = "line"
    paragraph = "paragraph"
    block = "block"
    until_stop = "until_stop"

    @classmethod
    def default(cls) -> "CompletionKind":
        return cls.until_stop


class StreamingCompletion:
    kind: CompletionKind
    start: CodePosition
    stream: Iterable[str]
    tokens: list[str]

    def __init__(
        self,
        vim: Nvim,
        kind: CompletionKind,
        start: CodePosition,
        stream: Iterable[str],
        hl_group: str = "LspInlayHint",
    ):
        self.kind = kind
        self.start = start
        self.stream = stream
        self.tokens = []
        for token in stream:
            self.tokens.append(token)
            self.set_virtual_text(vim, hl_group=hl_group)
        vim.api.exec_autocmds("User", dict(pattern=FINISH_EVENT))

    def set_virtual_text(self, vim: Nvim, hl_group: str = "LspInlayHint"):
        ns.completion.clear(vim)
        lines = [((line, hl_group),) for line in self.lines()]
        first_line = lines.pop(0)
        vim.api.buf_set_extmark(
            0,
            ns.completion.get(vim),
            self.start.row - 1,
            self.start.col,
            dict(
                hl_mode="combine",
                ephemeral=False,
                virt_text=first_line,
                virt_lines=lines,
                virt_text_pos="inline",
            ),
        )
        vim.command("redraw")

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


class CompletionStore:
    seeds: list[int]
    index: int
    completions: dict[int, StreamingCompletion]

    def __init__(self, initial_seed: int, max_variants: int):
        self.completions = {}
        random.seed(initial_seed)
        self.seeds = [random.randint(0, 999999) for _ in range(max_variants)]
        self.index = 0

    @property
    def current_seed(self) -> int:
        return self.seeds[self.index]

    @property
    def current_completion(self) -> StreamingCompletion | None:
        return self.completions.get(self.current_seed)

    @current_completion.setter
    def current_completion(self, completion: StreamingCompletion):
        self.completions[self.current_seed] = completion

    def shift_seed(self, shift: int):
        self.index = (self.index + shift) % len(self.seeds)

    def reset(self):
        self.index = 0
        self.completions = {}
