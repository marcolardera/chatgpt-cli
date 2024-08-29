from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings


def create_keybindings(multiline: bool = False):
    kb = KeyBindings()

    @kb.add("escape", "enter", filter=Condition(lambda: multiline))
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    @kb.add("enter", filter=Condition(lambda: not multiline))
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    return kb
