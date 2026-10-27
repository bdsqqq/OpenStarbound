"""Only configured discovery; deliberately no compile/link/run class command."""
import os
import sys

sys.dont_write_bytecode = True
from acquirer import load, emit
from recipe import discover

if __name__ == '__main__':
    rules = load(os.fsencode(sys.argv[1]))
    emit(os.fsencode(sys.argv[2]), discover(rules))
