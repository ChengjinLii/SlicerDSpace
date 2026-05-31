import sys


def verb_msg(msg, PS):
    if not getattr(PS, 'quiet', False):
        print(msg)
        sys.stdout.flush()
