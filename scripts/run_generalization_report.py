"""Run the standalone report with all optional grouped/withheld-family refits."""
import sys

from run_notebook import main


if __name__ == "__main__":
    if "--extended" not in sys.argv:
        sys.argv.append("--extended")
    main()
