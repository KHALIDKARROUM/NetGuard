"""Check the consolidated notebook without regenerating historical archives."""
import json

from notebook_integrity import validate_all


if __name__ == "__main__":
    print(json.dumps(validate_all(), indent=2))
