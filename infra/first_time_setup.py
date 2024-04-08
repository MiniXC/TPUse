import os
from pathlib import Path

from dotenv import load_dotenv
from pyinfra import host
from pyinfra.operations import apt, server, files, git, pip
from pyinfra.facts.files import File
from pyinfra.facts.server import Home, Command

load_dotenv()
homedir = host.get_fact(Home)

# RAM POLICE
ram_police_host = host.get_fact(File, f"{homedir}/ram_police.sh")
if not ram_police_host:
    server.shell(
        name="Install & run ram police bash script",
        commands=[
            "wget https://gist.githubusercontent.com/MiniXC/47100a896d0d265aeb589b292919d744/raw/43e9f7dc9be3214945752e7dceca97b8ea6bc6e4/ram_police.sh",
            "chmod +x ram_police.sh",
            "./ram_police.sh",
        ],
    )


# GITHUB CONFIG
git.config(
    name="Configure github email",
    key="user.email",
    value=os.getenv("GH_EMAIL"),
)
git.config(
    name="Configure github name",
    key="user.name",
    value=os.getenv("GH_NAME"),
)


# SSH
ssh_key_path = os.getenv("SSH_KEY_PATH")
ssh_key_path = Path(ssh_key_path)
if ssh_key_path.parts[0] == "~":
    ssh_key_path = Path.home().joinpath(*ssh_key_path.parts[1:])
files.put(
    name=f"Write ssh key to file",
    src=ssh_key_path,
    dest=f"{homedir}/.ssh/{ssh_key_path.name}",
    mode="0600",
)
files.block(
    name="Add ssh key to ssh-agent",
    path=f"{homedir}/.bashrc",
    marker="## {mark} ssh ##",
    try_prevent_shell_expansion=True,
    content="\n".join(
        [
            'eval "$(ssh-agent -s)"',
            f"ssh-add ~/.ssh/{ssh_key_path.name}",
        ]
    ),
)


# ENVIRONMENT VARIABLES & ALIASES
files.block(
    name="Add environment variables & aliases",
    path=f"{homedir}/.bashrc",
    marker="## {mark} env ##",
    try_prevent_shell_expansion=True,
    before=True,  # this adds the block at the top of the file
    after=True,  # this adds the block at the top of the file
    content="\n".join(
        [
            f'export DISPLAYNAME="{host.name.split("/")[-1]}"',
            'export PS1="$USER:\\e[1;32m$DISPLAYNAME\\e[0m:\\e[1;34m\\W\\e[0m$ "',
            'export XRT_TPU_CONFIG="localservice;0;localhost:51011"',
            'export HF_HOME="/dev/shm/hf"',
            'export HF_DATASETS_PATH="/dev/shm/hf_datasets"',
            'export HF_DATASETS_CACHE="/dev/shm/hf_cache"',
            'export TOKENIZERS_PARALLELISM="false"',
            'alias python3="/usr/bin/python3"',
            'alias python="/usr/bin/python3"',
            'alias pip3="/usr/bin/pip3"',
            'alias pip="/usr/bin/pip"',
        ]
    ),
)


server.shell(
    name="Source .bashrc",
    commands=[
        f". {homedir}/.bashrc",
    ],
)


# TORCHAUDIO
apt.packages(
    name="Install sox, ffmpeg, libcairo2, libcairo2-dev, libsndfile1-dev",
    packages=["sox", "ffmpeg", "libcairo2", "libcairo2-dev", "libsndfile1-dev"],
    update=True,
    cache_time=3600,
    _sudo=True,
)
if os.getenv("PYTORCH_VERSION") == "1.10":
    pip.packages(
        name="Install torchaudio",
        packages=["torchaudio==0.10.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "1.11":
    pip.packages(
        name="Install torchaudio",
        packages=["torchaudio==0.11.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "1.12":
    pip.packages(
        name="Install torchaudio",
        packages=["torchaudio==0.12.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "1.13":
    pip.packages(
        name="Install torchaudio",
        packages=["torchaudio==0.13.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "2.0":
    pip.packages(
        name="Install torchaudio",
        packages=["torchaudio==2.0.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "2.1":
    pip.packages(
        name="Install torchaudio",
        packages=["torchaudio==2.1.0"],
        extra_install_args="--no-deps",
    )
else:
    raise ValueError("Invalid pytorch version")

# TORCHVISION
apt.packages(
    name="Install libjpeg-dev, zlib1g-dev",
    packages=["libjpeg-dev", "zlib1g-dev"],
    update=True,
    cache_time=3600,
    _sudo=True,
)
if os.getenv("PYTORCH_VERSION") == "1.10":
    pip.packages(
        name="Install torchvision",
        packages=["torchvision==0.11.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "1.11":
    pip.packages(
        name="Install torchvision",
        packages=["torchvision==0.12.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "1.12":
    pip.packages(
        name="Install torchvision",
        packages=["torchvision==0.13.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "1.13":
    pip.packages(
        name="Install torchvision",
        packages=["torchvision==0.14.0"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "2.0":
    pip.packages(
        name="Install torchvision",
        packages=["torchvision==0.15.1"],
        extra_install_args="--no-deps",
    )
elif os.getenv("PYTORCH_VERSION") == "2.1":
    pip.packages(
        name="Install torchvision",
        packages=["torchvision==0.16.0"],
        extra_install_args="--no-deps",
    )
else:
    raise ValueError("Invalid pytorch version")
