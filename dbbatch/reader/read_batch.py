from pathlib import Path
import shutil
from dbbatch.misc_os import list_files
from dbbatch.reader.sbem_reader import SbemRequest, get_results

ROOT = Path(r"C:\Users\vojtechp1\Desktop\Testing\SBEM\Ireland - 6.1.7.001")
if __name__ == "__main__":
    pths = list_files(Path(ROOT, "TC22_Models_all_outputs"), ext="inp", depth=2)
    pths = [pth for pth in pths if "model_ber" in pth]
    req = SbemRequest("ACTUAL - BUILDING-DATA", "BUILDING_DATA", ["KWH/M2-HEAT",
                                                                  "KWH/M2-COOL",
                                                                  "KWH/M2-AUX",
                                                                  "KWH/M2-LIGHT",
                                                                  "KWH/M2-DHW",
                                                                  "KWH/M2-EQUP", ])
    results = get_results(pths, req)
    results.to_excel(Path(ROOT, "TC22_OUT.xlsx"))

    # only model_ber files are required for validation
    dest_root = Path(ROOT, "TC22_Models_out")
    dest_root.mkdir(exist_ok=True)
    for source_path in pths:
        name = Path(source_path).name
        shutil.copy(source_path, Path(dest_root, name))
