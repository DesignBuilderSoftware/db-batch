from db_batch.run_batch import WATCH_EPLUS, run_batch

if __name__ == "__main__":
    # CHANGE THIS TO A VALID PATH!
    root = r"C:\path\to\test\models"
    out = r"C:\path\to\results"

    attributes = [
        ("DailyOutput", 0),
        ("TimesteplyOutput", 0),
        ("HourlyOutput", 0),
        ("MonthlyOutput", 1),
    ]
    run_batch(
        root,
        out,
        analysis_type="eplus",
        watch_files=WATCH_EPLUS,
        make_output_subdirs=True,
        models_dirs_depth=2,
        timeout=3000,
        use_sim_manager=True,
        sim_start_date=(1, 1),
        sim_end_date=(1, 12),
        change_attributes=attributes,
        start_index=146,
    )
