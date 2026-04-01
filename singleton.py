class Singleton(type):
    # https://stackoverflow.com/questions/6760685/what-is-the-best-way-of-implementing-a-singleton-in-python
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]