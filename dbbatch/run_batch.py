import subprocess
import threading
import os
import time

from queue import Queue
from dbbatch.misc_os import list_files, create_dir, split_file_name_ext, kill_process
from dbbatch.collector import Collector
from dbbatch.watchers import SbemWatcher, EplusWatcher

SBEM_VERSIONS = ["41e", "54a", "54b", "55h", "56a"]
DB_PATH = "C:/Program Files (x86)/DesignBuilder/designbuilder.exe"
TIMEOUT = 600
DB_DATA = os.path.join(os.getenv('LOCALAPPDATA'), "DesignBuilder")
JOB_SERVER_DIR = "C:/ProgramData/DesignBuilder/JobServer/Users/User"

WATCH_SBEM = (
    "model.inp",
    "model_epc.inp",
    "model_epc[epc].pdf",
    "model_epc[rec].pdf",
    "model_epc[srec].pdf",
    "model_ber.inp",
    "model_ber[adv].pdf",
    "model_ber[ber].pdf",
    "model_ber[sadv].pdf",
)
WATCH_EPLUS = (
    "in.idf",
    "eplusout.err",
    "eplusout.eso",
    "eplustbl.htm",
)


class NoDsbFileFound(Exception):
    """ Exception is raised when there isn't any .dsb file found. """
    pass


class IncorrectAnalysisType(Exception):
    """ Exception is raised when the analysis type is not applicable. """
    pass


class IncorrectFilesRequest(Exception):
    """ Exception is raised when requested files are not applicable. """
    pass


class InvalidStartingIndex(Exception):
    """ Exception is raised when requested starting index is greater then number of models. """
    pass


class InvalidDBExePath(Exception):
    """ Exception is raised when DB exe path is not valid. """
    pass


def get_loc(analysis):
    """ Get results subdirectory for the given analysis. """
    if analysis.lower() == "eplus":
        return ["energyplus"]

    elif analysis.lower() == "sbem":
        return SBEM_VERSIONS

    else:
        raise IncorrectAnalysisType("Incorrect analysis type: '{}'\n"
                                    "This can be: {}, {}.".format(analysis, "eplus", "sbem"))


def remove_files(paths):
    """ Delete files for given paths. """
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            # print("Cannot remove file: '{}'\n\tFile not found!".format(path))
            pass
        except PermissionError:
            print("Cannot remove file: '{}'\n\tAccess denied!".format(path))


def create_cmnd(analysis, sim_start_date, sim_end_date, use_sim_manager, attributes):
    """ Create a command string for automatic processing. """
    args = []

    if use_sim_manager:
        args.append("UseSimManager")

    if sim_start_date:
        args.append(f"SimStartDate {sim_start_date[0]} {sim_start_date[1]}")

    if sim_end_date:
        args.append(f"SimEndDate {sim_end_date[0]} {sim_end_date[1]}")

    if attributes:
        args.extend([f"ChangeAttributeValue {attr} {val}" for attr, val in attributes])

    types = {
        "eplus": "miGSS",
        "sbem": "miGCalculate",
        "dsm": "miGCalculate",  # not working
    }

    if analysis == "none":
        # this is used for cases when it's desired
        # only to update bunch of models
        pass

    else:
        try:
            args.append(types[analysis])

        except KeyError:
            raise KeyError("Incorrect analysis type: '{}'.".format(analysis))

    args.append("miTUpdate")

    if len(args) == 1:
        cmnd = "/process=" + args[0]
    else:
        cmnd = "/process=" + ", ".join(args)

    print(f"Running batch using '{cmnd}' command args. ")

    return cmnd


def run_subprocess(file, cmd, db_pth=DB_PATH, timeout=TIMEOUT):
    """ Run DesignBuilder file. """
    cmnd = f"{file} {cmd}"  # add file path to the command

    try:
        subprocess.run([db_pth, cmnd], timeout=timeout)
        return True

    except subprocess.TimeoutExpired:
        print(f"Model '{file}' - Timeout expired!")
        return False


def watcher(analysis):
    """
    Choose a watcher thread based on the analysis type.

    Notes
    -----
    DSM is not supported at the moment!
    """
    types = {
        "sbem": SbemWatcher,
        "eplus": EplusWatcher,
        "dsm": None
    }

    try:
        watcher = types[analysis]

    except KeyError:
        raise KeyError("Incorrect analysis type: '{}'.".format(analysis))

    if analysis == "dsm":
        raise Exception("DSM not supported!")

    return watcher


