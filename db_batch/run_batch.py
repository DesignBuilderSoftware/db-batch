import os
import threading
import time
from queue import Queue

import psutil
from db_process import (
    ProcessChain,
    eplus_simulation,
    find_designbuilder,
    kill_when_idle,
    run,
    run_async,
    sbem_calculation,
)

from db_batch.collector import Collector
from db_batch.misc_os import (
    create_dir,
    list_files,
    split_file_name_ext,
    to_absolute,
)
from db_batch.watchers import EplusWatcher, SbemWatcher

WATCHER_JOIN_TIMEOUT = 60
SBEM_VERSIONS = ["41e", "54a", "54b", "55h", "56a", "61e"]
TIMEOUT = 600
DB_DATA = os.path.join(os.getenv("LOCALAPPDATA"), "DesignBuilder")
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
    """Exception is raised when there isn't any .dsb file found."""


class IncorrectAnalysisType(Exception):
    """Exception is raised when the analysis type is not applicable."""


class IncorrectFilesRequest(Exception):
    """Exception is raised when requested files are not applicable."""


class InvalidStartingIndex(Exception):
    """Exception is raised when requested starting index is greater than n of models."""


def get_loc(analysis):
    """Get results subdirectory for the given analysis."""
    if analysis.lower() == "eplus":
        return ["energyplus"]

    elif analysis.lower() == "sbem":
        return SBEM_VERSIONS

    else:
        raise IncorrectAnalysisType(
            "Incorrect analysis type: '{}'\nThis can be: {}, {}.".format(
                analysis, "eplus", "sbem"
            )
        )


DB_PROCESS_NAME = "DesignBuilder.exe"


def kill_all_designbuilder(timeout=15.0, check_interval=0.25):
    """Terminate every DesignBuilder instance and wait until none is left.

    ``db_process.kill_process()`` only kills a *single* process — whichever
    one ``find_process()`` happens to return first. That is enough while the
    invariant "at most one DesignBuilder" holds, but it cannot restore that
    invariant once it has been broken: a model that died on a modal
    "DesignBuilder is already running - only one instance is allowed" dialog
    leaves an extra instance behind, one kill removes one of them, and every
    later model stacks another dialog until the batch stops progressing.

    Returns True if nothing is running by the time we give up.
    """
    deadline = time.monotonic() + timeout
    while True:
        procs = []
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] == DB_PROCESS_NAME:
                    procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not procs:
            return True

        if time.monotonic() >= deadline:
            print(
                f"Could not terminate {len(procs)} DesignBuilder instance(s) within {timeout}s."
            )
            return False

        for proc in procs:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        psutil.wait_procs(procs, timeout=check_interval)


def remove_files(paths):
    """Delete files for given paths."""
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except PermissionError:
            print("Cannot remove file: '{}'\n\tAccess denied!".format(path))


def build_process_chain(
    analysis, sim_start_date, sim_end_date, use_sim_manager, attributes, no_close
):
    """Build a ProcessChain for batch processing.

    This replaces the old ``create_cmnd()`` function, delegating
    command construction to ``db_process``.
    """
    if analysis == "eplus":
        chain = eplus_simulation(
            sim_start_date=tuple(sim_start_date) if sim_start_date else None,
            sim_end_date=tuple(sim_end_date) if sim_end_date else None,
            use_sim_manager=use_sim_manager,
            attributes=attributes,
            no_close=no_close,
        )
    elif analysis in ("sbem", "dsm"):
        chain = sbem_calculation(
            sim_start_date=tuple(sim_start_date) if sim_start_date else None,
            sim_end_date=tuple(sim_end_date) if sim_end_date else None,
            attributes=attributes,
            no_close=no_close,
        )
    elif analysis == "none":
        # Only update models, no screen switch
        chain = ProcessChain()
        if use_sim_manager:
            chain.use_sim_manager()
        if sim_start_date:
            chain.sim_start_date(sim_start_date[0], sim_start_date[1])
        if sim_end_date:
            chain.sim_end_date(sim_end_date[0], sim_end_date[1])
        if attributes:
            for attr, val in attributes:
                chain.change_attribute(attr, val)
        if no_close:
            chain.no_close()
        chain.run()
    else:
        raise KeyError("Incorrect analysis type: '{}'.".format(analysis))

    cmnd = chain.to_string()
    print(f"Running batch using '{cmnd}' command args. ")
    return chain


