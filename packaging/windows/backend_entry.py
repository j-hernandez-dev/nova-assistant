"""Console JSONL backend for Electron; never requires a system Python."""
import multiprocessing
import sys


def configure_utf8_stdio() -> None:
    """Set the wire encoding before imports or requests can use the streams.

    A frozen interpreter does not apply PYTHONIOENCODING during startup.
    Reconfigure the existing handles so JSONL input/output stays UTF-8 under
    Windows locales, including when Electron launches us without a console.
    Keep protocol errors strict; diagnostics can escape invalid surrogates.
    """
    for name, errors in (('stdin', 'strict'), ('stdout', 'strict'),
                         ('stderr', 'backslashreplace')):
        reconfigure = getattr(getattr(sys, name, None), 'reconfigure', None)
        if callable(reconfigure):
            reconfigure(encoding='utf-8', errors=errors)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    configure_utf8_stdio()
    if sys.argv[1:] in (['--runtime-info'], ['--check-browser']):
        import json
        from runtime_checks import runtime_info, check_browser
        result = check_browser() if sys.argv[1:] == ['--check-browser'] else runtime_info()
        print(json.dumps(result))
    else:
        from local_cli.__main__ import main
        main()