def pick_up_files(analysis_type):
    """
    Return a default list of output files based on analyis type.

    Notes
    -----
    DSM is not supported at the moment!
    """
    data = {
        "sbem": WATCH_SBEM,
        "eplus": WATCH_EPLUS,
        "dsm": None
    }

    try:
        files = data[analysis_type]

    except KeyError:
        raise KeyError("Incorrect analysis type: '{}'.".format(analysis_type))

    if analysis_type == "dsm":
        raise Exception("DSM not supported!")

    return files


def init_report(analysis_type, outputs_root_dir, num_models):
    """ Initialize output report file. """
    str_tme = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time()))
    name = "summary_{}_{}.txt".format(analysis_type, str_tme)
    report_file = os.path.join(outputs_root_dir, name)

    with open(report_file, "w") as f:
        f.write("Running '{}' analysis.\n\tNumber of files: '{}'.\n".format(analysis_type, num_models))

    return report_file


def finish_report(report_file, report_dct):
    """ Summarize batch run analysis. """
    lines = [
        "\n{}".format("*" * 50),
        "\nSummary:",
        "\n\tSkipped: '{}' models.".format(len(report_dct["skipped"])),
        "\n\tTimeout expired: '{}' models.".format(len(report_dct["expired"])),
        "\n\tFailed: '{}' models.".format(len(report_dct["failed"])),
        "\n\tSuccessful: '{}' models.".format(len(report_dct["successful"])),
        "\n{}".format("*" * 50)
    ]
    print("".join(lines))
    with open(report_file, "a") as f:
        f.writelines(lines)