def watcher(analysis):
    """
    Choose a watcher thread based on the analysis type.

    Notes
    -----
    DSM is not supported at the moment!
    """
    types = {"sbem": SbemWatcher, "eplus": EplusWatcher, "dsm": None}

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
    data = {"sbem": WATCH_SBEM, "eplus": WATCH_EPLUS, "dsm": None}

    try:
        files = data[analysis_type]

    except KeyError:
        raise KeyError("Incorrect analysis type: '{}'.".format(analysis_type))

    if analysis_type == "dsm":
        raise Exception("DSM not supported!")

    return files


def init_report(analysis_type, outputs_root_dir, num_models):
    """Initialize output report file."""
    str_tme = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time()))
    name = "summary_{}_{}.txt".format(analysis_type, str_tme)
    report_file = os.path.join(outputs_root_dir, name)

    with open(report_file, "w") as f:
        f.write(
            "Running '{}' analysis.\n\tNumber of files: '{}'.\n".format(
                analysis_type, num_models
            )
        )

    return report_file


def finish_report(report_file, report_dct):
    """Summarize batch run analysis."""
    lines = [
        "\n{}".format("*" * 50),
        "\nSummary:",
        "\n\tSkipped: '{}' models.".format(len(report_dct["skipped"])),
        "\n\tTimeout expired: '{}' models.".format(len(report_dct["expired"])),
        "\n\tFailed: '{}' models.".format(len(report_dct["failed"])),
        "\n\tSuccessful: '{}' models.".format(len(report_dct["successful"])),
        "\n{}".format("*" * 50),
    ]
    print("".join(lines))
    with open(report_file, "a") as f:
        f.writelines(lines)


