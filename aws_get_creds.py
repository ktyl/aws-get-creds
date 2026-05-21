from importlib.metadata import version, PackageNotFoundError
from application import Application
import sys


def main():
    try:
        v = version("aws-get-creds")
    except PackageNotFoundError:
        v = "unknown"

    print(f"aws-get-creds {v}")

    try:
        app = Application()
        app.run()
    except Exception as err:
        print(f"Error while fetching the credentials:\n\t{err}")
        sys.exit(1)