def run_batch(models_root_dir, outputs_root_dir, make_output_subdirs=False, models_dirs_depth=1,
              analysis_type="sbem", db_data_dir=DB_DATA, watch_files="default", db_pth=DB_PATH,
              job_server_dir=JOB_SERVER_DIR, timeout=TIMEOUT, start_index=1, end_index=None,
              write_report=True, include_model_name=True, include_orig_name=False, sim_start_date=None,
              sim_end_date=None, use_sim_manager=False, change_attributes=None):
    """
    This is a main function to run DesignBuilder files as a 'batch'.

    Parameters
    ----------
    models_root_dir : str, path like
        A root path in which models are placed.
    outputs_root_dir: : str, path like
        A path in which output files will be copied.
    make_output_subdirs : bool default False
        Defines if results should be placed in a subdirectory.
        This is only applicable when 'model_name' is included.
    models_dirs_depth : int, default 1
        Defines whether dsb models should be picked from
        subdirectories as well, goes n-level deep.
    analysis_type : {'sbem','eplus'}, default 'sbem'
        Defines which type of analysis should be automatically run.
    db_data_dir : str, path like
        A path to DesignBuilder app data directory.
    watch_files : 'default' or list of str
        A list with specified files to be watched when running a calculation.
        When this is 'default' relevant files are picked up automatically.
    db_pth : str, path like
        Path to DesignBuilder executable.
    job_server_dir : str, path like
        A path to 'job server' directory (where 'Simulation Manager'
        outputs are stored).
    timeout : int, default 300
        A timeout after which DesignBuilder process is terminated (secs).
    start_index: int, default 1
        A starting index of the batch run (batch starts from 1).
    end_index: int, default 1
        A last index of the batch run (batch starts from 1).
    write_report: bool
        Output summary file will be produced in the 'outputs' folder
        when this is 'True'.
    include_model_name : bool, default True
        Defines if model name should be included in the copied file title.
    include_orig_name : bool, default False
        If this is 'True' original name will be included in the
        copy title.
    sim_start_date : tuple, default None
        If defined, this forces simulation to start on a specific date.
        The format is (DD, MM).
    sim_end_date : tuple, default None
        If defined, this forces simulation to end on a specific date.
        The format is (DD, MM).
    use_sim_manager : bool, default False
        Force simulation manager.
    change_attributes : list of tuples, default None
        Overwrite given attributes, input in tuple pairs (attr, val).

    """
    t1000 = kill_process("DesignBuilder.exe")

    # get all the models which will be run in batch
    model_paths = list_files(models_root_dir, depth=models_dirs_depth)

    if not model_paths:
        # raise an error if there aren't any db models in specified folder
        raise NoDsbFileFound("No .dsb model was found in '{}'.".format(models_root_dir))

    if not os.path.isfile(db_pth):
        raise InvalidDBExePath("DB executable path '{}' is not valid.\n"
                               "Specify the correct path using 'db_path' kwarg.".format(db_pth))

    if watch_files == "default":
        watch_files = WATCH_SBEM if analysis_type == "sbem" else WATCH_EPLUS

    if analysis_type == "eplus" and "in.idf" not in watch_files and "eplusout.err" not in watch_files:
        raise IncorrectFilesRequest("Requested set of files is not applicable for eplus analysis!\n"
                                    "Request must contain at least 'in.idf' and 'eplusout.err' files.\n"
                                    "(Files are specified in 'watch_files' kwarg.)")

    start_index = 1 if not start_index else start_index
    if start_index > len(model_paths):
        raise InvalidStartingIndex("Chosen start index '{}' is higher than actual "
                                   "number of models: '{}'.".format(start_index, len(model_paths)))

    # create a queue which will be used to pass
    # the data between watchers and collector thread
    queue = Queue()

    # run a collector thread which handles storing of specified output files
    collector = Collector(queue, outputs_root_dir, make_subdirs=make_output_subdirs,
                          include_orig_name=include_orig_name, include_model_name=include_model_name)
    collector.start()

    # create directory to store outputs
    create_dir(outputs_root_dir)

    # initialize a report dictionary
    report_dct = {"skipped": [],
                  "expired": [],
                  "failed": [],
                  "successful": []}

    # initialize a report file if requested
    report_file = ""
    if write_report:
        report_file = init_report(analysis_type, outputs_root_dir, len(model_paths))

    # get name of the folder in which outputs are stored
    locs = get_loc(analysis_type)

    # define full paths for files which should be being watched
    if watch_files == "default":
        watch_files = pick_up_files(analysis_type)

    watch_paths = [os.path.join(db_data_dir, loc, file) for file in watch_files for loc in locs]

    cmnd = create_cmnd(analysis_type, sim_start_date, sim_end_date, use_sim_manager, change_attributes)

    for i, path in enumerate(model_paths, start=1):
        model_name = split_file_name_ext(path)[0]

        # if there are outputs files available from a previous run, these
        # are removed to guarantee that new files can be properly watched
        remove_files(watch_paths)

        if i < start_index or i > (end_index if end_index else 9999999):
            # non-default starting index has been requested
            # skip until the condition is met
            print("Skipping {}/{} - '{}'".format(i, len(model_paths), model_name))
            report_dct["skipped"].append(model_name)
            continue

        args = [model_name, watch_paths, queue, job_server_dir, report_file, report_dct]

        if analysis_type == "sbem":
            # job server is not applicable for sbem calculation
            args = args[:3]

        print("Running {}/{} - '{}'".format(i, len(model_paths), model_name))

        # run a watcher thread which is responsible for watching
        # output files based on analysis type
        w_thread = watcher(analysis_type)(*args)
        w_thread.start()

        # run an actual DesignBuilder process
        finished = run_subprocess(path, cmnd, db_pth=db_pth, timeout=timeout)

        if not finished:
            # kill the thread as the model timeout expired
            report_dct["expired"].append(model_name)
            if report_file:
                with open(report_file, "a") as f:
                    msg = "File '{}' - Timeout expired!".format(model_name)
                    f.write(msg + "\n")

            w_thread.stop()

        if analysis_type.lower() == "sbem":
            # for sbem analysis, there cannot be any pending watcher thread
            # as all the work must be already finished when the parent process ends
            # some time needs to be given to copy outputs
            if finished:
                report_dct["successful"].append(model_name)
            w_thread.stop()
            time.sleep(3)

    while threading.active_count() > 2:
        # wait until all child threads finish
        # when only main and collector threads are running
        # program can be terminated
        time.sleep(1)

    if write_report:
        finish_report(report_file, report_dct)

    # terminate collector thread gracefully
    collector.stop()
