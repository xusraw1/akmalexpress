import string
import random


def get_random_symbols():
    return ''.join(random.sample(string.ascii_letters + string.hexdigits, 10))
