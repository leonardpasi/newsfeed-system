"""Preferred over a yaml file because:
- One fewer dependency (PyYaml)
- Simpler packaging: no need to ensure YAML files are included in ZIP
- Faster startup: no file reading/parsing overhead
"""

SOURCE_CONFIG = {
    "tomshardware": {"url": "https://www.tomshardware.com/feeds.xml", "type": "rss"},
    "arstechnica": {
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "type": "rss",
    },
    "r-infosecnews": {"url": "https://www.reddit.com/r/InfoSecNews/", "type": "reddit"},
}
