"""Set of watchers to monitor calculation progress."""

import os
import time
from threading import Thread

from db_batch.misc_os import list_dirs


class Watcher(Thread):
    """
    A base thread to monitor specified paths.

    Given paths are being checked for changes,
    (using try-read mechanism) to see if actual files
    have been produced.

    Once the calculation finishes (either successfully
    or once timeout expires), watcher needs to be closed
    externally - using 'stop' method.

    All the files which were produced during the run will
    be passed into queue for further processing (copying to
    specified location using 'Collector' thread).

    Parameters
    ----------
    model_name : str
        A name of the monitored model.
    paths : list of (str, path like)
        A list of paths which are being checked for changes.
    queue : Queue
        A queue object to communicate with the main part of
        batch processor.

    """

    def __init__(self, model_name, paths, queue):
        super().__init__()
        self.model_name = model_name
        self.paths = paths
        self.queue = queue
        self._running = False

    def stop(self):
        """Stop monitoring."""
        self._running = False

    def run(self):
        """Monitor given calculation files."""
        self._running = True
        files = set()
        while self._running:
            for path in self.paths:
                try:
                    with open(path, "r"):
                        files.add(path)
                except FileNotFoundError:
                    pass
            time.sleep(1)
        self.queue.put((files, self.model_name))


class SbemWatcher(Watcher):
    """A watcher thread to monitor sbem outputs processing."""

    def __init__(self, model_name, paths, queue):
        super().__init__(model_name, paths, queue)


class EplusWatcher(Watcher):
    """
    A watcher to monitor EnergyPlus simulation.

    Watcher monitors standard 'EnergyPlus' and jobserver
    directory to find out if the simulation runs using
    'Simulation Manager' or 'Standard' simulation.

    Once the '.err' file is produced, watcher reads
    the file to get the status of the simulation run (this can
    be either 'Failed' or 'Successful').

    Based on the status, specific set of files will be
    passed into queue for further processing (copying to
    specified location using 'Collector' thread).

    Parameters
    ----------
    model_name : str
        A name of the monitored model.
    paths : list of (str, path like)
        A list of paths which are being checked for changes.
    queue : Queue
        A queue object to communicate with the main part of
        batch processor.
    job_server_dir : str, path like
        A path to DesignBuilder directory storing Simulation
        Manager jobs.
    report_file : str, path like
        A path to the summary output file (if this is 'None',
        file won't be written)

    """

    def __init__(
        self, model_name, paths, queue, job_server_dir, report_file, report_dct
    ):
        super().__init__(model_name, paths, queue)
        self.job_server_dir = job_server_dir
        self.report_file = report_file
        self.report_dct = report_dct

    def run(self):
        """Monitor EnergyPlus simulation files."""
        self._running = True

        files_dct = {os.path.basename(pth): pth for pth in self.paths}
        new_dir = self.check_simulation_method(files_dct)

        if new_dir:
            # the simulation runs using 'Simulation Manager'
            # update paths for requested output files
            files_dct = {k: os.path.join(new_dir, k) for k in files_dct.keys()}

        # this is a main check to see if simulation finished successfully
        success = self.read_err_file(files_dct["eplusout.err"])

        files = [v for v in files_dct.values()]

        if not success:
            # copy only err and idf file as the other will not be available
            self.report_dct["failed"].append(self.model_name)

            if self.report_file:
                with open(self.report_file, "a") as f:
                    msg = f"Model '{self.model_name}' - EnergyPlus failed!"
                    f.write(msg + "\n")

            files = list(
                filter(lambda x: ("eplusout.err" in x or "in.idf" in x), files)
            )

        else:
            self.report_dct["successful"].append(self.model_name)

        self.queue.put((files, self.model_name))

    def read_err_file(self, err_pth):
        """Read the '.err' file to find out a simulation status."""
        while True:
            if not self._running:
                # simulation has ended prematurely - timeout expired
                # return True to avoid writing E+ failed status
                return True

            time.sleep(1)

            if not os.path.exists(err_pth):
                # wait until the '.err' file is generated
                continue

            with open(err_pth, "r") as f:
                while True:
                    lines = f.readlines()

                    for line in lines:
                        if "EnergyPlus Completed Successfully" in line:
                            print(
                                f"\tModel: '{self.model_name}' - "
                                f"EnergyPlus Completed Successfully"
                            )
                            return True

                        elif "EnergyPlus Terminated--Fatal Error Detected" in line:
                            print(
                                f"\tModel: '{self.model_name}' - "
                                f"EnergyPlus Terminated--Fatal Error Detected"
                            )
                            return False

                    if not self._running:
                        # simulation has ended prematurely - timeout expired
                        # return True to avoid writing E+ failed
                        return True

                    time.sleep(0.1)

    def check_simulation_method(self, files_dct):
        """Find simulation method (SM or Standard)"""
        in_pth = files_dct["in.idf"]
        err_pth = files_dct["eplusout.err"]

        original_jobs = list_dirs(self.job_server_dir)

        while True:
            if not self._running:
                break

            time.sleep(1)  # wait a bit

            if not os.path.exists(in_pth):
                # waiting for idf to be generated
                continue

            # list the jobs folder again to find out
            # if a new job has been submitted
            current_jobs = list_dirs(self.job_server_dir)
            new_path = set(current_jobs).difference(set(original_jobs))

            if os.path.exists(err_pth):
                # Error file has been generated in the 'EnergyPlus'
                # folder, simulation type is standard
                print("\tRunning standard simulation.")
                return None

            elif new_path:
                # new directory has been created in the 'jobs' directory
                # simulation runs using 'Simulation Manager'
                new_path = new_path.pop()
                print("\tRunning simulation using SM.")
                return new_path
