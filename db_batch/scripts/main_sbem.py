import os

from db_batch.run_batch import run_batch

# CHANGE THIS TO A VALID PATH!
root = r"C:\path\to\sbem\models"
outputs = os.path.join(root, "out")

if __name__ == "__main__":
    run_batch(
        root,
        outputs,
        analysis_type="sbem",
        include_orig_name=True,
        models_dirs_depth=2,
        timeout=300,
    )
