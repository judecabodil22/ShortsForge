def __getattr__(name):
    import importlib
    lazy_map = {
        "phase_tts": "workflows.pipeline.phase_tts",
        "phase_assemble": "workflows.pipeline.phase_assemble",
        "pipeline_runner": "workflows.pipeline.pipeline_runner",
        "run_pipeline": "workflows.pipeline.pipeline_runner",
        "find_video": "workflows.pipeline.pipeline_runner",
        "video_info": "workflows.pipeline.pipeline_runner",
    }
    if name in lazy_map:
        mod = importlib.import_module(lazy_map[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