def run_batch(  # noqa: C901
    models_root_or_file,
    outputs_root_dir,
    *,
    make_output_subdirs=False,
    models_dirs_depth=1,
    analysis_type="sbem",
    db_data_dir=DB_DATA,
    watch_files="default",
    db_pth=None,
    job_server_dir=JOB_SERVER_DIR,
    timeout=TIMEOUT,
    start_index=1,
    end_index=None,
    write_report=True,
    include_model_name=True,
    include_orig_name=False,
    sim_start_date=None,
    sim_end_date=None,
    use_sim_manager=False,
    change_attributes=None,
    no_close=False,
):
    """
    This is a main function to run DesignBuilder files as a 'batch'.

    Parameters
    ----------
    models_root_or_file : str, path like
        A root path in which models are placed, alternatively single file.
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
    db_pth : str, path like, optional
        Path to DesignBuilder executable.  When None, uses db_process
        auto-discovery (env var, default install paths, system PATH).
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
    no_close : bool
        Prevent DB from closing after executing command.

    """
    kill_all_designbuilder()

    if not os.path.exists(models_root_or_file):
        raise NoDsbFileFound("Path '{}' does not exist.".format(models_root_or_file))

    if os.path.isdir(models_root_or_file):
        # get all the models which will be run in batch
        model_paths = list_files(models_root_or_file, depth=models_dirs_depth)

        if not model_paths:
            # raise an error if there aren't any db models in specified folder
            raise NoDsbFileFound("No .dsb model was found in '{}'.".format(models_root_or_file))
    else:
        model_paths = [models_root_or_file]

    # Validate that DesignBuilder can be found (raises FileNotFoundError if not)
    exe = find_designbuilder(db_pth)

    if watch_files == "default":
        watch_files = WATCH_SBEM if analysis_type == "sbem" else WATCH_EPLUS

    if (
        analysis_type == "eplus"
        and "in.idf" not in watch_files
        and "eplusout.err" not in watch_files
    ):
        raise IncorrectFilesRequest(
            "Requested set of files is not applicable for eplus analysis!\n"
            "Request must contain at least 'in.idf' and 'eplusout.err' files.\n"
            "(Files are specified in 'watch_files' kwarg.)"
        )

    # make sure that paths are absolute
    model_paths = to_absolute(model_paths)

    start_index = 1 if not start_index else start_index
    if start_index > len(model_paths):
        raise InvalidStartingIndex(
            "Chosen start index '{}' is higher than actual number of models: '{}'.".format(
                start_index, len(model_paths)
            )
        )

    # create a queue which will be used to pass
    # the data between watchers and collector thread
    queue = Queue()

    # run a collector thread which handles storing of specified output files
    collector = Collector(
        queue,
        outputs_root_dir,
        make_subdirs=make_output_subdirs,
        include_orig_name=include_orig_name,
        include_model_name=include_model_name,
    )
    collector.start()

    # create directory to store outputs
    create_dir(outputs_root_dir)

    # initialize a report dictionary
    report_dct = {"skipped": [], "expired": [], "failed": [], "successful": []}

    # Watchers are joined explicitly at the end of the batch. Counting live
    # threads process-wide instead would stall any caller that runs its own
    # threads (a dashboard, a progress monitor, a test harness).
    watcher_threads = []

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

    # Build the process chain using db_process
    chain = build_process_chain(
        analysis_type,
        sim_start_date,
        sim_end_date,
        use_sim_manager,
        change_attributes,
        no_close,
    )

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
        watcher_threads.append(w_thread)

        # run an actual DesignBuilder process (non-blocking for eplus)
        if analysis_type.lower() == "eplus":
            # DesignBuilder permits a single instance, so never launch on top
            # of a leftover one: the new process would die on a modal
            # "already running" dialog instead of simulating. This also keeps
            # find_process() unambiguous for the monitor below, which targets
            # whichever DesignBuilder it sees first rather than a given pid.
            kill_all_designbuilder()

            # For EnergyPlus, launch DesignBuilder non-blocking
            run_async(path, chain, exe_path=exe)

            # Monitor DesignBuilder and kill when idle: it terminates once
            # CPU stays below 0.1% for 10+ seconds. Run it on a thread and
            # bound the wait with the caller's per-model timeout - on its own
            # kill_when_idle() has no overall cap, so a model that never
            # registers CPU activity (sitting on a modal dialog, say) parks
            # the whole batch on that one process indefinitely. The eplus
            # path ignored `timeout` entirely before this.
            monitor = threading.Thread(
                target=kill_when_idle,
                kwargs={
                    "idle_threshold": 10,
                    "check_interval": 0.5,
                    "startup_period": 20,
                },
                daemon=True,
            )
            monitor.start()
            monitor.join(timeout)

            expired = monitor.is_alive()
            if expired:
                print(f"Model '{model_name}' - Timeout expired!")
                report_dct["expired"].append(model_name)
                if report_file:
                    with open(report_file, "a") as f:
                        msg = f"File '{model_name}' - Timeout expired!"
                        f.write(msg + "\n")

            # kill_when_idle() returns without having killed anything in
            # several paths - no process found, the process exited on its own,
            # or it never registered as active - so it cannot be relied on to
            # have left a clean slate for the next model. Sweeping here also
            # releases the monitor thread when the timeout above expired.
            kill_all_designbuilder()

            # Watcher thread is still running in background, collecting files
            # We don't wait for it - move to next simulation immediately
            finished = not expired
        else:
            # For other analysis types, use blocking approach
            result = run(path, chain, exe_path=exe, timeout=timeout)
            finished = result.success and not result.timed_out

            if result.timed_out:
                print(f"Model '{path}' - Timeout expired!")

            if not finished:
                # kill the thread as the model timeout expired
                report_dct["expired"].append(model_name)
                if report_file:
                    with open(report_file, "a") as f:
                        msg = "File '{}' - Timeout expired!".format(model_name)
                        f.write(msg + "\n")

                w_thread.stop()

            # Kill DesignBuilder after each simulation to ensure clean state
            kill_all_designbuilder()

        if analysis_type.lower() == "sbem":
            # for sbem analysis, there cannot be any pending watcher thread
            # as all the work must be already finished when the parent process ends
            # some time needs to be given to copy outputs
            if finished:
                report_dct["successful"].append(model_name)
            w_thread.stop()
            time.sleep(3)

    # Wait for the watcher threads this batch started. The previous check -
    # `while threading.active_count() > 2` - assumed the process contained
    # nothing but this module's main and collector threads, so any caller
    # holding a thread of its own left run_batch spinning here forever after
    # the last model had finished.
    for w_thread in watcher_threads:
        w_thread.join(timeout=WATCHER_JOIN_TIMEOUT)
        if w_thread.is_alive():
            # never saw its .err reach a terminal state - stop it so the
            # collector can drain and the batch can return
            w_thread.stop()
            w_thread.join(timeout=5)

    if write_report:
        finish_report(report_file, report_dct)

    # terminate collector thread gracefully
    collector.stop()
