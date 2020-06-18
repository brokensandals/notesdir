from pathlib import Path
import toml


class Error(Exception):
    pass


class Notesdir:
    @classmethod
    def user_config_path(cls):
        """Returns the Path to the user's config file, ~/.notesdir.toml"""
        return Path.home().joinpath('.notesdir.toml')

    @classmethod
    def user_default(cls):
        """Creates an instance with config loaded from user_config_path().

        Raises Error if there is not a file at that path.
        """
        path = cls.user_config_path()
        if not path.is_file():
            raise Error(f"No config file found at {path}")
        return cls(toml.load(path))

    def __init__(self, config):
        self.config = config
