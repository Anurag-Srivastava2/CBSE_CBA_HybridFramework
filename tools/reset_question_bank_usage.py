"""Reset question-bank usage for one environment, e.g. after a dev environment wipe.

Usage:
    python tools/reset_question_bank_usage.py --env dev
    python tools/reset_question_bank_usage.py --env cbse-dev-new-akashic-dhira-io --path data/question_bank/questions.json
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utilities.question_bank_manager import reset_environment_usage  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="Environment key to reset (see ReadConfig.get_environment_key()).")
    parser.add_argument("--path", default=None, help="Question bank JSON path (defaults to CBSE_QUESTION_BANK_PATH / data/question_bank/questions.json).")
    args = parser.parse_args()

    reset_count = reset_environment_usage(args.env, path=args.path)
    print(f"Reset {reset_count} question(s) back to unused for env={args.env!r}.")


if __name__ == "__main__":
    main()
