import pytest

from pitagora.math_engine.sandbox import SymPySandbox


def test_sandbox_evaluate():
    sandbox = SymPySandbox()
    res = sandbox.evaluate("x**2 + 2*x + 1")
    assert res.verified is True
    assert "x**2 + 2*x + 1" in res.value or "x" in res.value
    assert res.latex is not None


def test_sandbox_solve():
    sandbox = SymPySandbox()
    res = sandbox.solve("x**2 - 4 = 0", "x")
    assert res.verified is True
    assert "-2" in res.value
    assert "2" in res.value


def test_sandbox_integrate():
    sandbox = SymPySandbox()
    res = sandbox.integrate("x**2", "x")
    assert res.verified is True
    assert "x**3/3" in res.value or "x**3" in res.value


def test_sandbox_differentiate():
    sandbox = SymPySandbox()
    res = sandbox.differentiate("sin(x)", "x")
    assert res.verified is True
    assert "cos(x)" in res.value


def test_sandbox_limit():
    sandbox = SymPySandbox()
    res = sandbox.limit("sin(x)/x", "x", "0")
    assert res.verified is True
    assert res.value == "1"


def test_sandbox_series():
    sandbox = SymPySandbox()
    res = sandbox.series("exp(x)", "x", "0", 4)
    assert res.verified is True
    # 1 + x + x**2/2 + x**3/6 + O(x**4)
    assert "x**3/6" in res.value


def test_sandbox_matrix_ops():
    sandbox = SymPySandbox()

    # 1. Determinant of [[1, 2], [3, 4]] -> 1*4 - 2*3 = -2
    res_det = sandbox.matrix_ops("[[1, 2], [3, 4]]", "det")
    assert res_det.verified is True
    assert res_det.value == "-2"

    # 2. Transpose of [[1, 2], [3, 4]] -> [[1, 3], [2, 4]]
    res_t = sandbox.matrix_ops("[[1, 2], [3, 4]]", "transpose")
    assert res_t.verified is True
    assert "3" in res_t.value
