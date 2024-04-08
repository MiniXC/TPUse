import os
from pathlib import Path
from time import sleep

from dotenv import load_dotenv
from pyinfra import host
from pyinfra.operations import apt, server, files, git, pip
from pyinfra.facts.files import File
from pyinfra.facts.server import Home, Command

load_dotenv()

output = host.get_fact(Command, "tmux capture-pane -pet exp")
print(output)
