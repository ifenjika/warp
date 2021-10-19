import json
import os
import subprocess
from http import HTTPStatus
from typing import Any, Dict, Optional, Union

import aiohttp
from cli.StarkNetEvmContract import get_evm_calldata
from eth_hash.auto import keccak
from starkware.starknet.definitions import fields
from starkware.starknet.services.api.contract_definition import ContractDefinition
from starkware.starknet.services.api.gateway.transaction import (
    Deploy,
    InvokeFunction,
    Transaction,
)
from transpiler.utils import cairoize_bytes

WARP_ROOT = os.path.abspath(os.path.join(__file__, "../.."))
artifacts_dir = os.path.join(os.path.abspath("."), "artifacts")


def get_selector_cairo(args: str) -> int:
    return int.from_bytes(keccak(args.encode("ascii")), "big") & (2 ** 250 - 1)


async def send_req(method, url, tx: Optional[Union[str, Dict[str, Any]]] = None):
    if tx is not None:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method, url=url, data=Transaction.Schema().dumps(obj=tx)
            ) as response:
                text = await response.text()
                return text
    else:
        async with aiohttp.ClientSession() as session:
            async with session.request(method=method, url=url, data=None) as response:
                text = await response.text()
                return text


# returns true/false on transaction success/failure
async def _invoke(source_name, address, function, cairo_inputs, evm_inputs):
    with open(os.path.join(artifacts_dir, "MAIN_CONTRACT")) as f:
        main_contract = f.read()
    evm_calldata = get_evm_calldata(source_name, main_contract, function, evm_inputs)
    cairo_input, unused_bytes = cairoize_bytes(bytes.fromhex(evm_calldata[2:]))
    calldata_size = (len(cairo_input) * 16) - unused_bytes
    function = "fun_" + function + "_external"

    with open(os.path.abspath(os.path.join(artifacts_dir, ".DynArgFunctions"))) as f:
        dynArgFunctions = f.readlines()

    try:
        address = int(address, 16)
    except ValueError:
        raise ValueError("Invalid address format.")

    if function in dynArgFunctions:
        selector = get_selector_cairo("fun_ENTRY_POINT")
        calldata = [calldata_size, unused_bytes, len(cairo_input)] + cairo_input
    else:
        selector = get_selector_cairo(function)
        calldata = cairo_inputs

    tx = InvokeFunction(
        contract_address=address, entry_point_selector=selector, calldata=calldata
    )

    response = await send_req(
        method="POST", url="https://alpha2.starknet.io/gateway/add_transaction", tx=tx
    )
    tx_id = json.loads(response)["tx_id"]
    print(
        f"""\
Invoke transaction was sent.
Contract address: 0x{address:064x}.
Transaction ID: {tx_id}."""
    )
    return True


async def _call(address, abi, function, inputs) -> bool:
    with open(abi) as f:
        abi = json.load(f)

    try:
        address = int(address, 16)
    except ValueError:
        raise ValueError("Invalid address format.")

    selector = get_selector_cairo(function)
    calldata = inputs
    tx = InvokeFunction(
        contract_address=address, entry_point_selector=selector, calldata=calldata
    )

    url = "https://alpha2.starknet.io/feeder_gateway/call_contract?blockId=null"
    async with aiohttp.ClientSession() as session:
        async with session.request(method="POST", url=url, data=tx.dumps()) as response:
            raw_resp = await response.text()
            resp = json.loads(raw_resp)
        return resp["result"][0]


def starknet_compile(contract):
    compiled = os.path.join(artifacts_dir, f"{contract[:-6]}_compiled.json")
    abi = os.path.join(artifacts_dir, f"{contract[:-6]}_abi.json")
    process = subprocess.Popen(
        [
            "starknet-compile",
            "--disable_hint_validation",
            f"{contract}",
            "--output",
            compiled,
            "--abi",
            abi,
            "--cairo_path",
            f"{WARP_ROOT}/cairo-src",
        ]
    )
    output = process.wait()
    if output == 1:
        raise Exception("Compilation failed")
    return compiled, abi


async def _deploy(contract_path):
    contract_name = contract_path[:-6]
    compiled_contract, abi = starknet_compile(contract_path)
    address = fields.ContractAddressField.get_random_value()
    with open(compiled_contract) as f:
        cont = f.read()

    contract_definition = ContractDefinition.loads(cont)
    url = "https://alpha2.starknet.io/gateway/add_transaction"
    tx = Deploy(contract_address=address, contract_definition=contract_definition)

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method="POST", url=url, data=Transaction.Schema().dumps(obj=tx)
        ) as response:
            text = await response.text()
            if response.status != HTTPStatus.OK:
                print("FAIL")
                print(response)

            tx_id = json.loads(text)["tx_id"]
            print(
                f"""\
Deploy transaction was sent.
Contract address: 0x{address:064x}.
Transaction ID: {tx_id}.

Contract Address Has Been Written to {os.path.abspath(contract_name)}_ADDRESS.txt
"""
            )
    with open(f"{os.path.abspath(contract_name)}_ADDRESS.txt", "w") as f:
        f.write(f"0x{address:064x}")
    return f"0x{address:064x}"


async def _status(tx_id):
    status = f"https://alpha2.starknet.io/feeder_gateway/get_transaction_status?transactionId={tx_id}"
    res = await send_req("GET", status)
    print(json.loads(res))
