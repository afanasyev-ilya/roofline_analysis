#!/usr/bin/python


import shutil
from paths import *


def clean_all():
    shutil.rmtree(profiling_data_path)
    return