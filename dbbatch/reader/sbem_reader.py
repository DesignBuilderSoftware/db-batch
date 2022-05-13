"""
A package to process UK SBEM .inp files.

The aim is to extract specific set of attributes to
compare outputs between different versions.

"""

import json
import os
from collections import defaultdict, namedtuple
from functools import partial
from typing import List, Union

import pandas as pd

SbemRequest = namedtuple("SbemRequest", "parent_obj child_obj attributes")


def get_results(inp_pths: Union[List[str], str], request: tuple) -> pd.DataFrame:
    """
    Extract results from given input file paths.

    Example
    -------
    outputs = ["KWH/M2-HEAT",
                "KWH/M2-COOL",
                "KWH/M2-AUX",
                "KWH/M2-LIGHT",
                "KWH/M2-DHW",
                "KWH/M2-EQUP"]

    request = SbemRequest('ACTUAL - BUILDING-DATA', 'BUILDING_DATA', outputs)
    df = get_results('some/path/model_epc.inp', request)

    Parameters
    ----------
    inp_pths : {str, list of str}
        Paths to model_epc.inp files.
    request : SbemRequest
        A special namedtuple object to define the request.

    Returns
    -------
    pd.DataFrame()
        Table with extracted attribute-value data.

    """
    if not isinstance(inp_pths, list):
        inp_pths = [inp_pths]

    sers = []
    for inp_pth in inp_pths:
        inp_file = ModelEpcInpFile(inp_pth)
        print("Extracting results from: '{}'".format(inp_file.name))
        outputs = inp_file.get_output_vals(*request)
        sers.append(pd.Series(outputs, name=inp_file.name))

    return pd.DataFrame(sers)


class ModelEpcInpFile:
    """
    Holds processed SBEM EPC output data.

    The data is structured as a nested dictionary with three
    layers: 'Main-object' > 'Child-object' > 'Attributes':

    {
        Object1: {
            Sub-object1: {
                Attribute1:Value,
                Attribute2:Value,
                ...},
            Sub-object2: {
                Attribute1:Value,
                Attribute2:Value,
                ...},
            {
        Object2: {
            ....
    }

    There are several ways to access the data. To print top
    two level objects into console, one of following method
    can be used:
                        'print_all_content'
                        'print_all_main_objects'
                        'print_all_objects'

    To access bottom level values, 'get_output_vals' method
    is a preferred way to get the data - 'SbemRequest' named
    tuple can be a convenient helper to define the request.

    'get_results' function can be used to extract outputs
    from multiple files in one go.

    """

    def __init__(self, path):
        self.name = os.path.basename(path)
        self.content = self.read_model_epc(path)

    @property
    def main_objects(self):
        """Get a list of all top level objects."""
        return list(self.content.keys())

    @property
    def all_objects(self):
        """Get a list of all objects (main + child)."""
        all_objects = {}
        for k, v in self.content.items():
            all_objects[k] = []
            for name in v.keys():
                all_objects[k].append(name)
        return all_objects

    def _get_attr(self, obj, attr):
        """Get attribute value."""
        try:
            return obj[attr]
        except KeyError:
            print(
                "Attribute: '{}' was not found.\n"
                "Available options are:\n\t{}".format(attr, "\n\t".join(obj.keys()))
            )

    def get_output_vals(self, par_name, child_name, attr_lst):
        """Return a dictionary {attr: val, ...} for a given object."""
        obj = self._get_child_obj(par_name, child_name)
        attrs = {}

        if not obj:
            return

        for attr in attr_lst:
            val = self._get_attr(obj, attr)

            if not val:
                continue

            attrs[attr] = val

        return attrs

    def _get_obj(self, obj, parent_obj):
        """Fetch object content."""
        try:
            return parent_obj[obj]

        except KeyError:
            print(
                "Object: '{}' was not found.\n"
                "Available options are:\n\t{}".format(
                    obj, "\n\t".join(parent_obj.keys())
                )
            )

    def _get_main_obj(self, obj_name):
        """Fetch main object content."""
        return self._get_obj(obj_name, self.content)

    def _get_child_obj(self, par_obj, child_name):
        """Fetch child object content."""
        par_cont = self._get_main_obj(par_obj)
        return self._get_obj(child_name, par_cont)

    def print_all_content(self):
        """Print all data."""
        print(json.dumps(self.content, indent=2))

    def print_all_main_objects(self):
        """Print only top level object names."""
        objects_str = "\n\t".join(self.main_objects)
        print("Available objects:\n\t{}".format(objects_str))

    def print_all_objects(self):
        """Print all objects (main + child)."""
        objects_str = ""

        for k, v in self.all_objects.items():
            objects_str += "{}\n\t{}\n".format(k, "\n\t".join(v))

        print("Available objects:\n{}".format(objects_str))

    def print_object_content(self, obj):
        """Print attributes for"""
        try:
            return self.content[obj]

        except KeyError:
            print(
                "Object: '{}' was not found.\n"
                "Available objects are:\n\t{}".format(
                    obj, "\n\t".join(self.main_objects)
                )
            )

    @staticmethod
    def process_line(line):
        """Clean up the given data."""
        line = line.replace('"', "")
        line = line.strip()
        name, obj = line.split("=")
        return name.strip(), obj.strip()

    def process_object(self, file, objects, name, obj, building):
        """Populate object data."""
        b_obj = str(obj)

        while True:
            line = file.readline()
            line = line.strip()

            if line == "":
                continue

            if ".." in line:
                break

            field, value = self.process_line(line)

            if obj == "BUILDING-DATA" and field == "ANALYSIS":
                building = value

            if obj == "BUILDING-DATA" or obj == "HVAC-SYSTEM-DATA":
                b_obj = "{} - {}".format(building, obj)

            objects[b_obj][name][field] = value

        return building

    def process_file(self, file):
        """Process .inp file."""
        objects_dct = defaultdict(partial(defaultdict, dict))
        building = ""

        while True:
            line = file.readline()

            if not line:
                break

            line = line.strip()

            if line == "":
                continue

            if line[0] == "$":
                continue

            if line[0] == '"':
                name, obj = self.process_line(line)
                building = self.process_object(file, objects_dct, name, obj, building)

        return objects_dct

    def read_model_epc(self, path):
        """Open the .inp file and trigger processing."""
        try:
            with open(path) as input_file:
                return self.process_file(input_file)

        except IOError:
            print("Cannot open file: '{}'.".format(path))
