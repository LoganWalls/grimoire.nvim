from typing import Iterator, Optional
from openai.types.completion import Completion
import pynvim
from openai import OpenAI, Stream
from pynvim.api import Nvim
from grimoire.context import CodePosition, get_buffer_context
from grimoire.completion import StreamingCompletion
from grimoire import completion, namespace
from grimoire.keymap import Keymap


@pynvim.plugin
class Grimoire:
    vim: Nvim
    oai_client: OpenAI
    busy: bool
    accept_keymap: Keymap
    current_completion: Optional[StreamingCompletion]

    def __init__(self, nvim: Nvim):
        self.vim = nvim
        self.oai_client = OpenAI(
            api_key="sk-not-required",
            base_url="http://localhost:7777/v1",
        )
        self.busy = False
        self.accept_keymap = Keymap(
            self.vim, "i", "<CR>", f"<CMD>{completion.ACCEPT_COMMAND}<CR>"
        )
        self.current_completion = None

    @pynvim.command("RequestCompletion", nargs="?")
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
        prompt = f"""[SUFFIX]{after}[PREFIX]{before}"""
        stop = ["</s>", "[SUFFIX]"]
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
            model="codestral",
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

    @pynvim.autocmd("InsertLeave")
    def on_insert_leave(self):
        if self.current_completion is not None:
            namespace.completion.clear(self.vim)
        self.accept_keymap.unregister()
