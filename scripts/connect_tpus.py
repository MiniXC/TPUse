from typing import List
from subprocess import run
import subprocess
from time import sleep
import yaml
import os
import getpass

import hydra
from omegaconf import DictConfig
from rich import print

os.environ["HYDRA_FULL_ERROR"] = "1"

sudo_password = None


def parse_tpu_list(output: str) -> List[str]:
    tpu_names = []
    tpu_types = []
    tpu_states = []
    for line in output.split("\n"):
        cols = line.split()
        if len(cols) > 0 and cols[0] != "NAME":
            tpu_names.append(cols[0])
            tpu_types.append(cols[2])
            tpu_states.append(cols[5])
    result = list(zip(tpu_names, tpu_types, tpu_states))
    try:
        return sorted(result, key=lambda x: int(x[0].split("-")[1]))
    except ValueError:
        raise ValueError("TPU names should be in the format v2-<number>")


def check_tpus(
    version: int,
    zone: str,
    num_vms: int,
    num_cores: int,
    create_missing: bool = False,
    pt_version: int = "1.13",
) -> bool:
    # check if TPUs are already created and running
    command = f"gcloud compute tpus list --zone={zone}"
    result = run(command, shell=True, check=True, capture_output=True)
    if result.stdout:
        tpus = parse_tpu_list(result.stdout.decode("utf-8"))
        # check if there are enough TPUs
        # if they have the correct number of cores
        # if they are in the correct state
        # if they are named in the schema v<version>-<number>
        if len(tpus) < num_vms and not create_missing:
            print(
                f"Expected {num_vms} TPUs, found {len(tpus)}: {tpus}, pass general.create_missing to create missing TPUs"
            )
        elif len(tpus) < num_vms and create_missing:
            # check which numbers are missing
            existing_numbers = [
                int(tpu[0].split("-")[1]) for tpu in tpus if tpu[-1] == "READY"
            ]
            missing_numbers = [
                i for i in range(1, num_vms + 1) if i not in existing_numbers
            ]
            print(
                f"Missing TPUs: {[f'v{version}-{i}' for i in missing_numbers]}, creating them now"
            )
            for number in missing_numbers:
                if version == 4:
                    version_str = f"tpu-vm-v4-pt-{pt_version}"
                else:
                    version_str = f"tpu-vm-pt-{pt_version}"
                name = f"v{version}-{number}"
                accelerator_type = f"v{version}-{num_cores}"
                command = f"gcloud compute tpus tpu-vm create {name} --zone={zone} --accelerator-type={accelerator_type} --version={version_str}"
                run_create_command(command)
        final_tpus = []
        for i, (tpu, tpu_type, tpu_state) in enumerate(tpus):
            add = True
            if tpu_type != f"v{version}-{num_cores}":
                print(
                    f"[red]TPU {tpu} has incorrect number of cores: {tpu_type}, expected v{version}-{num_cores}[/red]"
                )
                add = False
            if tpu_state != "READY":
                print(f"[red]TPU {tpu} is not ready: {tpu_state}[/red]")
                add = False
            if tpu != f"v{version}-{i+1}":
                print(
                    f"[red]TPU {tpu} is not named correctly, expected v{version}-{i+1}[/red]"
                )
                add = False
            if add:
                final_tpus.append(tpu)
        return final_tpus


def run_create_command(command: str) -> None:
    while True:
        result = run(command, shell=True, check=False, capture_output=True)
        if result.returncode == 0:
            break
        else:
            print(command)
            print(f"Error creating TPUs: {result.stderr.decode('utf-8')}")
            sleep(1)


