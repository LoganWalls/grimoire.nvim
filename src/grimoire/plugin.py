from typing import Iterator, Optional
import random
from openai.types.completion import Completion
from pydantic import BaseModel
import pynvim
from openai import OpenAI, Stream
from pynvim.api import Nvim
from grimoire.context import CodePosition, get_buffer_context
from grimoire.completion import StreamingCompletion
from grimoire import completion, namespace
from grimoire.keymap import Keymap


class GrimoireKeys(BaseModel):
    accept_completion: str


class GrimoireOptions(BaseModel):
    host: str
    port: int
    initial_seed: int
    max_variants: int
    keys: GrimoireKeys


@pynvim.plugin
class GrimoirePlugin:
    vim: Nvim
    options: GrimoireOptions
    oai_client: OpenAI
    busy: bool
    accept_keymap: Keymap
    seeds: list[int]
    current_completion: Optional[StreamingCompletion]

    def __init__(self, nvim: Nvim):
        self.vim = nvim
        self.options = GrimoireOptions.model_validate(
            self.vim.exec_lua("return require('grimoire').options")
        )
        self.oai_client = OpenAI(
            api_key="sk-not-required",
            base_url=f"http://{self.options.host}:{self.options.port}/v1",
        )
        self.busy = False
        self.accept_keymap = Keymap(
            self.vim,
            "i",
            self.options.keys.accept_completion,
            f"<CMD>{completion.ACCEPT_COMMAND}<CR>",
        )
        random.seed(self.options.initial_seed)
        self.seeds = [
            random.randint(0, 999999) for _ in range(self.options.max_variants)
        ]
        self.current_completion = None

    @pynvim.command("GrimoireRequestCompletion", nargs="?")
    def request_completion(self, args: list):
        if self.busy:
            self.vim.out_write(
                "Requested completion while another is pending - ignoring\n"
            )
            return
        self.busy = True

        kind = "line"
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
            seed=1234,
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

        self.current_completion = StreamingCompletion(
            self.vim,
            position,
            tokens(stream),
        )

    @pynvim.command(completion.ACCEPT_COMMAND)
    def accept_completion(self):
        if self.current_completion is None:
            self.vim.err_write("No completion available to accept\n")
            return

        self.current_completion.accept(self.vim)

    @pynvim.autocmd("User", pattern=completion.FINISH_EVENT)
    def on_completion_finish(self):
        self.busy = False
        self.accept_keymap.register()

    @pynvim.autocmd("User", pattern=completion.ACCEPT_EVENT)
    def on_completion_accepted(self):
        self.accept_keymap.unregister()

    @pynvim.autocmd("InsertLeave", pattern="*")
    def on_insert_leave(self):
        if self.current_completion is not None:
            namespace.completion.clear(self.vim)
        self.accept_keymap.unregister()
