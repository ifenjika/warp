import os

import pytest
from cli.encoding import get_evm_calldata
from starkware.starknet.compiler.compile import compile_starknet_files
from starkware.starknet.testing.state import StarknetState
from yul.main import transpile_from_solidity
from yul.starknet_utils import deploy_contract, invoke_method
from yul.utils import cairoize_bytes

warp_root = os.path.abspath(os.path.join(__file__, "../../.."))
test_dir = __file__


@pytest.mark.asyncio
async def test_calldatacopy():
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

    evm_calldata = get_evm_calldata(program_info["sol_abi"], "copyFourBytes", [0])
    [first_four_bytes], _ = cairoize_bytes(evm_calldata[:4])
    evm_calldata = get_evm_calldata(program_info["sol_abi"], "copyFourBytes", [4])
    [next_four_bytes], _ = cairoize_bytes(evm_calldata[4:8])

    res = await invoke_method(
        starknet, program_info, contract_address, "copyFourBytes", 0
    )
    assert res.retdata == [4, 1, first_four_bytes]

    res = await invoke_method(
        starknet, program_info, contract_address, "copyFourBytes", 4
    )
    assert res.retdata == [4, 1, next_four_bytes]
