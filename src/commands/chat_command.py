# Author: Yiannis Charalambous

from abc import ABC, abstractmethod


class ChatCommand(ABC):
    command_name: str
    help_message: str

    def __init__(
        self,
        command_name: str = "",
        help_message: str = "",
    ) -> None:
        super().__init__()
        self.command_name = command_name
        self.help_message = help_message

    @abstractmethod
    def execute(self) -> None:
        pass
