import argparse
import os

from dbbatch.run_batch import run_batch

DB_PATH = "C:/Program Files (x86)/DesignBuilder/designbuilder.exe"
JOB_SERVER_DIR = "C:/ProgramData/DesignBuilder/JobServer/Users/User"
DB_DATA = os.path.join(os.getenv("LOCALAPPDATA"), "DesignBuilder")

parser = argparse.ArgumentParser(
    prog="run_db_batch",
    description="Run batch of DesignBuilder files and store results.",
)

parser.add_argument(
    "modelsDir", help="directory containing models to be run (may be nested)"
)
parser.add_argument("outputsDir", help="directory where results will be stored")
parser.add_argument(
    "--analysis",
    type=str,
    choices=["sbem", "eplus", "none"],
    default="eplus",
    help="requested analysis type, calculation is not triggered if set to 'none'",
)
parser.add_argument(
    "--dbPath",
    type=str,
    default=DB_PATH,
    help=f"path to DesignBuilder executable (default: {DB_PATH})",
)
parser.add_argument(
    "--jobServerDir",
    type=str,
    default=JOB_SERVER_DIR,
    help=f"path to 'job server' directory (default: {JOB_SERVER_DIR})",
)
parser.add_argument(
    "--dbAppDataDir",
    type=str,
    default=DB_DATA,
    help=f"path to 'db app data' directory (default: {DB_DATA})",
)
parser.add_argument(
    "--timeout",
    type=int,
    default=300,
    help="timeout in secs for a single file (default: 300)",
)
parser.add_argument(
    "--noClose", action="store_true", help="prevent db from closing after command"
)
parser.add_argument(
    "--startIndex", type=int, help="starting index of the batch run (default: 1)"
)
parser.add_argument(
    "--endIndex", type=int, help="last index of the batch run (default: -1)"
)
parser.add_argument(
    "--nSubDirs",
    type=int,
    default=1,
    help="look for DB files n levels deep (default: 1)",
)
parser.add_argument(
    "--simStartDate",
    type=int,
    nargs=2,
    help="force start date of the simulation, format DD MM",
)
parser.add_argument(
    "--simEndDate",
    type=int,
    nargs=2,
    help="force end date of the simulation, format DD MM",
)
parser.add_argument(
    "--outputSubDirs",
    action="store_true",
    help="create a results directory for each model",
)
parser.add_argument(
    "--noModelNames",
    action="store_true",
    help="do not add a model name to each output file",
)
parser.add_argument(
    "--originalNames",
    action="store_true",
    help="add file original name to an output file title",
)
parser.add_argument(
    "--useSimManager", action="store_true", help="force using 'Simulation Manager'"
)
parser.add_argument(
    "--report", action="store_true", help="write a simple batch summary report"
)
parser.add_argument(
    "--changeAttr",
    action="append",
    type=str,
    nargs=2,
    help="update a model attribute: attribute name value",
)

if __name__ == "__main__":
    args = parser.parse_args()
    kwargs = {
        "models_dirs_depth": args.nSubDirs,
        "analysis_type": args.analysis,
        "db_pth": args.dbPath,
        "job_server_dir": args.jobServerDir,
        "db_data_dir": args.dbAppDataDir,
        "timeout": args.timeout,
        "start_index": args.startIndex,
        "end_index": args.endIndex,
        "make_output_subdirs": args.outputSubDirs,
        "include_model_name": not args.noModelNames,
        "include_orig_name": args.originalNames,
        "write_report": args.report,
        "use_sim_manager": args.useSimManager,
        "change_attributes": args.changeAttr,
        "sim_start_date": args.simStartDate,
        "sim_end_date": args.simEndDate,
        "no_close": args.noClose,
    }
    str_args = f"\tmodels dir : {args.modelsDir}\n\toutputs dir : {args.outputsDir}\n"
    for k, v in kwargs.items():
        str_args += f"\t{k} : {v}\n"
    print(f"Running batch with following arguments:\n{str_args}")
    run_batch(args.modelsDir, args.outputsDir, **kwargs)
