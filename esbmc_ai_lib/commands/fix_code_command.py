# Author: Yiannis Charalambous

from time import sleep


from .chat_command import ChatCommand
from .. import config
from ..msg_bus import Signal
from ..loading_widget import LoadingWidget
from ..esbmc_util import esbmc_load_source_code
from ..solution_generator import SolutionGenerator
from ..base_chat_interface import FINISH_REASON_LENGTH


class FixCodeCommand(ChatCommand):
    on_solution_signal: Signal = Signal()

    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )
        self.anim = LoadingWidget()
        wait_time: int = int(config.consecutive_prompt_delay)
        # Create time left animation to show how much time left between API calls
        # This is done by creating a list of all the numbers to be displayed and
        # setting the animation delay to 1 second.
        self.wait_anim = LoadingWidget(
            anim_speed=1,
            animation=[str(num) for num in range(wait_time, 0, -1)],
        )

    def execute(self, file_name: str, source_code: str, esbmc_output: str):
        solution_generator = SolutionGenerator(
            system_messages=config.chat_prompt_generator_mode.system_messages,
            initial_prompt=config.chat_prompt_generator_mode.initial_prompt,
            source_code=source_code,
            esbmc_output=esbmc_output,
            model=config.ai_model,
            temperature=config.code_fix_temperature,
        )

        print()

        max_retries: int = 10
        for idx in range(max_retries):
            # Get response.
            response: str = ""
            while True:
                # Generate AI solution
                self.anim.start("Generating Solution... Please Wait")
                response, finish_reason = solution_generator.generate_solution()
                self.anim.stop()
                if finish_reason == FINISH_REASON_LENGTH:
                    self.anim.start("Compressing message stack... Please Wait")
                    solution_generator.compress_message_stack()
                    self.anim.stop()
                else:
                    break

            # Pass to ESBMC, a workaround is used where the file is saved
            # to a temporary location since ESBMC needs it in file format.
            self.anim.start("Verifying with ESBMC... Please Wait")
            exit_code, esbmc_output = esbmc_load_source_code(
                file_path=file_name,
                source_code=str(response),
                esbmc_params=config.esbmc_params,
                auto_clean=config.temp_auto_clean,
            )
            self.anim.stop()

            if exit_code == 0:
                print("\n\nassistant: Here is the corrected code, verified with ESBMC:")
                print(f"```\n{response}\n```")

                self.on_solution_signal.emit(response)

                return False, response
            elif exit_code != 1:
                # The program did not compile.
                solution_generator.push_to_message_stack(
                    "user",
                    "The source code you provided does not compile.",
                )
                solution_generator.push_to_message_stack(
                    "assistant",
                    "OK. Show me the ESBMC output for additional assistance.",
                )

            # Failure case
            print(f"Failure {idx+1}/{max_retries}: Retrying...")
            # If final iteration no need to sleep.
            if idx < max_retries - 1:
                self.wait_anim.start(f"Sleeping due to rate limit:")
                sleep(config.consecutive_prompt_delay)
                self.wait_anim.stop()

                # Inform solution generator chat about the ESBMC response.
                solution_generator.push_to_message_stack(
                    "user",
                    f"Based on the source code provided, here is ESBMC output:\n\n{esbmc_output}",
                )

                solution_generator.push_to_message_stack("assistant", "Understood.")

        return True, "Failed all attempts..."
