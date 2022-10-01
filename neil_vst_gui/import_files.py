
import os


class ImportFiles(object):
    """docstring for ImportFiles"""
    def __init__(self):
        self.filelist = []
        self.last_path = ""
        self.out_folder = ""

    def add(self, filelist):
        for a in filelist:
            if a in self.filelist:
                continue
            self.filelist.append(a)
            self.last_path = os.path.dirname(a)

    def file(self, name):
        self.filelist.remove(name)

    def update(self, filelist):
        self.clear()
        self.add(filelist)

    def clear(self):
        self.filelist = []

    def out_folder_update(self, dirpath):
        self.out_folder = dirpath


