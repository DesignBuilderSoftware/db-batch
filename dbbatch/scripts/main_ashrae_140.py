import os

from dbbatch.run_batch import WATCH_EPLUS, run_batch

if __name__ == "__main__":
    # CHANGE THIS TO A VALID PATH!
    root = r"C:\Users\vojtechp1\Desktop\Testing\ASHRAE 140\ASHRAE 140 2017 620xxx"

    models = os.path.join(root, "FABRIC", "TestFiles")
    outputs = os.path.join(root, "FABRIC", "Outputs")
    run_batch(
        models,
        outputs,
        analysis_type="eplus",
        watch_files=WATCH_EPLUS,
        make_output_subdirs=True,
        models_dirs_depth=2,
        timeout=300,
    )

    models = os.path.join(root, "HVAC", "HE100_230", "TestFiles")
    outputs = os.path.join(root, "HVAC", "HE100_230", "Outputs")
    run_batch(
        models,
        outputs,
        analysis_type="eplus",
        watch_files=WATCH_EPLUS,
        make_output_subdirs=True,
        models_dirs_depth=2,
        timeout=300,
    )

    # models = os.path.join(root, "HVAC", "AE101_445", "TestFiles")
    # outputs = os.path.join(root, "HVAC", "AE101_445", "Outputs")
    # run_batch(models, outputs, analysis_type="eplus", watch_files=WATCH_EPLUS,
    #           make_output_subdirs=True, models_dirs_depth=2, timeout=300)
    #
    # models = os.path.join(root, "HVAC", "CE100_200", "TestFiles")
    # outputs = os.path.join(root, "HVAC", "CE100_200", "Outputs")
    # run_batch(models, outputs, analysis_type="eplus", watch_files=WATCH_EPLUS,
    #           make_output_subdirs=True, models_dirs_depth=2, timeout=300)
    #
    # models = os.path.join(root, "HVAC", "CE300_545", "TestFiles")
    # outputs = os.path.join(root, "HVAC", "CE300_545", "Outputs")
    # run_batch(models, outputs, analysis_type="eplus", watch_files=WATCH_EPLUS,
    #           make_output_subdirs=True, models_dirs_depth=2, timeout=300)
