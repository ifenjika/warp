import os

import pytest
from starkware.starknet.compiler.compile import compile_starknet_files
from starkware.starknet.testing.state import StarknetState
from yul.main import transpile_from_solidity
from yul.starknet_utils import invoke_method

warp_root = os.path.abspath(os.path.join(__file__, "../../.."))
test_dir = __file__


@pytest.mark.asyncio
async def test_starknet():
    solidity_file = test_dir[:-8] + ".sol"
    contract_file = test_dir[:-8] + ".cairo"
    contract_info = transpile_from_solidity(solidity_file, "WARP")
    cairo_path = f"{warp_root}/warp/cairo-src"
    contract_definition = compile_starknet_files(
        [contract_file], debug_info=True, cairo_path=[cairo_path]
    )

    starknet = await StarknetState.empty()
    contract_address = await starknet.deploy(
        contract_definition=contract_definition, constructor_calldata=[]
    )

    res = await invoke_method(starknet, contract_info, contract_address, "returnFun")
    assert res.retdata == [1, 96, 6, 0, 32, 0, 3, 0x41424300000000000000000000000000, 0]

    res = await invoke_method(starknet, contract_info, contract_address, "bytesFun")
    assert res.retdata == [1, 96, 6, 0, 32, 0, 3, 0x41424300000000000000000000000000, 0]
