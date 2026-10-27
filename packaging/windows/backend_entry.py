"""Console JSONL backend for Electron; never requires a system Python."""
import multiprocessing
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if sys.argv[1:] in (['--runtime-info'], ['--check-browser']):
        import json
        from runtime_checks import runtime_info, check_browser
        result = check_browser() if sys.argv[1:] == ['--check-browser'] else runtime_info()
        print(json.dumps(result))
    else:
        from local_cli.__main__ import main
        main()
