# procurve_dokuwiki
Parses HP Procurve config files and makes DokuWiki tables

Copyright (C) 2017  Per von Zweigbergk <pvz@itassistans.se>

## Usage instructions

1. Install Python 3 (https://www.python.org/downloads/)
2. Download `procurve_dokuwiki.py`
3. Run `python procurve_dokuwiki.py > a.txt`
4. Paste in a config file from a HP Procurve switch
5. Send EOF (Ctrl+Z and Enter on Windows, Ctrl+D on Linux/Mac/BSD etc)
6. The `a.txt` file will now include a nice formatted table for the VLANs
