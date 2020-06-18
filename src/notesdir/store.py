from pathlib import Path


class FSStore:
    def __init__(self, root: Path):
        self.root = root
