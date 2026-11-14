import os
if os.environ.get('CP_ISOLATION_ROOT'):
    try:
        import guard
        guard.install()
    except BaseException:
        os._exit(96)
