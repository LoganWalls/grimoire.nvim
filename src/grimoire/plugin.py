from typing import Iterator

import pynvim
from openai import OpenAI, Stream
from openai.types.completion import Completion
from pydantic import BaseModel, Field
from pynvim.api import Nvim

from . import completion, namespace
from .completion import CompletionKind, CompletionStore, StreamingCompletion
from .context import CodePosition, get_buffer_context
from .keymap import Keymap, KeymapDict


class GrimoireKeys(BaseModel):
    accept_completion: str

    def to_keymaps(self, vim: Nvim) -> KeymapDict:
        return KeymapDict(
            {
                "accept_completion": Keymap(
                    vim,
                    "i",
                    self.accept_completion,
                    f"<CMD>{completion.ACCEPT_COMMAND}<CR>",
                )
            }
        )


class GrimoireOptions(BaseModel):
    host: str
    port: int
    initial_seed: int = Field(ge=0)
    max_variants: int = Field(ge=1)
    keys: GrimoireKeys


@pynvim.plugin
class GrimoirePlugin:
    vim: Nvim
    options: GrimoireOptions
    keymaps: KeymapDict
    completions: CompletionStore
    oai_client: OpenAI
    busy: bool

    def __init__(self, nvim: Nvim):
        self.vim = nvim
        self.options = GrimoireOptions.model_validate(
            self.vim.exec_lua("return require('grimoire').options")
        )
        self.keymaps = self.options.keys.to_keymaps(self.vim)
        self.completions = CompletionStore(
            self.options.initial_seed, self.options.max_variants
        )
        self.oai_client = OpenAI(
            api_key="sk-not-required",
            base_url=f"http://{self.options.host}:{self.options.port}/v1",
        )
        self.busy = False

    @pynvim.command("GrimoireRequestCompletion", nargs="?")
    def request_completion(self, args: list[CompletionKind]):
        if self.busy:
            self.vim.out_write(
                "Requested completion while another is pending - ignoring\n"
            )
            return
        self.busy = True

        kind = CompletionKind.line
        if len(args):
            kind = args[0]

        position = CodePosition.from_cursor(self.vim)
        before, after = get_buffer_context(self.vim, position)
        prompt = f"<｜fim▁begin｜>{before}<｜fim▁hole｜>{after}<｜fim▁end｜>"
        stop = ["<｜end▁of▁sentence｜>", "<｜fim▁begin｜>"]
        match kind:
            case "line":
                stop.append("\n")
            case "paragraph":
                stop.append("\n\n")
            case "block":
                stop.append("\n\n\n")
            case other:
                self.vim.err_write(
                    f"Unrecognized completion type '{other}' requested\n"
                )
        self.vim.api.exec_autocmds("User", dict(pattern=completion.PENDING_EVENT))
        stream = self.oai_client.completions.create(
            prompt=prompt,
            model="deepseek-coder-base",
            seed=self.completions.current_seed,
            top_p=0.9,
            temperature=0.1,
            max_tokens=200,
            stop=stop,
            stream=True,
        )

        def tokens(stream: Stream[Completion]) -> Iterator[str]:
            for chunk in stream:
                if (choices := chunk.choices) and (text := choices[0].text):
                    yield text

        if (
            prev_completion := self.completions.current_completion
        ) is not None and prev_completion.start != position:
            self.completions.reset()

        self.completions.current_completion = StreamingCompletion(
            self.vim,
            kind,
            position,
            tokens(stream),
        )

    @pynvim.command(completion.ACCEPT_COMMAND)
    def accept_completion(self):
        if self.completions.current_completion is None:
            self.vim.err_write("No completion available to accept\n")
            return

        self.completions.current_completion.accept(self.vim)

    def _change_variant(self, shift: int):
        kind = CompletionKind.default()
        if (prev_completion := self.completions.current_completion) is not None:
            namespace.completion.clear(self.vim)
            kind = prev_completion.kind
        self.completions.shift_seed(shift)
        self.vim.out_write(
            f"Completion {self.completions.index + 1}/{len(self.completions.seeds)}\n"
        )
        if (current_completion := self.completions.current_completion) is not None:
            current_completion.set_virtual_text(self.vim)
        else:
            self.request_completion([kind])

    @pynvim.command(completion.NEXT_VARIANT_COMMAND)
    def next_variant(self):
        self._change_variant(1)

    @pynvim.command(completion.PREV_VARIANT_COMMAND)
    def prev_variant(self):
        self._change_variant(-1)

    @pynvim.autocmd("User", pattern=completion.FINISH_EVENT)
    def on_completion_finish(self):
        self.busy = False
        self.keymaps.register()

    @pynvim.autocmd("User", pattern=completion.ACCEPT_EVENT)
    def on_completion_accepted(self):
        self.keymaps.unregister()

    @pynvim.autocmd("InsertLeave", pattern="*")
    def on_insert_leave(self):
        if self.completions.current_completion is not None:
            namespace.completion.clear(self.vim)
        self.keymaps.unregister()
