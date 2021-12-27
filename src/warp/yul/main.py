from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import warp.yul.ast as ast
from warp.yul.BuiltinHandler import get_default_builtins
from warp.yul.ConstantFolder import ConstantFolder
from warp.yul.DeadcodeEliminator import DeadcodeEliminator
from warp.yul.ExpressionSplitter import ExpressionSplitter
from warp.yul.FoldIf import FoldIf
from warp.yul.ForLoopEliminator import ForLoopEliminator
from warp.yul.ForLoopSimplifier import ForLoopSimplifier
from warp.yul.FunctionGenerator import CairoFunctions, FunctionGenerator
from warp.yul.FunctionPruner import FunctionPruner
from warp.yul.LeaveNormalizer import LeaveNormalizer
from warp.yul.NameGenerator import NameGenerator
from warp.yul.parse_object import parse_to_normalized_ast
from warp.yul.Renamer import MangleNamesVisitor
from warp.yul.RevertNormalizer import RevertNormalizer
from warp.yul.ScopeFlattener import ScopeFlattener
from warp.yul.SwitchToIfVisitor import SwitchToIfVisitor
from warp.yul.ToCairoVisitor import ToCairoVisitor
from warp.yul.utils import get_for_contract
from warp.yul.VariableInliner import VariableInliner
from warp.yul.WarpException import warp_assert

AST_GENERATOR = "kudu"


def transpile_from_solidity(sol_src_path, main_contract) -> dict:
    sol_src_path_modified = str(sol_src_path)[:-4] + "_marked.sol"
    if not shutil.which(AST_GENERATOR):
        sys.exit(f"Please install {AST_GENERATOR} first")

    try:
        result = subprocess.run(
            [AST_GENERATOR, "--yul-json-ast", sol_src_path, main_contract],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr.decode("utf-8"), file=sys.stderr)
        raise e

    output = get_for_contract(sol_src_path_modified, main_contract, ["abi"])
    warp_assert(output, f"Couldn't extract {main_contract}'s abi from {sol_src_path}")
    (abi,) = output

    codes = json.loads(result.stdout)
    yul_ast = parse_to_normalized_ast(codes)
    cairo_code = transpile_from_yul(yul_ast)
    try:
        os.remove(sol_src_path_modified)
    except FileNotFoundError:
        pass  # for reentrancy
    return {"cairo_code": cairo_code, "sol_abi": abi}


def transpile_from_yul(yul_ast: ast.Node) -> str:
    name_gen = NameGenerator()
    cairo_functions = CairoFunctions(FunctionGenerator())
    builtins = get_default_builtins(cairo_functions)
    yul_ast = ForLoopSimplifier().map(yul_ast)
    yul_ast = ForLoopEliminator(name_gen).map(yul_ast)
    yul_ast = MangleNamesVisitor().map(yul_ast)
    yul_ast = SwitchToIfVisitor().map(yul_ast)
    yul_ast = VariableInliner().map(yul_ast)
    yul_ast = ConstantFolder().map(yul_ast)
    yul_ast = FoldIf().map(yul_ast)
    yul_ast = ExpressionSplitter(name_gen).map(yul_ast)
    yul_ast = RevertNormalizer(builtins).map(yul_ast)
    yul_ast = ScopeFlattener(name_gen).map(yul_ast)
    yul_ast = LeaveNormalizer().map(yul_ast)
    yul_ast = RevertNormalizer(builtins).map(yul_ast)
    yul_ast = FunctionPruner().map(yul_ast)
    yul_ast = DeadcodeEliminator().map(yul_ast)

    cairo_visitor = ToCairoVisitor(name_gen, cairo_functions, get_default_builtins)

    from starkware.cairo.lang.compiler.parser import parse_file

    return parse_file(cairo_visitor.translate(yul_ast)).format()


def main(argv):
    if len(argv) != 3:
        sys.exit("Supply SOLIDITY-CONTRACT and MAIN-CONTRACT-NAME")
    sol_src_path = argv[1]
    main_contract = argv[2]
    transpile_from_solidity(sol_src_path, main_contract)


if __name__ == "__main__":
    main(sys.argv)
