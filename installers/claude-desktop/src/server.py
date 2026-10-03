"""Entry point Claude Desktop runs: the installed ``mars-mcp``, over stdio.

The manifest maps each optional ``user_config`` field to an environment
variable. A field the user left empty can arrive as an empty string, or as
the unexpanded ``${user_config...}`` placeholder; which one is undocumented.
Both are removed here, before ``mars-mcp`` reads anything. Two of them
matter: an unexpanded ``MARS_MCP_TOOLS`` stops ``mars-mcp`` at startup
("unknown tool group(s)"), and an empty ``ADS_DEV_KEY`` stops astroquery
from reading ``~/.ads/dev_key``. ``mars-mcp`` already treats an empty
``MARS_HOME`` or ``MARS_MCP_TOOLS`` as unset; removing them too keeps one rule.
"""

import os
import sys

OPTIONAL_SETTINGS = ("ADS_DEV_KEY", "MARS_MCP_TOOLS", "MARS_HOME")


def drop_unset(environ):
    for name in OPTIONAL_SETTINGS:
        value = environ.get(name)
        if value is not None and (not value.strip() or value.startswith("${")):
            del environ[name]


if __name__ == "__main__":
    drop_unset(os.environ)
    from tools.mcp.__main__ import main

    sys.exit(main(sys.argv[1:]))
