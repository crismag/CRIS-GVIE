"""Run the local CRIS-GVIE interviewer workflow."""

from gvie import RuntimeConfig
from gvie.adapters import create_interviewer_runtime


if __name__ == "__main__":
    runtime = create_interviewer_runtime(RuntimeConfig())
    runtime.run()
