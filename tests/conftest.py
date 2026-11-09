"""Load the plugin folder (aeriotv-setup, a hyphenated slug) as package aeriotv_setup."""

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "aeriotv-setup")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

if "aeriotv_setup" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "aeriotv_setup", os.path.join(PKG_DIR, "__init__.py"), submodule_search_locations=[PKG_DIR]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["aeriotv_setup"] = module
    spec.loader.exec_module(module)


@pytest.fixture
def fixture():
    def load(name):
        with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
            return json.load(fh)
    return load
