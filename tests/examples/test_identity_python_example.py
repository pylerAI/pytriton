#!/usr/bin/env python3
# Copyright (c) 2022, NVIDIA CORPORATION. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import logging
import re
import signal
import subprocess
import sys
import time

from tests.utils import (  # pytype: disable=import-error
    ScriptThread,
    get_current_container_version,
    verify_docker_image_in_readme_same_as_tested,
)

LOGGER = logging.getLogger("tests.examples.test_identity_python_example")

METADATA = {
    "image_name": "nvcr.io/nvidia/pytorch:{version}-py3",
}


def verify_client_output(client_output):
    input1_match = re.search(r"INPUT_1: (.*)", client_output, re.MULTILINE)
    input2_match = re.search(r"INPUT_2: (.*)", client_output, re.MULTILINE)
    output1_match = re.search(r"OUTPUT_1: (.*)", client_output, re.MULTILINE)
    output2_match = re.search(r"OUTPUT_2: (.*)", client_output, re.MULTILINE)
    input1_array = input1_match.group(1) if input1_match else None
    input2_array = input2_match.group(1) if input2_match else None
    output1_array = output1_match.group(1) if output1_match else None
    output2_array = output2_match.group(1) if output2_match else None
    if not input1_array or input1_array != output1_array:
        raise ValueError(f"input1_array: {input1_array} differs from output1_array: {output1_array}")
    if not input2_array or input2_array != output2_array:
        raise ValueError(f"input2_array: {input2_array} differs from output2_array: {output2_array}")
    LOGGER.info("Input and output arrays matches")


def main():
    parser = argparse.ArgumentParser(description="short_description")
    parser.add_argument("--timeout-s", required=False, default=300, type=float, help="Timeout for test")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s:%(name)s:%(levelname)s:%(message)s")

    docker_image_with_name = METADATA["image_name"].format(version=get_current_container_version())
    verify_docker_image_in_readme_same_as_tested("examples/identity_python//README.md", docker_image_with_name)

    subprocess.run(["bash", "examples/identity_python/install.sh"])

    start_time = time.time()
    elapsed_s = 0
    wait_time_s = min(args.timeout_s, 1)

    server_cmd = ["python", "examples/identity_python/server.py"]
    client_cmd = ["python", "examples/identity_python/client.py"]

    with ScriptThread(server_cmd, name="server") as server_thread:
        with ScriptThread(client_cmd, name="client") as client_thread:
            while server_thread.is_alive() and client_thread.is_alive() and elapsed_s < args.timeout_s:
                client_thread.join(timeout=wait_time_s)
                elapsed_s = time.time() - start_time

        LOGGER.info("Interrupting server script process")
        if server_thread.process:
            server_thread.process.send_signal(signal.SIGINT)

    if client_thread.returncode != 0:
        raise RuntimeError(f"Client returned {client_thread.returncode}")
    if server_thread.returncode not in [0, -2]:  # -2 is returned when process finished after receiving SIGINT signal
        raise RuntimeError(f"Server returned {server_thread.returncode}")

    timeout = elapsed_s >= args.timeout_s and client_thread.is_alive() and server_thread.is_alive()
    if timeout:
        LOGGER.error(f"Timeout occurred (timeout_s={args.timeout_s})")
        sys.exit(-2)
    verify_client_output(client_thread.output)


if __name__ == "__main__":
    main()
