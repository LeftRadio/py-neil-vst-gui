
import os
from neil_vst import VstHost, VstPlugin


class VSTChain(object):
    """docstring for VSTChain"""

    def __init__(self, logger=None):
        self.vst_host = VstHost(44100, logger=logger)
        self.plugins_list = []
        self.logger = logger
        self.last_path = ""

    # -------------------------------------------------------------------------

    def _vst_dll_load(self, dll_path):
        # load and return plugin instance if success
        return VstPlugin(
            host=self.vst_host,
            vst_path_lib=dll_path,
            sample_rate=self.vst_host.sample_rate,
            block_size=self.vst_host.block_size,
            max_channels=4,
            self_buffers=True,
            logger=self.vst_host.logger
        )

    # -------------------------------------------------------------------------

    def add(self, dll_path, parameters={}):
        try:
            plugin = self._vst_dll_load(dll_path)
            self.logger.info('Loaded "%s"' % os.path.basename(dll_path))
            self.logger.debug(plugin.info())
        except Exception as e:
            self.logger.error('[ ERROR ] while load "%s"' % os.path.basename(dll_path))
            self.logger.debug(str(e))
            return

        self.plugins_list.append(plugin)
        self.last_path = dll_path
        self.plugin_parameters_set(plugin, parameters)
        return plugin

    def remove(self, index):
        self.plugins_list.remove(self.plugins_list[index])

    def swap(self, index_0, index_1):
        swap_plugins = self.plugins_list[index_0], self.plugins_list[index_1]
        self.plugins_list[index_1], self.plugins_list[index_0] = swap_plugins

    def clear(self):
        self.plugins_list.clear()

    def plugin(self, index):
        return self.plugins_list[index]

    def plugins(self):
        return self.plugins_list

    def host(self):
        return self.vst_host

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

    def plugins_load(self, plugins_parameters_list):
        for v in plugins_parameters_list.values():
            self.add(v["path"], v["params"])
