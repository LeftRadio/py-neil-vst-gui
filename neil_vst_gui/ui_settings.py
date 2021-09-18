
import os
import json


class UI_Settings(object):
    """docstring for UI_Settings"""

    def __init__(self, filepath):
        # open json job file
        self.filepath = filepath
        self.settings = {}

    def save(self, **settings):
        # aplly
        for k in settings.keys():
            self.settings[k] = settings[k]
        # save
        with open(self.filepath, "w") as f:
            data = json.dumps(self.settings, indent="    ", sort_keys=True)
            f.write(data)

    def load(self):
        try:
            with open(self.filepath, "r") as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            self.save()
        return self.settings
