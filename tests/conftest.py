from freezegun.api import FakeDatetime
import yaml
from yaml.dumper import SafeDumper
from yaml.representer import SafeRepresenter


def pytest_configure():
    SafeDumper.add_representer(FakeDatetime, SafeRepresenter.represent_datetime)
