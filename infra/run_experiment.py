import os
from pathlib import Path

from dotenv import load_dotenv
from pyinfra import host
from pyinfra.operations import apt, server, files, git, pip
from pyinfra.facts.files import File
from pyinfra.facts.server import Home, Command
from yaml import safe_load

load_dotenv()

homedir = host.get_fact(Home)
hostname = host.name.split(".")[0].split("/")[-1]


def get_num_tpus():
    ip = host.get_fact(Command, "curl https://ipinfo.io/ip")
    ip = ip.strip().replace(".local", "")
    zone = host.get_fact(
        Command,
        "curl http://metadata.google.internal/computeMetadata/v1/instance/zone -H Metadata-Flavor:Google | cut '-d/' -f4",
    )
    tpu_list = host.get_fact(
        Command,
        f"gcloud compute tpus tpu-vm list --zone={zone} --format=yaml",
    ).split("---")
    for tpu in tpu_list:
        if ip in tpu:
            accelerator_type = safe_load(tpu)["acceleratorType"]
            break
    return accelerator_type.split("-")[1]


num_tpu_cores = get_num_tpus()

# kill any python processes running in the session
server.shell(
    name="Kill existing python processes",
    commands=[
        'pgrep -u $UID -f ".*python.*" | xargs -r kill',
    ],
)

# check if a tmux session called "exp" exists
tmux_session = host.get_fact(Command, "tmux ls")
if "exp:" in tmux_session:
    # an experiment session already exists
    if os.getenv("FORCE") is None:
        print("An experiment session already exists")
        exit(0)
    else:
        # kill the existing session
        server.shell(
            name="Kill existing experiment session",
            commands=[
                "tmux kill-session -t exp",
            ],
        )

git_status = host.get_fact(Command, f"cd {homedir}/experiments && git status")

if "nothing to commit" not in git_status:
    if os.getenv("FORCE") is None:
        print("There are uncommitted changes in the repo")
        exit(0)
    else:
        print("Discarding uncommitted changes")
        server.shell(
            name="Discard uncommitted changes",
            commands=[
                f"cd {homedir}/experiments && git reset --hard HEAD",
            ],
        )
        print("Removing untracked files")
        server.shell(
            name="Remove untracked files",
            commands=[
                f"cd {homedir}/experiments && git clean -df",
            ],
        )

# clone git repo specified in .env
git_repo = os.getenv("GH_REPO")
git.repo(
    name="Clone repo",
    src=git_repo,
    dest=f"{homedir}/experiments",
    pull=True,
)

# install requirements
pip.packages(
    name="Install requirements",
    requirements=f"{homedir}/experiments/requirements.txt",
)

# copy the config file to the experiments directory
config_file = Path(os.getenv("CONFIG_PATH")) / f"{hostname}.yaml"
print(f"Copying config file: {config_file}")
files.put(
    name="Copy config file",
    src=config_file,
    dest=f"{homedir}/experiments/configs/config.yaml",
    force=True,
)

# "accelerate launch" with the config file in a tmux session
server.shell(
    name="Launch experiment",
    commands=[
        "tmux new-session -d -s exp",
        f"tmux send-keys -t exp 'cd {homedir}/experiments' Enter",
        f"tmux send-keys -t exp 'accelerate launch --tpu --num_processes {num_tpu_cores} scripts/train.py' Enter",
    ],
)
