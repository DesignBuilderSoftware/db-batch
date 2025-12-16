import os
import traceback
from pathlib import Path
from shutil import copyfile

import psutil


def list_dirs(pth):
    """Return sub-directory paths."""
    content = os.listdir(pth)
    dirs = []
    for name in content:
        dir_pth = os.path.join(pth, name)
        if os.path.isdir(dir_pth):
            dirs.append(dir_pth)
    return dirs


def list_files(root, depth=1, ext="dsb"):
    """Return a list of all files with specified extension."""
    files_lst = []

    if not os.path.isdir(root):
        raise FileNotFoundError("Root folder '{}' does not exist!".format(root))

    _walk(root, files_lst, depth=depth, ext=ext)
    return files_lst


def to_absolute(paths):
    """Convert relative paths to absolute."""
    return [Path(path).resolve() for path in paths]


def _walk(root, files, depth=1, ext=None):
    """Walk directories to pick up files with specified extension."""
    dirs = []
    for name in os.listdir(root):
        pth = os.path.join(root, name)
        if os.path.isfile(pth):
            if ext:
                if pth.lower().endswith(ext):
                    files.append(pth)
        else:
            dirs.append(pth)
    if depth > 1:
        for pth in dirs:
            _walk(pth, files, depth=depth - 1, ext=ext)


def copy_files(
    srcs,
    dest,
    model_name=None,
    include_model_name=True,
    make_subdirs=False,
    include_orig_name=False,
):
    """Copy multiple files specified into a specific location."""
    for src in srcs:
        copy_file(
            src,
            dest,
            model_name=model_name,
            include_model_name=include_model_name,
            make_subdirs=make_subdirs,
            include_orig_name=include_orig_name,
        )


def file_name(pth):
    """
    Extract file name from the specified path.

    Returned file name includes extension.
    """
    return os.path.basename(pth)


def split_file_name_ext(pth):
    """
    Extract file name and extension from the specified file path.

    Returns a list [file name, extension]
    """
    basename = file_name(pth)
    return os.path.splitext(basename)


def create_dir(dir_pth):
    """Create directory for the specified dir path."""
    try:
        os.makedirs(dir_pth)
    except OSError:
        pass


def copy_file(
    src,
    dest,
    model_name=None,
    include_model_name=True,
    make_subdirs=False,
    include_orig_name=False,
):
    """
    Copy file.

    Parameters
    ----------
    src : str, path like
        Source file path.
    dest : str, path like
        Destination directory, if it does not exits
        it will be generated.
    model_name : str, default None
        If this field is used, name is added into
        the destination path.
    include_model_name : bool
        Defines if model name should be included in the copy title.
    make_subdirs : bool default False
        Defines if results should be placed in a subdirectory.
        This is only applicable when 'model_name' is defined.
    include_orig_name : bool
        If this is 'True' original name will be included in the
        copy title.
    """
    orig_name, ext = split_file_name_ext(src)
    out = file_name(src)

    if model_name and include_model_name:
        if include_orig_name:
            out = "{} - {}{}".format(model_name, orig_name, ext)
        else:
            out = "{}{}".format(model_name, ext)

    if make_subdirs and model_name:
        create_dir(os.path.join(dest, model_name))
        dest = os.path.join(dest, model_name, out)
    else:
        dest = os.path.join(dest, out)

    try:
        copyfile(src, dest)
    except IOError:
        print(
            "Cannot copy file '{}' to '{}'.\n{}".format(
                src, dest, traceback.format_exc()
            )
        )


def get_process(name):
    """Get process by name."""
    for p in psutil.process_iter():
        if p.name() == name:
            return p
    return None


def on_terminate(process):
    """Report status."""
    print("process {} terminated with exit code {}".format(process, process.returncode))


def kill_process(name="DesignBuilder.exe"):
    """Terminate DesignBuilder forcefully."""
    db = get_process(name)

    if db:
        print("Killing DesignBuilder process!")
        db.terminate()

        gone, alive = psutil.wait_procs([db], timeout=3, callback=on_terminate)
        for p in alive:
            p.kill()


def kill_process_when_idle(name="DesignBuilder.exe", idle_threshold=10, check_interval=0.5, startup_period=20):
    """
    Monitor process and kill it when CPU usage is below 0.1% for specified duration.

    Parameters
    ----------
    name : str
        Process name to monitor
    idle_threshold : float
        Time in seconds that process must be idle (0% CPU) before killing
    check_interval : float
        How often to check CPU usage in seconds
    startup_grace_period : float
        Time in seconds to wait before starting idle detection (allows process to start up)
    """
    import time

    process = get_process(name)
    if not process:
        return

    idle_time = 0
    has_been_active = False  # Track if process has ever been active

    try:
        # Wait for startup grace period
        if startup_period > 0:
            time.sleep(startup_period)

        while process.is_running():
            # Get CPU usage (interval=0.1 means measure over 0.1 seconds)
            cpu_percent = process.cpu_percent(interval=0.1)

            # Only start counting idle time after process has been active at least once
            CPU_TRESHOLD = 0.1  # Define what is considered "active" CPU usage
            if cpu_percent >= CPU_TRESHOLD:
                has_been_active = True
                idle_time = 0  # Reset idle counter
            elif has_been_active and cpu_percent < CPU_TRESHOLD:
                # Process was active before, now it's idle
                idle_time += check_interval
                if idle_time >= idle_threshold:
                    print(f"DesignBuilder process has been idle for {idle_time:.1f}s - terminating...")
                    process.terminate()
                    # Wait for graceful shutdown
                    _, alive = psutil.wait_procs([process], timeout=3)
                    if alive:
                        process.kill()
                    break

            time.sleep(check_interval)

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Process already ended or access denied
        pass
