from application import Application
import sys

try:
    app = Application()
    app.run()
except Exception as err:
    print(f"Error while fetching the credentials:\n\t" + err.__str__())
    sys.exit(1)