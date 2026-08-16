from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from docker_broker.config import Settings


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["/usr/bin/git", "init", "--quiet", str(path)], check=True)
    return path.resolve()


@pytest.fixture
def fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "docker-argv.jsonl"
    executable = tmp_path / "docker"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"log = pathlib.Path({str(log)!r})\n"
        "with log.open('a') as stream: stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "args = sys.argv[1:]\n"
        "def merge(left, right):\n"
        " for key, value in right.items():\n"
        "  if isinstance(value, dict) and isinstance(left.get(key), dict): merge(left[key], value)\n"
        "  else: left[key] = value\n"
        "if args and args[0] == 'version': print('29.0.0')\n"
        "elif args[:2] == ['compose', 'version']: print('5.3.1')\n"
        "elif args and args[0] == 'inspect':\n"
        " print(json.dumps([{'Name':'/backend-langgraph-api-1','Config':{'Image':'jasper-langgraph:current','Env':['SECRET=hidden']},'State':{'Status':'running','Health':{'Status':'healthy'}},'HostConfig':{'Privileged':False,'NetworkMode':'backend_default'},'Platform':'linux','NetworkSettings':{'Ports':{'8000/tcp':[{'HostIp':'127.0.0.1','HostPort':'8123'}]},'Networks':{'backend_default':{}}},'Mounts':[{'Type':'bind','Source':'/private/secret','Destination':'/workspace','RW':True}]}]))\n"
        "elif args and args[0] == 'compose' and 'config' in args:\n"
        " files = [pathlib.Path(args[index + 1]) for index, item in enumerate(args) if item == '--file']\n"
        " model = {}\n"
        " for path in files: merge(model, json.loads(path.read_text()))\n"
        " for service in model.get('services', {}).values():\n"
        "  memory = service.get('mem_limit')\n"
        "  if isinstance(memory, str) and memory.lower().endswith('g'): service['mem_limit'] = int(memory[:-1]) * 1024**3\n"
        "  if 'cpus' in service: service['cpus'] = float(service['cpus'])\n"
        "  normalized_ports = []\n"
        "  for port in service.get('ports', []):\n"
        "   if isinstance(port, str):\n"
        "    host, published, target = port.split(':')\n"
        "    normalized_ports.append({'host_ip':host,'published':published,'target':int(target),'protocol':'tcp'})\n"
        "   else: normalized_ports.append(port)\n"
        "  if normalized_ports: service['ports'] = normalized_ports\n"
        "  normalized_volumes = []\n"
        "  for volume in service.get('volumes', []):\n"
        "   if isinstance(volume, str):\n"
        "    parts = volume.split(':')\n"
        "    normalized_volumes.append({'type':'volume','source':parts[0],'target':parts[1]})\n"
        "   else: normalized_volumes.append(volume)\n"
        "  if normalized_volumes: service['volumes'] = normalized_volumes\n"
        " print(json.dumps(model))\n"
        "elif args and args[0] == 'compose' and 'ps' in args: print('[]')\n"
        "sys.exit(0)\n"
    )
    os.chmod(executable, 0o700)
    return executable, log


@pytest.fixture
def settings(
    repository: Path, fake_docker: tuple[Path, Path], tmp_path: Path
) -> Settings:
    executable, _ = fake_docker
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    return Settings(
        allowed_roots=(repository,),
        state_directory=state,
        agent_server_url="http://127.0.0.1:8123",
        owner_id="owner-one",
        docker_path=executable,
        client_secret="test-client-secret-" + "x" * 48,
        allow_builds=True,
    )
