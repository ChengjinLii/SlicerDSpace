import os


def make_full_path(instr, work_dir=None):
    if work_dir is None:
        work_dir = os.getcwd()
    else:
        if not os.path.isabs(work_dir):
            work_dir = os.path.join(os.getcwd(), work_dir)

    def process_each(path):
        if not os.path.dirname(path):
            return os.path.join(work_dir, path)
        return path

    if isinstance(instr, str):
        return process_each(instr)
    if isinstance(instr, (list, tuple)):
        return [process_each(x) for x in instr]
    return instr
