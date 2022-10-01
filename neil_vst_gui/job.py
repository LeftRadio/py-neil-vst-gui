#!python3

import os
import json
from neil_vst_gui.vst_chain import VSTChain
from neil_vst_gui.import_files import ImportFiles
from neil_vst_gui.metadata import Metadata





class Job(object):
    """docstring for Job"""
    def __init__(self, logger=None):
        #
        self.job_file_default = os.path.dirname(__file__) + "./_job.json"
        self.job_file = self.job_file_default
        #
        self.__files = ImportFiles()
        self.__vst_chain = VSTChain(logger=logger)
        self.__metadata = Metadata()

    def __settings_init(self):
        return {
            "title": "def chain",
            "in_files": [],
            "out_files": [],
            "normalize": {},
            "plugins_list": {},
            "out_folder": "",
            "metadata": ()
        }

    def __update_job_filepath(self, filepath):
        if filepath is not None:
            self.job_file = filepath
            self.last_path = os.path.dirname(filepath)

    # -------------------------------------------------------------------------

    def files(self):
        return self.__files

    def vst_chain(self):
        return self.__vst_chain

    def metadata(self):
        return self.__metadata

    # -------------------------------------------------------------------------

    def update(self, normilize_params, metadata, filepath=None):
        #
        settings = self.__settings_init()
        # update normilize parameters
        if len(normilize_params.keys()):
            settings["normalize"] = normilize_params
        # update import files param
        settings["in_files"] = self.__files.filelist
        # update out_folder param
        settings["out_folder"] = self.__files.out_folder
        # update all other parameters
        index = 0
        for plugin in self.__vst_chain.plugins():
            settings["plugins_list"]["%s (%d)" % (plugin.name, index)] = {
                "path": plugin.path_to_lib,
                "max_channels": 8,
                "params": self.__vst_chain.parse_plugin_parameters(plugin)
            }
            index += 1
        #
        settings["metadata"] = self.__metadata.data = metadata
        # dump updated parameters
        self.dump(settings, filepath)

    def load(self, filepath=None):
        # update job json filepath
        self.__update_job_filepath(filepath)
        # load data from filepath
        f = open(self.job_file, "r")
        data = f.read()
        f.close()

        settings = {**self.__settings_init(), **json.loads(data)}
        # set import file list
        self.__files.update(settings["in_files"])
        self.__files.out_folder_update(settings["out_folder"])
        #
        # self.settings["normalize"]
        # set VST chain
        self.__vst_chain.clear()
        self.__vst_chain.plugins_load(settings["plugins_list"])
        #
        self.__metadata.data = settings["metadata"]

    def dump(self, settings, filepath=None):
        # update job json filepath
        self.__update_job_filepath(filepath)
        # serialaze data
        data = json.dumps(settings, indent="    ", ensure_ascii=False, sort_keys=False)
        # write data to filepath
        with open(self.job_file, "w") as f:
            f.write(data)

    def is_default(self):
        if self.job_file == self.job_file_default:
            return True
        return False


if __name__ == '__main__':
    j = Job()
    j.load("S:/audio_job.json")
    j.dump("S:/audio_job_dump.json")