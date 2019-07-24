from threading import Thread
from db_batch.misc_os import copy_files


class Collector(Thread):
    """
    Collects and copies output files.

    This thread monitors queue object to find files which need to be copied.
    Kwargs define the form of copied outputs. There are various options to
    modify a title and a structure of copied results.

    Parameters
    ----------
    queue : Queue
        A queue object to communicate with watcher threads.
    output_root_dir : str, path like
        A path to the output folder.
    make_subdirs : bool, default False
        Create a subdirectory for each model outputs.
    include_model_name : bool
        Defines if model name should be included in the copy title.
    make_subdirs : bool default False
        Defines if results should be placed in a subdirectory.
        This is only applicable when 'model_name' is defined.
    include_orig_name : bool
        If this is 'True' original name will be included in the
        copy title.

    """

    def __init__(self, queue, output_root_dir, make_subdirs=False, include_orig_name=False,
                 include_model_name=True):
        super().__init__()
        self._running = False
        self.queue = queue
        self.output_root_dir = output_root_dir
        self.make_subdirs = make_subdirs
        self.include_model_name = include_model_name
        self.include_orig_name = include_orig_name

    def stop(self):
        """ Stop monitoring. """
        self.queue.put("DONE")

    def run(self):
        """ Wait for queue updates and copy files. """
        self._running = True

        while self._running:
            res = self.queue.get()

            if res == "DONE":
                break

            srcs, model_name = res
            copy_files(srcs, self.output_root_dir, model_name=model_name, include_model_name=self.include_model_name,
                       make_subdirs=self.make_subdirs, include_orig_name=self.include_orig_name)
