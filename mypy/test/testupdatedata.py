import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

from mypy.test.config import test_data_prefix
from mypy.test.helpers import Suite


class UpdateDataSuite(Suite):
    def _run_pytest_update_data(self, data_suite: str, *, max_attempts: int) -> str:
        """
        Runs a suite of data test cases through 'pytest --update-data' until either tests pass
        or until a maximum number of attempts (needed for incremental tests).
        """
        p = Path(test_data_prefix) / "check-update-data.test"
        assert not p.exists()
        try:
            p.write_text(textwrap.dedent(data_suite).lstrip())

            test_nodeid = f"mypy/test/testcheck.py::TypeCheckSuite::{p.name}"
            args = [sys.executable, "-m", "pytest", "-n", "0", "-s", "--update-data", test_nodeid]
            if sys.version_info >= (3, 8):
                cmd = shlex.join(args)
            else:
                cmd = " ".join(args)
            for i in range(max_attempts - 1, -1, -1):
                res = subprocess.run(args)
                if res.returncode == 0:
                    break
                print(f"`{cmd}` returned {res.returncode}: {i} attempts remaining")

            return p.read_text()
        finally:
            p.unlink()

    def test_update_data(self) -> None:
        # Note: We test multiple testcases rather than 'test case per test case'
        #       so we could also exercise rewriting multiple testcases at once.
        actual = self._run_pytest_update_data(
            """
            [case testCorrect]
            s: str = 42  # E: Incompatible types in assignment (expression has type "int", variable has type "str")

            [case testWrong]
            s: str = 42  # E: wrong error

            [case testXfail-xfail]
            s: str = 42  # E: wrong error

            [case testWrongMultiline]
            s: str = 42  # E: foo \
                         # N: bar

            [case testMissingMultiline]
            s: str = 42;  i: int = 'foo'

            [case testExtraneous]
            s: str = 'foo'  # E: wrong error

            [case testExtraneousMultiline]
            s: str = 'foo'  # E: foo \
                            # E: bar

            [case testExtraneousMultilineNonError]
            s: str = 'foo'  # W: foo \
                            # N: bar

            [case testOutCorrect]
            s: str = 42
            [out]
            main:1: error: Incompatible types in assignment (expression has type "int", variable has type "str")

            [case testOutWrong]
            s: str = 42
            [out]
            main:1: error: foobar

            [case testOutWrongIncremental]
            s: str = 42
            [out]
            main:1: error: foobar
            [out2]
            main:1: error: foobar

            [case testWrongMultipleFiles]
            import a, b
            s: str = 42  # E: foo
            [file a.py]
            s1: str = 42  # E: bar
            [file b.py]
            s2: str = 43  # E: baz
            [builtins fixtures/list.pyi]
            """,
            max_attempts=3,
        )

        # Assert
        expected = """
        [case testCorrect]
        s: str = 42  # E: Incompatible types in assignment (expression has type "int", variable has type "str")

        [case testWrong]
        s: str = 42  # E: Incompatible types in assignment (expression has type "int", variable has type "str")

        [case testXfail-xfail]
        s: str = 42  # E: wrong error

        [case testWrongMultiline]
        s: str = 42  # E: Incompatible types in assignment (expression has type "int", variable has type "str")

        [case testMissingMultiline]
        s: str = 42;  i: int = 'foo'  # E: Incompatible types in assignment (expression has type "int", variable has type "str") \\
                                      # E: Incompatible types in assignment (expression has type "str", variable has type "int")

        [case testExtraneous]
        s: str = 'foo'

        [case testExtraneousMultiline]
        s: str = 'foo'

        [case testExtraneousMultilineNonError]
        s: str = 'foo'

        [case testOutCorrect]
        s: str = 42
        [out]
        main:1: error: Incompatible types in assignment (expression has type "int", variable has type "str")

        [case testOutWrong]
        s: str = 42
        [out]
        main:1: error: Incompatible types in assignment (expression has type "int", variable has type "str")

        [case testOutWrongIncremental]
        s: str = 42
        [out]
        main:1: error: Incompatible types in assignment (expression has type "int", variable has type "str")
        [out2]
        main:1: error: Incompatible types in assignment (expression has type "int", variable has type "str")

        [case testWrongMultipleFiles]
        import a, b
        s: str = 42  # E: Incompatible types in assignment (expression has type "int", variable has type "str")
        [file a.py]
        s1: str = 42  # E: Incompatible types in assignment (expression has type "int", variable has type "str")
        [file b.py]
        s2: str = 43  # E: Incompatible types in assignment (expression has type "int", variable has type "str")
        [builtins fixtures/list.pyi]
        """
        assert actual == textwrap.dedent(expected).lstrip()
