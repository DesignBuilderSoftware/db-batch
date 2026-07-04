import os
import traceback
import warnings
from pathlib import Path
from shutil import copyfile

from db_process import kill_process as _kill_process
from db_process import kill_when_idle as _kill_when_idle
from db_process import find_process as _find_process


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


# ---------------------------------------------------------------------------
# Deprecated wrappers — delegate to db_process
# ---------------------------------------------------------------------------
# These functions were moved to the ``db_process`` package.  The wrappers
# below keep backwards-compatibility for any external code that imports
# them from ``db_batch.misc_os``.


def get_process(name="DesignBuilder.exe"):
    """Get process by name.

    .. deprecated::
        Use ``db_process.find_process`` instead.
    """
    warnings.warn(
        "db_batch.misc_os.get_process is deprecated, use db_process.find_process",
        DeprecationWarning,
        stacklevel=2,
    )
    return _find_process(name)


def on_terminate(process):
    """Report status.

    .. deprecated::
        This callback is no longer used by db_process.
    """
    warnings.warn(
        "db_batch.misc_os.on_terminate is deprecated",
        DeprecationWarning,
        stacklevel=2,
    )
    print("process {} terminated with exit code {}".format(process, process.returncode))


def kill_process(name="DesignBuilder.exe"):
    """Terminate DesignBuilder forcefully.

    .. deprecated::
        Use ``db_process.kill_process`` instead.
    """
    warnings.warn(
        "db_batch.misc_os.kill_process is deprecated, use db_process.kill_process",
        DeprecationWarning,
        stacklevel=2,
    )
    return _kill_process(name)


def kill_process_when_idle(
    name="DesignBuilder.exe",
    idle_threshold=10,
    check_interval=0.5,
    startup_period=20,
):
    """Monitor process and kill it when CPU usage drops.

    .. deprecated::
        Use ``db_process.kill_when_idle`` instead.
    """
    warnings.warn(
        "db_batch.misc_os.kill_process_when_idle is deprecated, "
        "use db_process.kill_when_idle",
        DeprecationWarning,
        stacklevel=2,
    )
    return _kill_when_idle(
        name,
        idle_threshold=idle_threshold,
        check_interval=check_interval,
        startup_period=startup_period,
    )