def setup_external_ips(zone: str, extension: str) -> None:
    global sudo_password
    # get external IPs
    command = f"gcloud compute tpus tpu-vm list --zone={zone} --format=yaml"
    result = run(command, shell=True, check=True, capture_output=True)
    # key is .networkEndpoints[0].accessConfig.externalIp
    results = [
        yaml.safe_load(r.strip())
        for r in result.stdout.decode("utf-8").split("---")
        if r.strip()
    ]
    results = [
        (
            r["name"].split("/")[-1],
            r["networkEndpoints"][0]["accessConfig"]["externalIp"],
        )
        for r in results
    ]
    # we need to ask for sudo password
    if not sudo_password:
        sudo_password = getpass.getpass(
            "Enter your sudo password, to modify /etc/hosts: "
        )
    p = subprocess.Popen(
        f"sudo bash -c 'echo \"# {zone} TPUs\" >> /etc/hosts'",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, err = p.communicate(sudo_password.encode(), timeout=5)
    if err:
        print(f"Error adding comment to /etc/hosts: {err.decode('utf-8')}")
    for name, ip in results:
        # remove from /etc/hosts if it already exists there
        # sudo sed -i "/<name>/d" /etc/hosts
        p = subprocess.Popen(
            f"sudo sed -i '' '/{name}/d' /etc/hosts",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, err = p.communicate(sudo_password.encode(), timeout=5)
        if err:
            print(f"Error removing {name} from /etc/hosts: {err.decode('utf-8')}")
        # add to /etc/hosts
        # sudo echo "<ip> <extension>-<number>" >> /etc/hosts
        p = subprocess.Popen(
            f"sudo bash -c 'echo \"{ip} {name}.{extension}\" >> /etc/hosts'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, err = p.communicate(sudo_password.encode(), timeout=5)
        if err:
            print(f"Error adding {name} to /etc/hosts: {err.decode('utf-8')}")

    # ssh-keygen -R <ip>
    for name, ip in results:
        result = run(
            f"ssh-keygen -R {ip}",
            shell=True,
            check=False,
            capture_output=True,
        )
        result = run(
            f"ssh-keygen -R {name}.{extension}",
            shell=True,
            check=False,
            capture_output=True,
        )
        # add to known_hosts
        result = run(
            f"ssh-keyscan -H -t rsa {name}.{extension} >> ~/.ssh/known_hosts",
            shell=True,
            check=False,
        )


@hydra.main(config_path="../config", config_name="tpus", version_base=None)
def setup_tpus(cfg: DictConfig) -> None:
    if hasattr(cfg, "v2"):
        v2_zone = cfg.v2.zone
        v2_num_vms = cfg.v2.num_vms
        v2_num_cores = cfg.v2.cores_per_vm
        if not check_tpus(
            2,
            v2_zone,
            v2_num_vms,
            v2_num_cores,
            cfg.general.create_missing,
            cfg.general.pt_version,
        ):
            # create v2 TPUs
            version = f"tpu-vm-pt-{cfg.general.pt_version}"
            command = f"gcloud compute tpus tpu-vm create {cfg.v2.name} --zone={v2_zone} --accelerator-type={cfg.v2.accelerator_type} --version={version}"
            run_create_command(command)
        else:
            print("v2 TPUs are already running")
            print("Setting up external IPs")
            setup_external_ips(v2_zone, cfg.general.extension)

    if hasattr(cfg, "v3"):
        v3_zone = cfg.v3.zone
        v3_num_vms = cfg.v3.num_vms
        v3_num_cores = cfg.v3.cores_per_vm
        if not check_tpus(
            3,
            v3_zone,
            v3_num_vms,
            v3_num_cores,
            cfg.general.create_missing,
            cfg.general.pt_version,
        ):
            # create v3 TPUs
            version = f"tpu-vm-pt-{cfg.general.pt_version}"
            command = f"gcloud compute tpus tpu-vm create {cfg.v3.name} --zone={v3_zone} --accelerator-type={cfg.v3.accelerator_type} --version={version}"
            run_create_command(command)
        else:
            print("v3 TPUs are already running")
            print("Setting up external IPs")
            setup_external_ips(v3_zone, cfg.general.extension)

    if hasattr(cfg, "v4"):
        v4_zone = cfg.v4.zone
        v4_num_vms = cfg.v4.num_vms
        v4_num_cores = cfg.v4.cores_per_vm
        if not check_tpus(
            4,
            v4_zone,
            v4_num_vms,
            v4_num_cores,
            cfg.general.create_missing,
            cfg.general.pt_version,
        ):
            # create v4 TPUs
            version = f"tpu-vm-v4-pt-{cfg.general.pt_version}"
            command = f"gcloud compute tpus tpu-vm create {cfg.v4.name} --zone={v4_zone} --accelerator-type={cfg.v4.accelerator_type} --version={version}"
            run_create_command(command)
        else:
            print("v4 TPUs are already running")
            print("Setting up external IPs")
            setup_external_ips(v4_zone, cfg.general.extension)


if __name__ == "__main__":
    setup_tpus()
