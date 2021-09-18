#!python3

import os
import json
from neil_vst_gui.ui_settings import UI_Settings


base = { "plugins_chain": {} }
chain = {"chain": {"title": "", "normalize": {}, "plugins_list": {}}}
normilize = { "enable": True, "target_rms": 0, "error_db": 0.25 }
plugin = { "plugin_name": {"path": "", "max_channels": 8, "params": {}} }
plugin_param = { "Parameter": {"value": 0.0, "fullscale": 1.0, "normalized": True} }


class Job(object):
    """docstring for Job"""
    def __init__(self, name="chain 0", in_files=[], out_files=[]):
        # in/out files
        self.in_files = in_files
        self.out_files = out_files
        #
        self.vst_plugins_chain = []
        # plugins settings
        self.settings = { "title": name, "normalize": {}, "plugins_list": {} }
        #
        self.job_file = os.path.dirname(__file__) + "./_job.json"

    # -------------------------------------------------------------------------

    def set_in_files(self, in_files):
        for a in in_files:
            if a in self.in_files:
                continue
            self.in_files.append(a)

    def file_remove(self, name):
        self.in_files.remove(name)

    def files_remove_all(self):
        self.in_files = []

    def set_normalize(self, enable=False, target_rms=-20, error_db=0.25):
        self.settings["normalize"] = {"enable": enable, "target_rms": target_rms, "error_db": error_db }

    def vst_add_to_chain(self, vst_instance):
        self.vst_plugins_chain.append(vst_instance)

    def vst_remove_from_chain(self, index):
        self.vst_plugins_chain.remove(self.vst_plugins_chain[index])

    def vst_swap_in_chain(self, index_0, index_1):
        swap_plugins = self.vst_plugins_chain[index_0], self.vst_plugins_chain[index_1]
        self.vst_plugins_chain[index_1], self.vst_plugins_chain[index_0] = swap_plugins

    def vst_remove_all(self):
        self.vst_plugins_chain = []

    # -------------------------------------------------------------------------

    def parse_plugin_parameters(self, plugin):
        parameters = {}
        for k,v in plugin.parameters_indexes_dict.items():
            parameters[k] = {"value": plugin.parameter_value(index=v), "fullscale": 1.0, "normalized": True}
        return parameters

    def plugin_parameters_set(self, plugin, plugin_settings):
        for k, v in plugin_settings.items():
            if "normalized" not in v.keys():
                v["normalized"] = True
            plugin.parameter_value(name=k, value=v["value"], fullscale=v["fullscale"], normalized=v["normalized"])

    def update(self, filepath=None, normilize_params={}, out_folder="", tag_data=()):
        # update normilize parameters
        if len(normilize_params.keys()):
            self.settings["normalize"] = normilize_params
        # update out_folder param
        self.out_folder = out_folder
        self.tag_data = tag_data

        # update all other parameters
        index = 0
        self.settings["plugins_list"] = {}
        for plugin in self.vst_plugins_chain:
            self.settings["plugins_list"]["%s (%d)" % (plugin.name, index)] = {
                "path": plugin.path_to_lib,
                "max_channels": 8,
                "params": self.parse_plugin_parameters(plugin)
            }
            index += 1
        # dump updated parameters
        self.dump(filepath)

    def load(self, filepath=None):
        if filepath is None:
            filepath = self.job_file
        with open(filepath, "r") as f:
            data = f.read()
            self.settings = json.loads(data)

    def dump(self, filepath=None,):
        if filepath is None:
            filepath = self.job_file
        with open(filepath, "w") as f:
            data = json.dumps(self.settings, indent="    ", ensure_ascii=False, sort_keys=False)
            f.write(data)


if __name__ == '__main__':
    j = Job()
    j.load("S:/audio_job.json")
    j.dump("S:/audio_job_dump.json")