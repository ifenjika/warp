import os

import pytest
import pytest_check as check
from starkware.starknet.compiler.compile import compile_starknet_files
from starkware.starknet.testing.state import StarknetState
from yul.main import transpile_from_solidity
from yul.starknet_utils import deploy_contract, invoke_method

from warp.logging.generateMarkdown import steps_in_function

warp_root = os.path.abspath(os.path.join(__file__, "../../.."))
test_dir = __file__


@pytest.mark.asyncio
async def test_starknet():
    contract_file = test_dir[:-8] + ".cairo"
    sol_file = test_dir[:-8] + ".sol"
    program_info = transpile_from_solidity(sol_file, "WARP")
    cairo_path = f"{warp_root}/warp/cairo-src"
    contract_definition = compile_starknet_files(
        [contract_file], debug_info=True, cairo_path=[cairo_path]
    )

    starknet = await StarknetState.empty()
    contract_address = await deploy_contract(
        starknet, program_info, contract_definition
    )
    sender = 74
    receiver = 68

    res = await invoke_method(
        starknet, program_info, contract_address, "deposit", sender, 500
    )
    steps_in_function(sol_file, "deposit", res, "ERC20_storage_test")
    check.equal(res.retdata, [0, 0])

    res = await invoke_method(
        starknet,
        program_info,
        contract_address,
        "transferFrom",
        *[sender, receiver, 400, sender],
    )
    steps_in_function(sol_file, "transferFrom", res, "ERC20_storage_test")
    check.equal(res.retdata, [32, 2, 0, 1])

    res = await invoke_method(
        starknet, program_info, contract_address, "withdraw", 80, sender
    )
    steps_in_function(sol_file, "withdraw", res, "ERC20_storage_test")
    check.equal(res.retdata, [0, 0])

    res = await invoke_method(
        starknet, program_info, contract_address, "get_balance", sender
    )
    steps_in_function(sol_file, "get_balance", res, "ERC20_storage_test")
    check.equal(res.retdata, [32, 2, 0, 20])

    res = await invoke_method(
        starknet, program_info, contract_address, "get_balance", receiver
    )
    steps_in_function(sol_file, "get_balance", res, "ERC20_storage_test")
    check.equal(res.retdata, [32, 2, 0, 400])
