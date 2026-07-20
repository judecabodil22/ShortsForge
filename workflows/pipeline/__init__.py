def __getattr__(name):
    import importlib
    lazy_map = {
        "phase_download": "workflows.pipeline.phase_download",
        "phase_transcribe": "workflows.pipeline.phase_transcribe",
        "phase_context": "workflows.pipeline.phase_context",
        "phase_tts": "workflows.pipeline.phase_tts",
        "phase_lore": "workflows.pipeline.phase_lore",
        "pipeline_runner": "workflows.pipeline.pipeline_runner",
        "run_pipeline": "workflows.pipeline.pipeline_runner",
        "find_video": "workflows.pipeline.pipeline_runner",
        "video_info": "workflows.pipeline.pipeline_runner",
    }
    if name in lazy_map:
        mod = importlib.import_module(lazy_map[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
